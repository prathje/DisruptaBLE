#include "ud3tn/bundle.h"
#include "ud3tn/bundle_fragmenter.h"
#include "ud3tn/bundle_processor.h"
#include "ud3tn/bundle_storage_manager.h"
#include "ud3tn/common.h"
#include "ud3tn/config.h"
#include "routing/epidemic/contact_manager.h"
#include "ud3tn/node.h"
#include "routing/router_task.h"
#include "routing/epidemic/routing_agent.h"
#include "routing/epidemic/router.h"
#include "ud3tn/task_tags.h"

#include "platform/hal_io.h"
#include "platform/hal_queue.h"
#include "platform/hal_semaphore.h"
#include "platform/hal_task.h"
#include "platform/hal_config.h"

#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

// Limit the amount of transmissions to nodes that are NOT the destination
// -1 Transmissions will not limit the amount of transmissions to other nodes
// Bundles will still be delivered to the destination node in all cases
#define EPIDEMIC_ROUTING_NUM_REPLICAS -1


// Limit the amount of hops to forward bundles to their destination
// 0 -> only directly deliver bundles to their destination (e.g. as in direct delivery)
// 1 -> only forward bundles once and then directly deliver them (e.g. as in spray-and-wait)
// -1 -> do not limit forwarding (e.g. classical epidemic flooding)
#define EPIDEMIC_ROUTING_FORWARDING -1


// While EPIDEMIC_ROUTING_NUM_REPLICAS and EPIDEMIC_ROUTING_FORWARDING need to be set to -1 for classical epidemic forwarding
// We can further tweak the settings to support both spray-and-wait and direct delivery (which are essentially limited variants)
// bundles are stored until their timeout

// TODO: Recheck https://tools.ietf.org/html/draft-irtf-dtnrg-ipnd-03 -> there the EID is part of the neighbor discovery
// Seems like we will also need to define neighbor discovery for BLE (!) -> we can split that to the BLE part and the initial connection setup? (e.g. BLE only GATT service UUID plus Service Data EID (hash?))
// THEN during connection setup use GATT / two channels ? / the one channel for setup by sending the same IPDTNNB packet on that reliable connection? -> covers ALL what we want... As we then know services, EID and cla address -> we can thus report a full node to the router! (not only the link address)
// the BLE NB could cache the nodes which are available at a specific point in time.


// TODO: Based on the link address, each party sends a hello message from their local endpoints to the routing AGENT
// This way, each can register the


// TODO: I think that we need to keep track of outdated bundles ourselves?
// TODO: Wrapping bundles in an Epidemic Routing Bundle could be nice?


// TODO: First send all bundles without checking which are alredy available? -> which will obviously be bad, then move on to send the distinct bundle hashes?!
// TODO: Use bundle source id, creation timestamp and sequence number together with the fragmentation (offset ?)


// TODO: I guess that we need to save the bundles (routed_bundles?!) that we want to (delete, forward?), deletion does not seem to be handled right now (-> select random bundle and check its timeout?
// TODO: Use hopcount! Seems fitting? -> but we need to make sure that we still deliver to the destination! Currently, hop count is only checked after local delivery! (but before routing so perfect for us?)


// TODO: We probably want to use the available contact struct to save the available links? Or we simply use custom helper structures for each connection to keep track of the bundles?


// TODO: Loop through all available contacts and pump connections full with bundles to send? (first send all bundles ofc)
// TODO: Do we also want to randomize this? (ignore duplicates?) or shall we use the timeouts as a way to determine forwarding?
// TODO: Maybe simply manage a htab of the routed_bundles locally too?

// TODO: We might want to limit the number of active connections?


static bool process_signal(
        struct router_signal signal,
        QueueIdentifier_t bp_signaling_queue,
        QueueIdentifier_t router_signaling_queue);

struct bundle_processing_result {
    int8_t status_or_fragments;
    bundleid_t fragment_ids[ROUTER_MAX_FRAGMENTS];
};

#define BUNDLE_RESULT_NO_ROUTE 0
#define BUNDLE_RESULT_NO_TIMELY_CONTACTS -1
#define BUNDLE_RESULT_NO_MEMORY -2
#define BUNDLE_RESULT_INVALID -3
#define BUNDLE_RESULT_EXPIRED -4


/**
 * This router task will first spawn our routing agent before handling the router signal queue
 * @param rt_parameters
 */
void router_task(void *rt_parameters)
{
    struct router_task_parameters *parameters =  (struct router_task_parameters *)rt_parameters;

    if(contact_manager_init() != UD3TN_OK) {
        LOG("RouterTask: Could not initialize contact manager!");
        return;
    }

    contact_manager_add_event_callback(router_handle_contact_event, NULL);
    contact_manager_add_event_callback(routing_agent_handle_contact_event, NULL);

    // we now initialize the router and routing_agent
    if(router_init(parameters->bundle_agent_interface) != UD3TN_OK) {
        LOG("RouterTask: Could not initialize router!");
        return;
    }

    if(routing_agent_init(parameters->bundle_agent_interface) != UD3TN_OK) {
        LOG("RouterTask: Could not initialize router agent!");
        return;
    }

    struct router_signal signal;

    ASSERT(rt_parameters != NULL);
    parameters = (struct router_task_parameters *)rt_parameters;

    for (;;) {
        if (hal_queue_receive(
                parameters->router_signaling_queue, &signal,
                100) == UD3TN_OK
                ) {
            process_signal(signal,
                           parameters->bundle_processor_signaling_queue,
                           parameters->router_signaling_queue
                   );
        } else {
            // TODO: Which order?
            routing_agent_update();
            router_update();
        }
    }
}

static inline enum bundle_processor_signal_type get_bp_signal(int8_t bh_result)
{
    switch (bh_result) {
        case BUNDLE_RESULT_EXPIRED:
            return BP_SIGNAL_BUNDLE_EXPIRED;
        default:
            return BP_SIGNAL_FORWARDING_CONTRAINDICATED;
    }
}

static inline enum bundle_status_report_reason get_reason(int8_t bh_result)
{
    switch (bh_result) {
        case BUNDLE_RESULT_NO_ROUTE:
            return BUNDLE_SR_REASON_NO_KNOWN_ROUTE;
        case BUNDLE_RESULT_NO_MEMORY:
            return BUNDLE_SR_REASON_DEPLETED_STORAGE;
        case BUNDLE_RESULT_EXPIRED:
            return BUNDLE_SR_REASON_LIFETIME_EXPIRED;
        case BUNDLE_RESULT_NO_TIMELY_CONTACTS:
        default:
            return BUNDLE_SR_REASON_NO_TIMELY_CONTACT;
    }
}

static bool process_signal(
        struct router_signal signal,
        QueueIdentifier_t bp_signaling_queue,
        QueueIdentifier_t router_signaling_queue)
{
    bool success = true;
    bundleid_t b_id;
    struct bundle *b;
    struct routed_bundle *rb;
    struct contact *contact;
    struct router_command *command;
    struct node *node;

    switch (signal.type) {
        case ROUTER_SIGNAL_PROCESS_COMMAND:
            command = (struct router_command *) signal.data;
            LOGF("RouterTask: Command (T = %c) ignored.", command->type);
            free_node(command->data);
            free(command);
            break;
        case ROUTER_SIGNAL_ROUTE_BUNDLE:

            b_id = (bundleid_t)(uintptr_t) signal.data;
            b = bundle_storage_get(b_id);
            if (b != NULL) {
                router_route_bundle(b);
            } // TODO: can we just ignore the other case?
            break;
        case ROUTER_SIGNAL_CONTACT_OVER:
            // TODO: remove stored contact information
            LOG("ROUTER_SIGNAL_CONTACT_OVER not supported");
            break;
        case ROUTER_SIGNAL_TRANSMISSION_SUCCESS:
            router_signal_bundle_transmission((struct routed_bundle *) signal.data, true);
            break;
        case ROUTER_SIGNAL_TRANSMISSION_FAILURE:
            router_signal_bundle_transmission((struct routed_bundle *) signal.data, false);
            break;
        case ROUTER_SIGNAL_OPTIMIZATION_DROP:
            LOG("ROUTER_SIGNAL_OPTIMIZATION_DROP not supported");
            break;
        case ROUTER_SIGNAL_WITHDRAW_NODE:
            LOG("ROUTER_SIGNAL_WITHDRAW_NODE not supported");
            break;
        case ROUTER_SIGNAL_NEW_LINK_ESTABLISHED:
            //LOG("ROUTER_SIGNAL_NEW_LINK_ESTABLISHED not supported");
            break;
        case ROUTER_SIGNAL_NEIGHBOR_DISCOVERED:
            {
                //LOG("ROUTER_SIGNAL_NEIGHBOR_DISCOVERED");
                struct node *neighbor = (struct node *) signal.data;
                if (neighbor) {
                    //LOGF("RouterTask: Neighbor Discovered %s, %s", neighbor->eid, neighbor->cla_addr);
                    contact_manager_handle_discovered_neighbor(neighbor); // handle_discovered_neighbor needs to free neighbor!
                } else {
                    LOG("RouterTask: ROUTER_SIGNAL_NEIGHBOR_DISCOVERED with null node");
                }
            }
            break;
        case ROUTER_SIGNAL_CONN_UP:;
            {
                char *cla_address = (char *) signal.data;
                if (cla_address) {
                    //LOGF("RouterTask: ROUTER_SIGNAL_CONN_UP %s", cla_address);
                    contact_manager_handle_conn_up(cla_address);
                    free(cla_address);
                } else {
                    LOG("RouterTask: ROUTER_SIGNAL_CONN_UP with null cla_address");
                }
            }
            break;
        case ROUTER_SIGNAL_CONN_DOWN:
            {
                char *cla_address = (char *)signal.data;
                if (cla_address) {
                    //LOGF("RouterTask: ROUTER_SIGNAL_CONN_DOWN %s", cla_address);
                    contact_manager_handle_conn_down(cla_address);
                    free(cla_address);
                } else {
                    LOG("RouterTask: ROUTER_SIGNAL_CONN_DOWN with null cla_address");
                }
            }
            break;
        default:
            LOGF("RouterTask: Invalid signal (%d) received!", signal.type);
            success = false;
            break;
    }
    return success;
}