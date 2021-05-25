#include "routing/epidemic/routing_agent.h"
#include "routing/epidemic/summary_vector.h"
#include "routing/epidemic/router.h"

#include "platform/hal_types.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>


#include "aap/aap.h"
#include "aap/aap_parser.h"
#include "aap/aap_serializer.h"
#include "agents/application_agent.h"
#include "bundle7/create.h"
#include "ud3tn/agent_manager.h"
#include "ud3tn/common.h"
#include "ud3tn/config.h"
#include "ud3tn/bundle.h"
#include "ud3tn/bundle_agent_interface.h"
#include "ud3tn/bundle_processor.h"
#include "ud3tn/bundle_storage_manager.h"
#include "ud3tn/task_tags.h"

#include "ud3tn/simplehtab.h"
#include "ud3tn/known_bundle_list.h"

#include "platform/hal_io.h"
#include "platform/hal_task.h"
#include "platform/hal_semaphore.h"

#define ROUTING_AGENT_SINK_PREFIX "routing/epidemic"
#define ROUTING_AGENT_SINK_OFFER (ROUTING_AGENT_SINK_PREFIX "/offer")
#define ROUTING_AGENT_SINK_REQUEST (ROUTING_AGENT_SINK_PREFIX "/request")

// TODO: Do we want to support even values below one second?
#define CONFIG_ROUTING_AGENT_SV_UPDATE_INTERVAL_S 5
#define CONFIG_ROUTING_AGENT_SV_EXPIRATION_BUFFER_S 2
#define CONFIG_ROUTING_AGENT_BUNDLE_LIFETIME_S 5

#define EPIDEMIC_ROUTING_INFO_BUNDLE_TYPE_OFFER 0
#define EPIDEMIC_ROUTING_INFO_BUNDLE_TYPE_REQUEST 1

// TODO: CONFIG_ROUTING_AGENT_SV_RESEND_INTERVAL_S?

// TODO: Convert list of known bundles to summary vector and send to others
// TODO: We need our list of local bundles and loop through it - do we need to assume that the summary vector is also ordered?
// TODO: CAn only handle bundles with creation_timestamp_ms


// The router calls the routing agent when bundles require routing (not the other way around!)
// it, however, has to filter the bundles for the epidemic endpoint as they are solely meant for "direct delivery"
// we keep a list of bundles that need to be routed further (e.g. a list of routed_bundle -> in the router or here?)

// the routing agent only decides if a bundles should be forwarded to another node (comparable to the routing table)


struct routing_agent_contact {
    const struct contact *contact;    // a pointer to contact_manager's contact
};

static struct routing_agent_config {
    const struct bundle_agent_interface *bundle_agent_interface;

    struct htab_entrylist *routing_agent_contact_htab_elem[CONFIG_BT_MAX_CONN]; // we should not have really more entries than active connections?
    struct htab routing_agent_contact_htab;
    Semaphore_t routing_agent_contact_htab_sem;
    struct known_bundle_list *known_bundle_list; // TODO: This also contains our custom bundles (which we do not need to offer -> use current bundles from router)
    char *source_eid;
} routing_agent_config;


bool routing_agent_is_info_bundle(const char* source_or_destination_eid) {
    const char *pos = strstr(source_or_destination_eid, ROUTING_AGENT_SINK_PREFIX);
    return pos != NULL;
}

static inline char *create_endpoint(const char *eid, const char* sink_identifier) {

    char *ep = malloc(
            strlen(eid) + strlen(sink_identifier) + 2); // 1 byte for "/", 1 for null termination

    if (!ep) {
        return NULL;
    }

    sprintf(ep, "%s/%s", eid, sink_identifier);

    return ep;
}


char * routing_agent_create_eid_from_info_bundle_eid(const char* source_or_destination_eid) {

    char * dup = strdup(source_or_destination_eid);
    char *pos = strstr(dup, "/" ROUTING_AGENT_SINK_PREFIX);
    if(pos != NULL) {
        *pos = '\0'; // we end the string already
    }
    return dup;
}

// TODO: optimize this..., especially as we hash all the time for the sv_entries!
static struct summary_vector *create_known_sv() {

    //TODO: We need to be careful that this is not the real one :)
    struct summary_vector *known_sv = router_create_known_sv();

    known_bundle_list_lock(routing_agent_config.known_bundle_list);

    KNOWN_BUNDLE_LIST_FOREACH(routing_agent_config.known_bundle_list, bundle_entry) {
        struct summary_vector_entry sv_entry;
        summary_vector_entry_from_bundle_unique_identifier(&sv_entry, &bundle_entry->unique_identifier);
        if (summary_vector_add_entry_by_copy(known_sv, &sv_entry) != UD3TN_OK) {
            summary_vector_destroy(known_sv);
            known_sv = NULL;
            break;
        }
    }
    known_bundle_list_unlock(routing_agent_config.known_bundle_list);

    return known_sv;
}


enum ud3tn_result send_sv(const char* sink, const char *destination_eid, struct summary_vector *sv) {

    char *dest_with_sink = create_endpoint(destination_eid, sink);

    if (!dest_with_sink) {
        LOGF("Routing Agent: Could not create destination eid to send SV with length %d to %s", sv->length, destination_eid);
        return UD3TN_FAIL;
    }

    LOGF("Routing Agent: Sending SV with length %d to %s", sv->length, dest_with_sink);

    size_t payload_size = summary_vector_memory_size(sv);
    uint8_t *payload = malloc(payload_size);

    summary_vector_copy_to_memory(sv, payload);

    if (!payload) {
        LOGF("Routing Agent: Could not allocate memory to send SV with length %d to %s", sv->length, destination_eid);
        free(dest_with_sink);
        return UD3TN_FAIL;
    }

    struct bundle *bundle = bundle7_create_local(
            payload, payload_size, routing_agent_config.source_eid, dest_with_sink,
            hal_time_get_timestamp_s(),
            CONFIG_ROUTING_AGENT_BUNDLE_LIFETIME_S,
            0);

    // we can now safely free the generated eid
    free(dest_with_sink);

    if (bundle == NULL) {
        LOGF("Routing Agent: Could not create bundle to send SV with length %d to %s", sv->length, destination_eid);
        return UD3TN_FAIL;
    }


    bundleid_t bundle_id = bundle_storage_add(bundle);

    if (bundle_id == BUNDLE_INVALID_ID) {
        LOGF("Routing Agent: Could not store bundle to send SV with length %d to %s", sv->length, destination_eid);
        bundle_free(bundle);
        return UD3TN_FAIL;
    }

    // from now on, the bundle and its resources (e.g. the payload are handled by the bundle processor)
    bundle_processor_inform(
            routing_agent_config.bundle_agent_interface->bundle_signaling_queue,
            bundle_id,
            BP_SIGNAL_BUNDLE_LOCAL_DISPATCH,
            BUNDLE_SR_REASON_NO_INFO
    );


    return UD3TN_OK;
}


// the routing agent registers a special endpoint to match the underlying cla address



static void on_offer_msg(struct bundle_adu data, void *param) {
    LOGF("Routing Agent: Got offer from \"%s\"", data.source);

    // extract real source id
    char *source = routing_agent_create_eid_from_info_bundle_eid(data.source);

    // create summary_vector from this message
    struct summary_vector *offer_sv = summary_vector_create_from_memory(data.payload, data.length);

    if (offer_sv) {

        //summary_vector_print("INCOMING OFFER SV ", offer_sv);
        // TODO: This is probably the least efficient variant possible... ;)
        struct summary_vector *known_sv = create_known_sv(source);
        //summary_vector_print("KNOWN SV ", known_sv);

        if (known_sv) {
            struct summary_vector *request_sv = summary_vector_create_diff(offer_sv, known_sv);

            if (request_sv) {
                //LOG("REQUEST SV");
                //summary_vector_print(request_sv);
                send_sv(ROUTING_AGENT_SINK_REQUEST, source,  request_sv);
                summary_vector_destroy(request_sv);
            } else {
                LOG("RoutingAgent: Could not create request_sv");
            }

            summary_vector_destroy(known_sv);
        } else {
            LOG("RoutingAgent: Could not create known_sv!");
        }

        summary_vector_destroy(offer_sv);
    } else {
        LOG("RoutingAgent: Could not parse offer sv!");
    }
    free(source);
    bundle_adu_free_members(data);
}

static void on_request_msg(struct bundle_adu data, void *param) {
    LOGF("Routing Agent: Got request from \"%s\"", data.source);

    // extract real source id
    char *source = routing_agent_create_eid_from_info_bundle_eid(data.source);

    // create summary_vector from this message
    struct summary_vector *request_sv = summary_vector_create_from_memory(data.payload, data.length);

    if (source && request_sv) {

        //summary_vector_print("INCOMING REQUEST SV ", request_sv);

        // we let the router directly handle the request summary vector (which also frees it!)
        router_update_request_sv(source, request_sv);
    } else {
        LOGF("Could not parse request sv from \"%s\"", data.source);
    }

    free(source);
    bundle_adu_free_members(data);
}




/**
 * Allocated resources are currently not destroyed
 * @param bundle_agent_interface
 */
enum ud3tn_result routing_agent_init(const struct bundle_agent_interface *bundle_agent_interface) {

    routing_agent_config.bundle_agent_interface = bundle_agent_interface;

    routing_agent_config.source_eid = create_endpoint(bundle_agent_interface->local_eid, ROUTING_AGENT_SINK_PREFIX);

    if (routing_agent_config.source_eid == NULL) {
        return UD3TN_FAIL;
    }

    htab_init(&routing_agent_config.routing_agent_contact_htab, CONFIG_BT_MAX_CONN, routing_agent_config.routing_agent_contact_htab_elem);

    routing_agent_config.routing_agent_contact_htab_sem = hal_semaphore_init_binary();

    if (!routing_agent_config.routing_agent_contact_htab_sem) {
        return UD3TN_FAIL;
    }

    hal_semaphore_release(routing_agent_config.routing_agent_contact_htab_sem);

    LOGF("Routing Agent: Trying to register offer sink with sid %s", ROUTING_AGENT_SINK_OFFER);
    int ret = bundle_processor_perform_agent_action(
            routing_agent_config.bundle_agent_interface->bundle_signaling_queue,
            BP_SIGNAL_AGENT_REGISTER,
            ROUTING_AGENT_SINK_OFFER,
            on_offer_msg,
            (void *) &routing_agent_config,
            true
    );

    if (ret) {
        LOG("Routing Agent: ERROR Failed to register sink!");
        hal_semaphore_delete(routing_agent_config.routing_agent_contact_htab_sem);
        return UD3TN_FAIL;
    }

    LOGF("Routing Agent: Trying to register request sink with sid %s", ROUTING_AGENT_SINK_REQUEST);

    ret = bundle_processor_perform_agent_action(
            routing_agent_config.bundle_agent_interface->bundle_signaling_queue,
            BP_SIGNAL_AGENT_REGISTER,
            ROUTING_AGENT_SINK_REQUEST,
            on_request_msg,
            (void *) &routing_agent_config,
            true
    );

    if (ret) {
        LOG("Routing Agent: ERROR Failed to register sink!");
        hal_semaphore_delete(routing_agent_config.routing_agent_contact_htab_sem);
        return UD3TN_FAIL;
    }

    LOG("Routing Agent: Getting access to list of known bundles");

    // We need to use the bundle list from the bundle_processor as local bundles would otherwise not be included
    // -> all bundles for this node would be retransmitted everytime
    while (bundle_processor_get_known_bundle_list(&routing_agent_config.known_bundle_list) != UD3TN_OK) {
        LOG("Routing Agent: Waiting for the bundle processor's list of known bundles");
        hal_task_delay(50);
    }

    // TODO: Initialize

    LOG("Routing Agent: Initialization finished!");
    return UD3TN_OK;
}

void routing_agent_send_offer_sv(const char *eid, struct summary_vector *offer_sv) {
    //hal_semaphore_take_blocking(routing_agent_config.routing_agent_contact_htab_sem);
    if (send_sv(ROUTING_AGENT_SINK_OFFER, eid,  offer_sv) != UD3TN_OK) {
        LOGF("Routing Agent: Could not send offer SV to %s", eid);
    }
    //hal_semaphore_release(routing_agent_config.routing_agent_contact_htab_sem);
}

void routing_agent_handle_contact_event(void *context, enum contact_manager_event event, const struct contact *contact) {

    (void)context; // currently unused


    // for now we only send bundles to active contacts, however we need the corresponding eid


    const char *eid = contact->node->eid;

    // we completely ignore contacts with invalid eids...

    if (IS_EID_NONE(eid)) {
        return;
    }


    // if contact is active but we do not yet know this contact -> add and initialize transmissions
    hal_semaphore_take_blocking(routing_agent_config.routing_agent_contact_htab_sem);

    struct routing_agent_contact *rc = htab_get(
            &routing_agent_config.routing_agent_contact_htab,
            eid
    );

    if (contact->active && rc == NULL) {
        rc = malloc(sizeof(struct routing_agent_contact));

        if (rc) {
            // Contact is already active, what else do we need to do?
            LOGF("Routing Agent: Added routing contact %s", eid);

            struct htab_entrylist *htab_entry = htab_add(
                    &routing_agent_config.routing_agent_contact_htab,
                    eid,
                    rc
            );

            if (htab_entry) {
                rc->contact = contact;
            } else {
                free(rc);
                LOG("Routing Agent: Error creating htab entry!");
            }
        } else {
            LOGF("Routing Agent: Could not allocate memory for routing contact for eid %s", eid);
        }
    } else if (!contact->active && rc != NULL) {
        // we remove the routing contact
        htab_remove(&routing_agent_config.routing_agent_contact_htab, eid);

        free(rc);   // TODO: Clear everything
        LOGF("Routing Agent: Removed routing contact %s", eid);
    }

    hal_semaphore_release(routing_agent_config.routing_agent_contact_htab_sem);
}

#if (CONFIG_FAKE_BUNDLE_INTERVAL > 0)

#define FAKE_DESTINATION "dtn://fake"
#include "platform/hal_random.h"

void generate_fake_bundles() {

    static uint32_t num_generated = 0;
    uint64_t cur = hal_time_get_timestamp_s();

    uint32_t planned = (cur / CONFIG_FAKE_BUNDLE_INTERVAL)+1;

    while(num_generated < planned) {

#if (CONFIG_FAKE_BUNDLE_SIZE_MAX > CONFIG_FAKE_BUNDLE_SIZE_MIN)
        uint32_t payload_length = (hal_random_get() % (CONFIG_FAKE_BUNDLE_SIZE_MAX-CONFIG_FAKE_BUNDLE_SIZE_MIN)) + CONFIG_FAKE_BUNDLE_SIZE_MIN;
#else
        uint32_t payload_length = CONFIG_FAKE_BUNDLE_SIZE_MIN;
#endif

        uint8_t *payload = malloc(payload_length);
        if (!payload) {
            LOG("RoutingAgent: Could not allocate fake payload!");
            return;
        }

        memset(payload, 0, payload_length);

         struct bundle *bundle = bundle7_create_local(
            payload, payload_length, routing_agent_config.bundle_agent_interface->local_eid, FAKE_DESTINATION,
            MAX(1, hal_time_get_timestamp_s()), // we force at least a ts of 1 as zero is the "unknown" ts
            CONFIG_FAKE_BUNDLE_LIFETIME,
            0);
        if (bundle == NULL) {
            LOG("RoutingAgent: Could not create fake bundle!");
            return;
        }

        bundleid_t bundle_id = bundle_storage_add(bundle);

        if (bundle_id != BUNDLE_INVALID_ID)
            bundle_processor_inform(
                    routing_agent_config.bundle_agent_interface->bundle_signaling_queue,
                    bundle_id,
                    BP_SIGNAL_BUNDLE_LOCAL_DISPATCH,
                    BUNDLE_SR_REASON_NO_INFO
            );
        else {
            bundle_free(bundle);
             LOG("RoutingAgent: Could not store fake bundle!");
            return;
        }
        num_generated++;
    }
}
#endif


void routing_agent_update() {

    // lock to correctly handle callbacks
    hal_semaphore_take_blocking(routing_agent_config.routing_agent_contact_htab_sem);

#if CONFIG_FAKE_BUNDLE_INTERVAL > 0
    generate_fake_bundles();
#endif

    // TODO: resend sv to contacts every X seconds?
    /*
    uint64_t cur = hal_time_get_timestamp_s();
    if (routing_agent_config.own_sv_ts + CONFIG_ROUTING_AGENT_SV_UPDATE_INTERVAL_S < cur) {
        routing_agent_config.own_sv_ts = cur;
    }*/

    hal_semaphore_release(routing_agent_config.routing_agent_contact_htab_sem);
}