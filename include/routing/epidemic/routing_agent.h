#ifndef ROUTING_AGENT_H_INCLUDED
#define ROUTING_AGENT_H_INCLUDED

#include "ud3tn/bundle_agent_interface.h"

#include <stdint.h>
#include "routing/epidemic/contact_manager.h"

void routing_agent_management_task(void *param);

void* routing_agent_management_config_init(const struct bundle_agent_interface *bundle_agent_interface) ;

/**
 * Called if a contact is active, eid needs to be copied (if required)
 */
void routing_agent_handle_contact_event(void *context, enum contact_manager_event event, const struct contact *contact);

#endif /* ROUTING_AGENT_H_INCLUDED */
