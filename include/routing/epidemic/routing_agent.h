#ifndef ROUTING_AGENT_H_INCLUDED
#define ROUTING_AGENT_H_INCLUDED

#include "ud3tn/bundle_agent_interface.h"

#include <stdint.h>
#include "routing/epidemic/contact_manager.h"
#include "routing/epidemic/summary_vector.h"

enum ud3tn_result routing_agent_init(const struct bundle_agent_interface *bundle_agent_interface);

/**
 * Called if a contact is active, eid needs to be copied (if required)
 */
void routing_agent_handle_contact_event(void *context, enum contact_manager_event event, const struct contact *contact);

void routing_agent_update();


bool routing_agent_is_info_bundle(const char* source_or_destination_eid);

char * routing_agent_create_eid_from_info_bundle_eid(const char* source_or_destination_eid);

/**
 * @param eid to send the sv to (ownership is not transferred)
 * @return
 */
void routing_agent_send_offer_sv(const char *eid, struct summary_vector *offer_sv);

#endif /* ROUTING_AGENT_H_INCLUDED */
