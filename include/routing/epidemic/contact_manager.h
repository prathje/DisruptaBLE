#ifndef CONTACTMANAGER_H_INCLUDED
#define CONTACTMANAGER_H_INCLUDED

#include "ud3tn/node.h"

#include "platform/hal_types.h"

#include <stdint.h>

enum contact_manager_event {
    CONTACT_EVENT_ADDED,
    CONTACT_EVENT_UPDATED,
    CONTACT_EVENT_REMOVED,
    CONTACT_EVENT_ACTIVE,
    CONTACT_EVENT_INACTIVE
};

typedef void (*contact_manager_cb)(void *context, enum contact_manager_event event, const struct contact *contact);
void contact_manager_set_event_callback(contact_manager_cb cb, void *context);


uint8_t remove_and_free_expired_contacts();

enum ud3tn_result send_bundle(const char *const eid, struct routed_bundle *routed_bundle);


/**
 * Handle a new neighbor, node needs to be freed (!)
 */
void handle_discovered_neighbor(struct node * node);

/**
 * Called if a new connection is available, cla_address needs to be copied
 * It is not guaranteed that we already know this neighbor (!)
 * (however we assume that neighbor discovery runs in the background so we eventually know the corresponding EID)
 */
void handle_conn_up(const char *cla_address);

/**
 * Called if a connection is not anymore available, cla_address needs to be copied
 */
void handle_conn_down(const char *cla_address);


#endif /* CONTACTMANAGER_H_INCLUDED */
