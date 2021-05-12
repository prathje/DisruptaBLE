#ifndef ROUTING_AGENT_H_INCLUDED
#define ROUTING_AGENT_H_INCLUDED

#include "ud3tn/bundle_agent_interface.h"

#include <stdint.h>

void routing_agent_management_task(void *param);

void* routing_agent_management_config_init(const struct bundle_agent_interface *bundle_agent_interface) ;

/**
 * Handle a new neighbor, eid and cla_address need to be copied (if required)
 */
void signal_new_neighbor(void *config, const char *eid, const char *cla_address);

/**
 * Called if a new connection is available, cla_address needs to be copied (if required)
 * It is not guaranteed that we already know this neighbor (!)
 * (however we assume that neighbor discovery runs in the background so we eventuall know the corresponding EID)
 */
void signal_conn_up(void *config, const char *cla_address);

/**
 * Called if a connection is not anymore available, cla_address needs to be copied (if required)
 */
void signal_conn_down(void *config, const char *cla_address);

#endif /* ROUTING_AGENT_H_INCLUDED */
