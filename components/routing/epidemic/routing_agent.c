#include "routing/epidemic/routing_agent.h"

#include "platform/hal_types.h"

#include <stdint.h>
#include <stdlib.h>


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

#include "platform/hal_io.h"
#include "platform/hal_task.h"

#define ROUTING_AGENT_SINK_IDENTIFIER "routing/epidemic"


struct routing_agent_config {
    const struct bundle_agent_interface *bundle_agent_interface;
};



char *create_routing_endpoint(const char* eid) {

    char *ep = malloc(strlen(eid) + strlen(ROUTING_AGENT_SINK_IDENTIFIER)+2); // 1 byte for "/", 1 for null termination

    if (!ep) {
        return NULL;
    }

    sprintf(ep, "%s/%s", eid, ROUTING_AGENT_SINK_IDENTIFIER);

    return ep;
}



static struct bundle *create_bundle(const char *local_eid, char *sink_id, char *destination,
                                    const uint64_t lifetime, void *payload, size_t payload_length)
{
    const size_t local_eid_length = strlen(local_eid);
    const size_t sink_length = strlen(sink_id);
    char *source_eid = malloc(local_eid_length + sink_length + 2);

    if (source_eid == NULL) {
        free(payload);
        return NULL;
    }

    memcpy(source_eid, local_eid, local_eid_length);
    source_eid[local_eid_length] = '/';
    memcpy(&source_eid[local_eid_length + 1], sink_id, sink_length + 1);

    struct bundle *result;

    result = bundle7_create_local(
            payload, payload_length, source_eid, destination,
            hal_time_get_timestamp_s(),
            lifetime, 0);

    free(source_eid);

    return result;
}

static bundleid_t create_forward_bundle(
        const struct bundle_agent_interface *bundle_agent_interface,
        char *sink_id, char *destination,
        const uint64_t lifetime, void *payload, size_t payload_length)
{
    struct bundle *bundle = create_bundle(
            bundle_agent_interface->local_eid,
            sink_id,
            destination,
            lifetime,
            payload,
            payload_length
    );

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
static bundleid_t send_info_bundle(const struct bundle_agent_interface *bundle_agent_interface, char *destination_eid, void *payload, size_t payload_length) {

    // we limit the lifetime of this meta bundle to a few seconds
    uint64_t lifetime = 5;

    char* dest = create_routing_endpoint(destination_eid);

    bundleid_t b = create_forward_bundle(
            bundle_agent_interface,
            ROUTING_AGENT_SINK_IDENTIFIER,
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

static void agent_msg_recv(struct bundle_adu data, void *param)
{
    struct routing_agent_config *const config = (
            (struct routing_agent_config *)param
    );

    (void)config;

    LOGF("Routing Agent: Got Bundle from \"%s\"", data.source);
    // TODO: Process Bundle
    bundle_adu_free_members(data);
}

void* routing_agent_management_config_init(const struct bundle_agent_interface *bundle_agent_interface) {
    struct routing_agent_config *routing_agent_config = malloc(sizeof(struct routing_agent_config));

    routing_agent_config->bundle_agent_interface = bundle_agent_interface;

    return routing_agent_config;
}

void routing_agent_management_task(void *param) {
    LOG("Routing Agent: Starting Epidemic Routing Agent...");
    const struct routing_agent_config *config = (const struct routing_agent_config *)param;


    LOGF("Routing Agent: Trying to register sink with sid %s", ROUTING_AGENT_SINK_IDENTIFIER);
    int ret = bundle_processor_perform_agent_action(
            config->bundle_agent_interface->bundle_signaling_queue,
            BP_SIGNAL_AGENT_REGISTER,
            ROUTING_AGENT_SINK_IDENTIFIER,
            agent_msg_recv,
            (void*) config,
            true
    );

    if (ret) {
        LOG("Routing Agent: ERROR Failed to register sink!");
        goto terminate;
    }

    LOG("Routing Agent: Registered sink");

    while(true) {
        hal_task_delay(20);
    }

    terminate:
    // Free the config in the end!
    free(config);

    // checkout routing_table on how to reschedule bundles
    // TODO: Do we
    // We might just merge the routing agent with the routing_task as we need a few signals in the agent as well
    // TODO: Handle ROUTER_SIGNAL_TRANSMISSION_SUCCESS?! checkout ret_constraints FAILED_FORWARD_POLICY use POLICY_TRY_RE_SCHEDULE?
    // I think that we can happily send to the bundle_processor whatever signal we want!
}

void routing_agent_handle_contact_event(void *context, enum contact_manager_event event, const struct contact *contact) {
    const struct routing_agent_config *config = (const struct routing_agent_config *)config;

    LOGF("Routing Agent: Contact Event %d", event);


    // we send a welcome bundle to the other node

    /*
     static char welcome_msg = "Hello World!";

    const struct routing_agent_config *config = (const struct routing_agent_config *)config;

    send_info_bundle(config->bundle_agent_interface)

    create_forward_bundle()*/
}