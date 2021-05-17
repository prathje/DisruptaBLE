#ifndef ROUTER_H_INCLUDED
#define ROUTER_H_INCLUDED


#include "ud3tn/simplehtab.h"
#include "ud3tn/bundle_processor.h"
#include "ud3tn/bundle.h"
#include "ud3tn/node.h"
#include "platform/hal_task.h"
#include "platform/hal_time.h"
#include "platform/hal_io.h"

#include "routing/epidemic/contact_manager.h"
#include "routing/epidemic/routing_agent.h"


struct bundle_info_list_entry {
    struct summary_vector_entry sv; // we directly compute it so we do not, e.g. hashing it
    bundleid_t id;
    uint64_t num_pending_transmissions; // -1 will result in infinite retransmissions, see CONFIG_EPIDEMIC_ROUTING_NUM_REPLICAS
    enum bundle_routing_priority prio;
    uint32_t size;
    uint64_t exp_time;
    struct bundle_info_list_entry *next;
};

struct bundle_info_list {
    struct bundle_info_list_entry *head;
    struct bundle_info_list_entry *tail;
};

struct router_contact {
    const struct contact *contact;    // a pointer to contact_manager's contact
    uint16_t index; // the contact's index to allow fast deletion

    struct bundle_info_list_entry *current_bundle; // the current bundle that is being transmitted
    struct bundle_info_list_entry *next_bundle_candidate; // the next bundle that MIGHT be transmitted, i.e. we need to check that first
};


struct router_config {
    const struct bundle_agent_interface *bundle_agent_interface;

    struct htab_entrylist *router_contact_htab_elem[CONFIG_BT_MAX_CONN];
    struct htab router_contact_htab;
    Semaphore_t router_contact_htab_sem;
    struct bundle_info_list bundle_info_list;

    struct router_contact *router_contacts[CONFIG_BT_MAX_CONN];
    uint16_t num_router_contacts;
};

enum ud3tn_result router_init(const struct bundle_agent_interface *bundle_agent_interface);
void router_handle_contact_event(void *context, enum contact_manager_event event, const struct contact *contact);
void router_update();

void router_signal_bundle_transmission(struct routed_bundle *routed_bundle, bool success);

void router_route_bundle(struct bundle *bundle);


//unused but called in init.c
struct router_config router_get_config(void);
enum ud3tn_result router_update_config(struct router_config config);

#endif /* ROUTER_H_INCLUDED */
