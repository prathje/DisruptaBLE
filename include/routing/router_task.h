#ifndef ROUTERTASK_H_INCLUDED
#define ROUTERTASK_H_INCLUDED

#include "ud3tn/bundle.h"
#include "ud3tn/node.h"

#include "platform/hal_types.h"

enum router_command_type {
	ROUTER_COMMAND_UNDEFINED,
	ROUTER_COMMAND_ADD = 0x31,    /* ASCII 1 */
	ROUTER_COMMAND_UPDATE = 0x32, /* ASCII 2 */
	ROUTER_COMMAND_DELETE = 0x33, /* ASCII 3 */
	ROUTER_COMMAND_QUERY = 0x34   /* ASCII 4 */
};

struct router_command {
	enum router_command_type type;
	struct node *data;
};

enum router_signal_type {
	ROUTER_SIGNAL_UNKNOWN = 0,
	ROUTER_SIGNAL_PROCESS_COMMAND,
	ROUTER_SIGNAL_ROUTE_BUNDLE,
	ROUTER_SIGNAL_CONTACT_OVER,
	ROUTER_SIGNAL_TRANSMISSION_SUCCESS,
	ROUTER_SIGNAL_TRANSMISSION_FAILURE,
	ROUTER_SIGNAL_WITHDRAW_NODE,
	ROUTER_SIGNAL_OPTIMIZATION_DROP,
	ROUTER_SIGNAL_NEW_LINK_ESTABLISHED,
	ROUTER_SIGNAL_NEIGHBOR_DISCOVERED, // notifies the router about new neighbor advertisements
	ROUTER_SIGNAL_CONN_UP, // TODO: for ml2cap, this means that the L2CAP connection is up and running
	ROUTER_SIGNAL_CONN_DOWN // TODO: for ml2cap, this means that we lost the L2CAP connection
};

struct router_signal {
	enum router_signal_type type;
	/* struct routed_bundle OR struct router_command */
	/* OR struct contact OR (void *)bundleid_t OR NULL */
	void *data;
};

struct router_task_parameters {
	QueueIdentifier_t router_signaling_queue;
	QueueIdentifier_t bundle_processor_signaling_queue;
    const struct bundle_agent_interface *bundle_agent_interface;
};

void router_task(void *args);

#endif /* ROUTERTASK_H_INCLUDED */
