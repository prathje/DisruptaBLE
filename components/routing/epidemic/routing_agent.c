#include "routing/epidemic/routing_agent.h"
#include "routing/epidemic/summary_vector.h"

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

#define ROUTING_AGENT_SINK_IDENTIFIER "routing/epidemic"

// TODO: Do we want to support even values below one second?
#define CONFIG_ROUTING_AGENT_SV_UPDATE_INTERVAL_S 5
#define CONFIG_ROUTING_AGENT_SV_EXPIRATION_BUFFER_S 2

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
    struct summary_vector *sv; // we use a pointer to mark that a summary vector is uninitialized
    uint64_t sv_received_ts;
};

static struct routing_agent_config {
    const struct bundle_agent_interface *bundle_agent_interface;

    struct htab_entrylist *routing_agent_contact_htab_elem[CONFIG_BT_MAX_CONN]; // we should not have really more entries than active connections?
    struct htab routing_agent_contact_htab;
    Semaphore_t routing_agent_contact_htab_sem;
    struct known_bundle_list *known_bundle_list;
    struct summary_vector *own_sv;
    uint64_t own_sv_ts;
    char *source_eid;
} routing_agent_config;


bool routing_agent_is_info_bundle(const char* source_or_destination_eid) {
    const char *pos = strstr(source_or_destination_eid, ROUTING_AGENT_SINK_IDENTIFIER);
    return pos != NULL;
}

char *create_routing_endpoint(const char *eid) {

    char *ep = malloc(
            strlen(eid) + strlen(ROUTING_AGENT_SINK_IDENTIFIER) + 2); // 1 byte for "/", 1 for null termination

    if (!ep) {
        return NULL;
    }

    sprintf(ep, "%s/%s", eid, ROUTING_AGENT_SINK_IDENTIFIER);

    return ep;
}

char * routing_agent_create_eid_from_info_bundle_eid(const char* source_or_destination_eid) {

    char * dup = strdup(source_or_destination_eid);
    char *pos = strstr(dup, ROUTING_AGENT_SINK_IDENTIFIER);
    if(pos != NULL) {
        *pos = '\0'; // we end the string already
    }
    return dup;
}

static bundleid_t create_forward_bundle(
        const struct bundle_agent_interface *bundle_agent_interface,
            char *destination,
        const uint64_t lifetime, void *payload, size_t payload_length) {

    struct bundle *bundle = bundle7_create_local(
            payload, payload_length, routing_agent_config.source_eid, destination,
            hal_time_get_timestamp_s(),
            lifetime, 0);

    if (bundle == NULL)
        return BUNDLE_INVALID_ID;

    bundleid_t bundle_id = bundle_storage_add(bundle);

    if (bundle_id != BUNDLE_INVALID_ID)
        bundle_processor_inform(
                bundle_agent_interface->bundle_signaling_queue,
                bundle_id,
                BP_SIGNAL_BUNDLE_LOCAL_DISPATCH,
                BUNDLE_SR_REASON_NO_INFO
        );
    else
        bundle_free(bundle);

    return bundle_id;
}

/**
 * We use info bundles to exchange information from one epidemic service to the other
 * Based on this information exchange, we will e.g. queue "real" data bundles etc.
 */
static bundleid_t
send_info_bundle(const struct bundle_agent_interface *bundle_agent_interface, char *destination_eid, void *payload,
                 size_t payload_length) {

    // we limit the lifetime of this meta bundle to a few seconds
    uint64_t lifetime = 5;

    char *dest = create_routing_endpoint(destination_eid);

    bundleid_t b = create_forward_bundle(
            bundle_agent_interface,
            dest,
            lifetime,
            payload,
            payload_length);

    free(dest);
    return b;
}



// TODO: Maybe store the bundles in this agent temporarily?!?

// This routing agent is also a normal agent as for example an application agent, it uses a special
// the associated router task further informs this routing agent, so that the epidemic routing is both an agent an the router task


// the routing agent registers a special endpoint to match the underlying cla address (namely the

// as uD3TN does currently not support registration of multiple endpoints -> we use the simple fact that bundles get directly forwarded to routing again

static void agent_msg_recv(struct bundle_adu data, void *param) {
    struct routing_agent_config *const config = (
            (struct routing_agent_config *) param
    );

    (void) config;

    LOGF("Routing Agent: Got Bundle from \"%s\"", data.source);
    // TODO: Process Bundle, extract SV :)
    bundle_adu_free_members(data);
}

// TODO: How can we prevent that we send the bundles to their original sender?
// TODO: How can we prevent that in a three device scenario, we don't directly transmit the same bundles to e.g. the third node?
// TODO: We should not recalculate everything everytime (!)
static void update_own_sv() {

    // delete the old sv
    if (routing_agent_config.own_sv != NULL) {
        summary_vector_destroy(routing_agent_config.own_sv);
    }

    routing_agent_config.own_sv = summary_vector_create();

    known_bundle_list_lock(routing_agent_config.known_bundle_list);

    uint64_t cur = hal_time_get_timestamp_s();
    routing_agent_config.own_sv_ts = cur;

    KNOWN_BUNDLE_LIST_FOREACH(routing_agent_config.known_bundle_list, bundle_entry) {

        // TODO: although we add some buffer here,
        if (bundle_entry->deadline + CONFIG_ROUTING_AGENT_SV_EXPIRATION_BUFFER_S < cur) {
            continue;
        }

        if (routing_agent_is_info_bundle(bundle_entry->unique_identifier.source)) {
            continue;
        }

        struct summary_vector_entry sv_entry;
        summary_vector_entry_from_bundle_unique_identifier(&sv_entry, &bundle_entry->unique_identifier);
        summary_vector_add_entry(routing_agent_config.own_sv, &sv_entry); // TODO: Check if this was successful!
    }
    known_bundle_list_unlock(routing_agent_config.known_bundle_list);
}


/**
 * TODO: Allocated resources are currently not destroyed
 * @param bundle_agent_interface
 */
enum ud3tn_result routing_agent_init(const struct bundle_agent_interface *bundle_agent_interface) {

    routing_agent_config.bundle_agent_interface = bundle_agent_interface;


    routing_agent_config.source_eid = create_routing_endpoint(bundle_agent_interface->local_eid);
    if (routing_agent_config.source_eid == NULL) {
        return UD3TN_FAIL;
    }

    htab_init(&routing_agent_config.routing_agent_contact_htab, CONFIG_BT_MAX_CONN, routing_agent_config.routing_agent_contact_htab_elem);

    routing_agent_config.routing_agent_contact_htab_sem = hal_semaphore_init_binary();

    if (!routing_agent_config.routing_agent_contact_htab_sem) {
        return UD3TN_FAIL;
    }

    hal_semaphore_release(routing_agent_config.routing_agent_contact_htab_sem);

    LOGF("Routing Agent: Trying to register sink with sid %s", ROUTING_AGENT_SINK_IDENTIFIER);
    int ret = bundle_processor_perform_agent_action(
            routing_agent_config.bundle_agent_interface->bundle_signaling_queue,
            BP_SIGNAL_AGENT_REGISTER,
            ROUTING_AGENT_SINK_IDENTIFIER,
            agent_msg_recv,
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

    // as we now the bundle list, we can update our summary vector
    update_own_sv();

    LOG("Routing Agent: Initialization finished!");
    return UD3TN_OK;
}

static void send_sv_unsafe(struct routing_agent_contact *rc) {

    size_t payload_size = summary_vector_memory_size(routing_agent_config.own_sv);
    void *payload = malloc(payload_size);

    char *eid = rc->contact->node->eid;

    if (payload) {
       // bundleid_t b =
                send_info_bundle(routing_agent_config.bundle_agent_interface, eid, payload, payload_size);
        LOGF("Routing Agent: Send SV with size %d to %s", payload_size, eid);
    } else {
        LOGF("RoutingAgent: Could not send summary vector with size %d to %s", payload_size, eid);
    }
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
                // TODO: Initialize everything
                rc->sv = NULL; // this will be initialized once we got a valid sv
                rc->sv_received_ts = 0; // this will be initialized once we got a valid sv

                // we send our sv bundle to the other node

                send_sv_unsafe(rc);
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

bool routing_agent_contact_active(const char *eid) {
    if (IS_EID_NONE(eid)) {
        return false;
    }

    bool ret = false;
    hal_semaphore_take_blocking(routing_agent_config.routing_agent_contact_htab_sem);

    struct routing_agent_contact *rc = htab_get(
            &routing_agent_config.routing_agent_contact_htab,
            eid
    );

    if (rc && rc->sv != NULL) {
        ret = true; // contact seems to be active
    }

    hal_semaphore_release(routing_agent_config.routing_agent_contact_htab_sem);
    return ret;
}


void routing_agent_update() {

    uint64_t cur = hal_time_get_timestamp_s();
    if (routing_agent_config.own_sv_ts + CONFIG_ROUTING_AGENT_SV_UPDATE_INTERVAL_S < cur) {
        update_own_sv(); // sv needs an update
    }

    // TODO: resend sv to contacts every X seconds?
}

bool routing_agent_contact_knows(const char *eid, struct summary_vector_entry *entry) {

    if (IS_EID_NONE(eid)) {
        return true;
    }

    bool ret = true; // we assume that the entry exists in the general case
    hal_semaphore_take_blocking(routing_agent_config.routing_agent_contact_htab_sem);

    struct routing_agent_contact *rc = htab_get(
            &routing_agent_config.routing_agent_contact_htab,
            eid
    );

    if (rc && rc->sv) {
        ret = summary_vector_contains_entry(rc->sv, entry);
    }

    hal_semaphore_release(routing_agent_config.routing_agent_contact_htab_sem);
    return ret;
}