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

#define ROUTING_AGENT_SINK_POSTFIX "/routing/epidemic"



struct routing_agent_config {
    const struct bundle_agent_interface *bundle_agent_interface;
};


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

    char *sink_identifier = malloc(strlen(config->bundle_agent_interface->local_eid) + strlen(ROUTING_AGENT_SINK_POSTFIX)+1);

    if (!sink_identifier) {
        LOG("Routing Agent: ERROR Failed to allocate the sink identifier");
        goto terminate;
    }



    sprintf(sink_identifier, "%s%s", config->bundle_agent_interface->local_eid, ROUTING_AGENT_SINK_POSTFIX);
    LOGF("Routing Agent: Trying to register sink with sid %s", sink_identifier);

    int ret = bundle_processor_perform_agent_action(
            config->bundle_agent_interface->bundle_signaling_queue,
            BP_SIGNAL_AGENT_REGISTER,
            sink_identifier,
            agent_msg_recv,
            config,
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


void signal_new_neighbor(void *config, const char *eid, const char *cla_address) {
    LOGF("RouterAgent: Neighbor Discovered %s, %s", eid, cla_address);
}

void signal_conn_up(void *config, const char *cla_address) {
    LOGF("RouterAgent: Conn UP %s", cla_address);
}

void signal_conn_down(void *config, const char *cla_address) {
    LOGF("RouterAgent: Conn DOWN %s", cla_address);
}