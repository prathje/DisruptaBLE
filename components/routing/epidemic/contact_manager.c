#include "ud3tn/common.h"
#include "routing/epidemic/contact_manager.h"
#include "routing/epidemic/routing_agent.h"
#include "routing/router_task.h"
#include "ud3tn/node.h"
#include "ud3tn/task_tags.h"

#include "cla/cla.h"
#include "cla/cla_contact_tx_task.h"

#include "platform/hal_config.h"
#include "platform/hal_io.h"
#include "platform/hal_platform.h"
#include "platform/hal_queue.h"
#include "platform/hal_semaphore.h"
#include "platform/hal_task.h"

#include <stddef.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>


#ifndef CONFIG_CONTACT_TIMEOUT_S
#define CONFIG_CONTACT_TIMEOUT_S 60
#endif


struct contact_info {
    struct contact *contact;
    struct cla_config *cla_conf;
};

// we just use two callbacks atm, one for the routing agent and another for the actual router
// we use callbacks as there is not really a need for this contact manager to now any specific functionality
#define CONTACT_MANAGER_NUM_CALLBACKS 2

static struct contact_manager_config {
    uint8_t num_event_cb;
    contact_manager_cb event_cb[CONTACT_MANAGER_NUM_CALLBACKS];
    void *event_cb_context[CONTACT_MANAGER_NUM_CALLBACKS];
    int8_t current_contact_count;
    struct contact_info current_contacts[MAX_CONCURRENT_CONTACTS];
    Semaphore_t sem;
} cm_config;


enum ud3tn_result contact_manager_init() {
    cm_config.num_event_cb = 0;
    cm_config.current_contact_count = 0;
    cm_config.sem = hal_semaphore_init_binary();

    if (!cm_config.sem) {
        return UD3TN_FAIL;
    }
    hal_semaphore_release(cm_config.sem);


    return UD3TN_OK;
}


/**
 * TODO: This is not yet thread-safe!
 */
void contact_manager_add_event_callback(contact_manager_cb cb, void *context) {
    if (cm_config.num_event_cb < CONTACT_MANAGER_NUM_CALLBACKS) {
        cm_config.event_cb[cm_config.num_event_cb] = cb;
        cm_config.event_cb_context[cm_config.num_event_cb] = context;
        cm_config.num_event_cb++;
    }
}

static void on_event(enum contact_manager_event event, const struct contact *contact) {
    for(uint8_t i = 0; i < cm_config.num_event_cb; i++) {
        if (cm_config.event_cb[i] != NULL) {
            cm_config.event_cb[i](cm_config.event_cb_context[i], event, contact);
        }
    }
}


/**
 * This does not free the contacts! use remove_and_free_expired_contacts for that...
 * TODO: This is not yet thread-safe!
 */
static int8_t remove_expired_contacts(
	const uint64_t current_timestamp, struct contact_info list[])
{
	/* Check for ending contacts */
	/* We do this first as it frees space in the list */
	int8_t i, c, removed = 0;

	// update all active contacts to be active as of this current_timestamp
    for (i = cm_config.current_contact_count - 1; i >= 0; i--) {
        if (cm_config.current_contacts[i].contact->active) {
            cm_config.current_contacts[i].contact->to = Z_MAX(current_timestamp, cm_config.current_contacts[i].contact->to);
        }
    }

	// we add a timeout so we do not directly remove the contacts
	uint64_t timeout = current_timestamp + CONFIG_CONTACT_TIMEOUT_S;

	for (i = cm_config.current_contact_count - 1; i >= 0; i--) {
		if (cm_config.current_contacts[i].contact->to <= timeout) {
			ASSERT(i <= MAX_CONCURRENT_CONTACTS);

			/* Unset "active" constraint */
			if (cm_config.current_contacts[i].contact->active) {
                cm_config.current_contacts[i].contact->active = 0;
                on_event(CONTACT_EVENT_INACTIVE, cm_config.current_contacts[i].contact);
			}

            on_event(CONTACT_EVENT_REMOVED, cm_config.current_contacts[i].contact);

			/* The TX task takes care of re-scheduling */
			list[removed++] = cm_config.current_contacts[i];
			/* If it's not the last element, we have to move mem */
			if (i != cm_config.current_contact_count - 1) {
				for (c = i; c < cm_config.current_contact_count; c++)
                    cm_config.current_contacts[c] =
                            cm_config.current_contacts[c+1];
			}
            cm_config.current_contact_count--;
		}
	}

	return removed;
}


/**
 * This does also free the contacts!
 * TODO: This is not yet thread-safe!
 */
static uint8_t remove_and_free_expired_contacts()
{
    // TODO: This could be a bit heavy for the stack ;)
    static struct contact_info removed_contacts[MAX_CONCURRENT_CONTACTS];

    int8_t i;
    uint64_t current_timestamp = hal_time_get_timestamp_s();
    int8_t removed_count = remove_expired_contacts(
            current_timestamp,
            removed_contacts
    );

    for (i = 0; i < removed_count; i++) {
        LOGF("ContactManager: Contact with \"%s\" ended.",
             removed_contacts[i].contact->node->eid);

        if (removed_contacts[i].cla_conf) {
            removed_contacts[i].cla_conf->vtable->cla_end_scheduled_contact(
                    removed_contacts[i].cla_conf,
                    removed_contacts[i].contact->node->eid,
                    removed_contacts[i].contact->node->cla_addr
            );
        }
        free_contact(removed_contacts[i].contact);
        removed_contacts[i].contact = NULL;
    }

    return removed_count;
}

uint8_t contact_manager_remove_and_free_expired_contacts() {
    hal_semaphore_take_blocking(cm_config.sem);
    uint8_t res = remove_and_free_expired_contacts();
    hal_semaphore_release(cm_config.sem);
    return res;
}

/**
 * TODO: This is not yet thread-safe!
 * TODO: This is currently not efficient
 */
static struct contact_info * find_contact_info_by_eid(const char *const eid) {

    struct contact_info *found = NULL;

    for (int i = cm_config.current_contact_count - 1; i >= 0; i--) {
        const char * const contact_eid = cm_config.current_contacts[i].contact->node->eid;
        if (!strcmp(eid, contact_eid)) {
            found = &cm_config.current_contacts[i];
            break;
        }
    }

    return found;
}

/**
 * TODO: This is not yet thread-safe!
 * TODO: This is currently not efficient
 */
static struct contact_info * find_contact_info_by_cla_addr(const char *const cla_addr) {

    struct contact_info *found = NULL;

    for (int i = cm_config.current_contact_count - 1; i >= 0; i--) {
        const char * const contact_cla_addr = cm_config.current_contacts[i].contact->node->cla_addr;
        if (!strcmp(cla_addr, contact_cla_addr)) {
            found = &cm_config.current_contacts[i];
            break;
        }
    }

    return found;
}

/**
 * TODO: This is currently not efficient
 */
static enum ud3tn_result try_to_send_bundle(struct routed_bundle *routed_bundle, int timeout) {


    struct contact_info * contact_info = NULL;

    if (routing_agent_is_info_bundle(routed_bundle->destination)) {

        char *destination_override = routing_agent_create_eid_from_info_bundle_eid(routed_bundle->destination);

        if (!destination_override) {
            return UD3TN_FAIL;
        }
        contact_info = find_contact_info_by_eid(destination_override);
        free(destination_override);
    } else {
        contact_info = find_contact_info_by_eid(routed_bundle->destination);
    }

    if (!contact_info) {
        return UD3TN_FAIL;
    }

    struct contact * contact = contact_info->contact;
    struct node * node = contact->node;

    ASSERT(node->cla_addr != NULL);

    if (contact_info->cla_conf == NULL) {
        contact_info->cla_conf = cla_config_get(
                node->cla_addr
        );
    }

    ASSERT(contact_info->cla_conf != NULL); // We should always have the corresponding CLA layer available

    // Get the corresponding tx_queue handler, note that this will also lock it -> we have to free it once if successfull
    struct cla_tx_queue tx_queue = contact_info->cla_conf->vtable->cla_get_tx_queue(
            contact_info->cla_conf,
            node->eid,
            node->cla_addr
    );

    if (!tx_queue.tx_queue_handle) {
        LOGF("ContactManager: Could not obtain queue for TX to \"%s\" via \"%s\"",
             node->eid, node->cla_addr);
        // Re-scheduling will be done by routerTask or transmission will
        // occur after signal of new connection.
        return UD3TN_FAIL;
    }

    LOGF("ContactManager: Sending bundles for contact with \"%s\"", node->eid);

    struct cla_contact_tx_task_command command = {
            .type = TX_COMMAND_BUNDLES,
            .bundles = NULL,
    };

    command.bundles = malloc(sizeof(struct routed_bundle_list));
    command.bundles->data = routed_bundle;
    command.bundles->next = NULL;

    enum ud3tn_result res = hal_queue_try_push_to_back(tx_queue.tx_queue_handle, &command, timeout);
    if (res == UD3TN_FAIL) {
        free(command.bundles);
    }

    hal_semaphore_release(tx_queue.tx_queue_sem); // taken by get_tx_queue

    return res;
}


enum ud3tn_result contact_manager_try_to_send_bundle(struct routed_bundle *routed_bundle, int timeout) {

    // TODO: blocking would lead to deadlocks in case the router or agent sends data in a contact event
    if (hal_semaphore_try_take(cm_config.sem, timeout) == UD3TN_FAIL) {
        return UD3TN_FAIL;
    }

    enum ud3tn_result res = try_to_send_bundle(routed_bundle, timeout);
    hal_semaphore_release(cm_config.sem);
    return res;
}


/**
 * Adds node as a recent contact if not yet known. The node pointer will be handled by the contact manager, so its ownership is transferred to the callee.
 * uses the current timestamp to update the contacts from and to times
 * This is not yet thread-safe!
 */
static void handle_discovered_neighbor(struct node * node) {

    //LOGF("handle_discovered_neighbor: %s, %s", node->eid, node->cla_addr);
    ASSERT(node->eid != NULL);
    ASSERT(node->cla_addr != NULL);

    const uint64_t current_timestamp = hal_time_get_timestamp_s();
    struct contact_info *contact_info = find_contact_info_by_eid(node->eid);

    if (!contact_info) {
        // we try to find the contact by cla address as a fallback
        contact_info = find_contact_info_by_cla_addr(node->cla_addr);
    }

    if (!contact_info) {
        // we initialize contact_info
        if (cm_config.current_contact_count < MAX_CONCURRENT_CONTACTS) {
            contact_info = &cm_config.current_contacts[cm_config.current_contact_count];

            // reset values
            memset(contact_info, 0, sizeof(struct contact_info));

            contact_info->contact = contact_create(node);

            if (!contact_info->contact) {
                LOGF("Contact Manager: No place to handle contact for eid \"%s\"", node->eid);
                free_node(node);
                return;
            }
            contact_info->contact->to = current_timestamp;
            contact_info->contact->from = current_timestamp;
            cm_config.current_contact_count++;
            on_event(CONTACT_EVENT_ADDED, contact_info->contact);
        }

        if (!contact_info) {
            LOGF("Contact Manager: No place to handle node with eid \"%s\"", node->eid);
            free_node(node);
            return;
        }
    } else {
        // update the to value if the contact already existed
        contact_info->contact->to = Z_MAX(contact_info->contact->to, current_timestamp);

        // We also swap the node in order to have more up-to-date information about e.g. services or cla addrress
        free_node(contact_info->contact->node);
        contact_info->contact->node = node;
        on_event(CONTACT_EVENT_UPDATED, contact_info->contact);
    }
}

static void handle_missing_cla_address(const char *cla_address) {
    struct node * node = node_create(EID_NONE);
    if(!node) {
        return;
    }
    node->cla_addr = strdup(cla_address);
    handle_discovered_neighbor(node);
}

static void handle_conn_up(const char *cla_address) {
    struct contact_info *info = find_contact_info_by_cla_addr(cla_address);

    if (!info) {
        handle_missing_cla_address(cla_address);

        // search again ;)
        info = find_contact_info_by_cla_addr(cla_address);

        if (!info) {
            LOG("Could not handle missing cla address");
            return;
        }

        on_event(CONTACT_EVENT_ADDED, info->contact);
    }

    if (!info->contact->active) {
        info->contact->active = true;
        on_event(CONTACT_EVENT_ACTIVE, info->contact);
    }
}

static void handle_conn_down(const char *cla_address) {

    struct contact_info *info = find_contact_info_by_cla_addr(cla_address);

    if (!info) {
        handle_missing_cla_address(cla_address);

        // search again ;)
        info = find_contact_info_by_cla_addr(cla_address);

        if (!info) {
            LOG("Could not handle missing cla address");
            return;
        }
        on_event(CONTACT_EVENT_ADDED, info->contact);
    }

    if (info->contact->active) {
        info->contact->active = false;
        on_event(CONTACT_EVENT_INACTIVE, info->contact);
    }
}

void contact_manager_handle_discovered_neighbor(struct node * node) {
    hal_semaphore_take_blocking(cm_config.sem);
    handle_discovered_neighbor(node);
    hal_semaphore_release(cm_config.sem);
}

void contact_manager_handle_conn_up(const char *cla_address) {
    hal_semaphore_take_blocking(cm_config.sem);
    handle_conn_up(cla_address);
    hal_semaphore_release(cm_config.sem);
}

void contact_manager_handle_conn_down(const char *cla_address) {
    hal_semaphore_take_blocking(cm_config.sem);
    handle_conn_down(cla_address);
    hal_semaphore_release(cm_config.sem);
}