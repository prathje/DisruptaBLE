#ifndef CONTACTMANAGER_H_INCLUDED
#define CONTACTMANAGER_H_INCLUDED

#include "ud3tn/node.h"

#include "platform/hal_types.h"

#include <stdint.h>


#define IS_EID_NONE(eid) (!strcmp(eid, (EID_NONE)))

enum contact_manager_event {
    CONTACT_EVENT_ADDED,
    CONTACT_EVENT_UPDATED,
    CONTACT_EVENT_REMOVED,
    CONTACT_EVENT_ACTIVE,
    CONTACT_EVENT_INACTIVE
};


enum ud3tn_result contact_manager_init();

typedef void (*contact_manager_cb)(void *context, enum contact_manager_event event, const struct contact *contact);
void contact_manager_add_event_callback(contact_manager_cb cb, void *context);

//void contact_manager_get_current_contacts(contact_manager_cb cb, void *context);

// Thread-safe!
uint8_t contact_manager_remove_and_free_expired_contacts();

// Thread-safe!
enum ud3tn_result contact_manager_try_to_send_bundle(struct routed_bundle *routed_bundle, int timeout);

 /**
  * Handle a new neighbor, , Thread-safe
  * @param node (will be freed by this function)
  */
void contact_manager_handle_discovered_neighbor(struct node * node);

/**
 * Called if a new connection is available, cla_address needs to be copied
 * It is not guaranteed that we already know this neighbor (!)
 * (however we assume that neighbor discovery runs in the background so we eventually know the corresponding EID)
 *  Thread-safe
 */
void contact_manager_handle_conn_up(const char *cla_address);

/**
 * Called if a connection is not anymore available, cla_address needs to be copied
 * Thread-safe
 */
void contact_manager_handle_conn_down(const char *cla_address);


#endif /* CONTACTMANAGER_H_INCLUDED */
