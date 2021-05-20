
#include "routing/epidemic/router.h"
#include <stdlib.h>

// Limit the amount of transmissions to nodes that are NOT the destination
// -1 Transmissions will not limit the amount of transmissions to other nodes
// Bundles will still be delivered to the destination node in all cases
#define CONFIG_EPIDEMIC_ROUTING_NUM_REPLICAS -1


// Limit the amount of hops to forward bundles to their destination
// 0 -> only directly deliver bundles to their destination (e.g. as in direct delivery)
// 1 -> only forward bundles once and then directly deliver them (e.g. as in spray-and-wait)
// -1 -> do not limit forwarding (e.g. classical epidemic flooding)
#define CONFIG_EPIDEMIC_ROUTING_FORWARDING -1



static struct router_config router_config;


bool contact_should_receive(const char *eid, struct bundle_info_list_entry *candidate) {

    uint64_t cur_time = hal_time_get_timestamp_s();

    if (candidate->num_pending_transmissions == 0) {
        // TODO: Shall we do direct delivery in case the bundle destination is actually this contact?
        return false;
    }

    if (candidate->exp_time < cur_time) {
        return false; // bundle is sadly expired -> will be removed eventually
    }

    if (routing_agent_contact_knows(eid, &candidate->sv)) {
        return false; // bundle already known!
    }

    return true; // seems like this is a good candidate!
}


void signal_bundle_expired(struct bundle_info_list_entry *bundle_info) {

    const enum bundle_status_report_reason reason = BUNDLE_SR_REASON_LIFETIME_EXPIRED;
    const enum bundle_processor_signal_type signal = BP_SIGNAL_BUNDLE_EXPIRED;

    bundle_processor_inform(
            router_config.bundle_agent_interface->bundle_signaling_queue,
            bundle_info->id,
            signal,
            reason
    );
}

void update_bundle_info_list() {

    uint64_t cur_time = hal_time_get_timestamp_s();
    struct bundle_info_list_entry *current = router_config.bundle_info_list.head;
    struct bundle_info_list_entry *prev = NULL;

    // this loops through all available bundles and checks for possible expiration,
    //TODO: Delete old bundles if not enough space for new ones?
    while(current != NULL) {

        bool delete = false;
        if (current->exp_time < cur_time) {
            delete = true;
            // this bundle is invalid -> we try to delete it!
            // but only if no contact is trying to send it right now
            for(int i = router_config.num_router_contacts-1; i >= 0; i--) {
                if (current == router_config.router_contacts[i]->current_bundle) {
                    delete = false;
                    break;
                }
            }
        }

        if (delete) {
            struct bundle_info_list_entry *next = current->next;

            if (current == router_config.bundle_info_list.head) {
                // prev could be null in this case and is not relevant
                router_config.bundle_info_list.head = next;
            } else {
                // prev is not null!
                prev->next = next;
            }

            // current could also be the last one in the list -> we need to set it to the previous element! (which could also be null)
            if (current == router_config.bundle_info_list.tail) {
                router_config.bundle_info_list.tail = prev;
            }

            // we now need to update all references of the contacts (so they do not reference an old bundle!
            for(int i = router_config.num_router_contacts-1; i >= 0; i--) {
                if (current == router_config.router_contacts[i]->next_bundle_candidate) {
                    router_config.router_contacts[i]->next_bundle_candidate = next;
                }
            }

            signal_bundle_expired(current);

            free(current); //nothing more todo atm :)
            // prev stays the same
            current = next;
        } else {
            prev = current;
            current = current->next;
        }
    }
}


enum ud3tn_result try_to_send_bundle(const char* eid, struct bundle_info_list_entry *bundle_info) {

    struct routed_bundle *routed_bundle = malloc(sizeof(struct routed_bundle));

    if (routed_bundle == NULL)
        return UD3TN_FAIL;

    routed_bundle->id = bundle_info->id;

    routed_bundle->prio = bundle_info->prio;
    routed_bundle->size = bundle_info->size;
    routed_bundle->exp_time = bundle_info->exp_time;
    routed_bundle->destination = strdup(eid);
    routed_bundle->contacts = NULL;

    if (routed_bundle->destination == NULL) {
        free(routed_bundle);
        return UD3TN_FAIL;
    }

    enum ud3tn_result res = contact_manager_try_to_send_bundle(eid, routed_bundle, 0); // TODO: which timeout to use?

    if (res == UD3TN_FAIL) {
        free(routed_bundle->destination);
        free(routed_bundle);
    }

    return res;
}

static void send_bundles_to_contact(struct router_contact *router_contact ) {
    const char *eid = router_contact->contact->node->eid;

    // we need to wait for the routing agent to know the summary vector
    if (routing_agent_contact_active(eid)) {

        if (router_contact->current_bundle == NULL) {
            // we need a new transmission!

            struct bundle_info_list_entry *candidate = router_contact->next_bundle_candidate;

            while(candidate != NULL) {
                // we still have possible candidates to send!
                if (contact_should_receive(eid, candidate)) {
                    break; // we found a possible candidate! -> keep the candidate for now!
                } else {
                    // try the next entry!
                    candidate = candidate->next;
                }
            }

            // we found a good candidate!
            if (candidate != NULL) {
                // we try to schedule it
                if (try_to_send_bundle(eid, candidate) == UD3TN_OK) {

                    if (candidate->num_pending_transmissions > 0) {
                        candidate->num_pending_transmissions--;
                    }

                    // we could schedule the send process! this means that we get a transmission success / fail in all cases (even in case of a connection failure)
                    // we therefore set the curret bundle and further increment to the next_bundle_candidate (which could be null (!))
                    router_contact->current_bundle = candidate;
                    router_contact->next_bundle_candidate = candidate->next;
                }
            } else {
                // there were no possible candidates, however the router_route_bundle method sets the correct references in case a new bundle is available
            }
        }
    }
}

static void send_bundles() {
    for(int i = router_config.num_router_contacts-1; i >= 0; i--) {
        send_bundles_to_contact(router_config.router_contacts[i]);
    }
}


enum ud3tn_result router_init(const struct bundle_agent_interface *bundle_agent_interface) {
    memset(&router_config, 0, sizeof(struct router_config));
    router_config.bundle_agent_interface = bundle_agent_interface;

    htab_init(&router_config.router_contact_htab, CONFIG_BT_MAX_CONN, router_config.router_contact_htab_elem);

    router_config.router_contact_htab_sem = hal_semaphore_init_binary();

    if (!router_config.router_contact_htab_sem) {
        return UD3TN_FAIL;
    }

    hal_semaphore_release(router_config.router_contact_htab_sem);


    return UD3TN_OK;
}


void route_epidemic_bundle(struct bundle *bundle) {
    struct bundle_info_list_entry *info = malloc(sizeof(struct bundle_info_list_entry));

    if (!info) {
        //TODO: directly signal that we could not route this bundle!
        const enum bundle_status_report_reason reason = BUNDLE_SR_REASON_NO_KNOWN_ROUTE;
        const enum bundle_processor_signal_type signal = BP_SIGNAL_FORWARDING_CONTRAINDICATED;

        bundle_processor_inform(
                router_config.bundle_agent_interface->bundle_signaling_queue,
                bundle->id,
                signal,
                reason
        );
        return;
    }

    info->id = bundle->id;

    summary_vector_entry_from_bundle(&info->sv, bundle);
    info->num_pending_transmissions = CONFIG_EPIDEMIC_ROUTING_NUM_REPLICAS; // -1 will result in infinite retransmissions, see CONFIG_EPIDEMIC_ROUTING_NUM_REPLICAS


    info->prio = bundle_get_routing_priority(bundle);
    info->size = bundle_get_serialized_size(bundle);
    info->exp_time = bundle_get_expiration_time_s(bundle);

    info->next = NULL;
    // we append this element to list's tail

    struct bundle_info_list_entry *cur_tail = router_config.bundle_info_list.tail;

    router_config.bundle_info_list.tail = info;

    if (cur_tail) {
        ASSERT(cur_tail->next == NULL);
        cur_tail->next = info;
    } else {
        ASSERT(router_config.bundle_info_list.head == NULL);
        router_config.bundle_info_list.head = info;
    }


    bool needs_update = false;

    // we now add this bundle to every currently known contact that has no other candidates
    for(int i = router_config.num_router_contacts-1; i >= 0; i--) {
        struct router_contact *rc = router_config.router_contacts[i];
        if (rc->next_bundle_candidate == NULL) {
            rc->next_bundle_candidate = info;
            LOGF("Router: Found new candidate for contact %s", rc->contact->node->eid);
            needs_update = true;
        }
    }

    if (needs_update) {
        send_bundles(); // we directly try to send outstanding bundles
    }
}

bool route_info_bundle(struct bundle *bundle) {

    char * destination = routing_agent_create_eid_from_info_bundle_eid(bundle->destination);

    bool success = false;
    if (destination) {

        struct routed_bundle *rb = malloc(sizeof(struct routed_bundle));

        rb->id = bundle->id;
        rb->prio = bundle_get_routing_priority(bundle);
        rb->size = bundle_get_serialized_size(bundle);
        rb->exp_time = bundle_get_expiration_time_s(bundle);
        rb->destination = strdup(bundle->destination);
        rb->contacts = NULL;

        if (rb && rb->destination && contact_manager_try_to_send_bundle(destination, rb, 1000) == UD3TN_OK) {
            success = true;
        } else {
            free(rb->destination);
            free(rb);
        }

        free(destination);
    }

    return success;
}

/*
 * We store the relevant bundle info in the bundle_info_list, if we have contacts, that
 */
void router_route_bundle(struct bundle *bundle) {

    LOGF("Router: Routing bundle %d to %s", bundle->id, bundle->destination);

    bool success = false;
    if(routing_agent_is_info_bundle(bundle->destination)) {
        success = route_info_bundle(bundle);
    } else {
        success = true;
        route_epidemic_bundle(bundle);
    }

    const enum bundle_status_report_reason reason = success ? BUNDLE_SR_REASON_NO_INFO : BUNDLE_SR_REASON_NO_KNOWN_ROUTE;
    const enum bundle_processor_signal_type signal = success ? BP_SIGNAL_BUNDLE_ROUTED : BP_SIGNAL_FORWARDING_CONTRAINDICATED;

    bundle_processor_inform(
            router_config.bundle_agent_interface->bundle_signaling_queue,
            bundle->id,
            signal,
            reason
    );
}

void router_signal_bundle_transmission(struct routed_bundle *routed_bundle, bool success) {

    LOGF("Router: bundle %d transmission status %d", routed_bundle->id, (int)success);
    if(routing_agent_is_info_bundle(routed_bundle->destination)) {
        bundle_processor_inform(
                router_config.bundle_agent_interface->bundle_signaling_queue,
                routed_bundle->id,
                success
                ? BP_SIGNAL_TRANSMISSION_SUCCESS
                : BP_SIGNAL_TRANSMISSION_FAILURE,
                BUNDLE_SR_REASON_NO_INFO
        );
    } else {

        hal_semaphore_take_blocking(router_config.router_contact_htab_sem);
        char * eid = routed_bundle->destination;

        struct router_contact *rc = htab_get(
                &router_config.router_contact_htab,
                eid
        );

        if (rc) {
            if (rc->current_bundle != NULL) {
                if (rc->current_bundle->id == routed_bundle->id) {

                    if (success) {
                        LOGF("Router: transmission success %d for contact %s", routed_bundle->id, eid);
                        // TODO: We might be able to transmit more if we have multiple bundles available
                    } else {
                        // TODO: if the transmission failed, do we even need to schedule more bundles?
                        if (rc->current_bundle->num_pending_transmissions >= 0) {
                            rc->current_bundle->num_pending_transmissions++;
                        }

                        rc->next_bundle_candidate = rc->current_bundle; // This will reset the current candidate to the very same bundle...
                        LOGF("Router: transmission failed %d for contact %s", routed_bundle->id, eid);
                    }

                    rc->current_bundle = NULL;
                    send_bundles_to_contact(rc); // try to reschedule directly
                } else {
                    LOGF("Router: error router_signal_bundle_transmission wrong bundle %d for contact %s", routed_bundle->id, eid);
                }
            } else {
                LOGF("Router: error current_bundle is null for bundle %d contact %s", routed_bundle->id, eid);
            }
        } else {
            LOGF("Router: Received bundle transmissionf for unknown contact %s", eid);
        }

        hal_semaphore_release(router_config.router_contact_htab_sem);
        // TODO: send signal if the transmission is done, i.e. routed_bundle->dest == bundle->dest
    }

    free(routed_bundle->destination);
    free(routed_bundle);
}

void router_update() {
    update_bundle_info_list();
    send_bundles();
}


void router_handle_contact_event(void *context, enum contact_manager_event event, const struct contact *contact) {

    (void)context; // currently unused
    

    // for now we only send bundles to active contacts, however we need the corresponding eid


    const char *eid = contact->node->eid;

    // we completely ignore contacts with invalid eids...

    if (IS_EID_NONE(eid)) {
        return;
    }


    // if contact is active but we do not yet know this contact -> add and initialize transmissions
    hal_semaphore_take_blocking(router_config.router_contact_htab_sem);

    struct router_contact *rc = htab_get(
            &router_config.router_contact_htab,
            eid
    );

    if (contact->active && rc == NULL) {

        if (router_config.num_router_contacts < CONFIG_BT_MAX_CONN) {

            rc = malloc(sizeof(struct router_contact));

            if (rc) {

                struct htab_entrylist *htab_entry = htab_add(
                        &router_config.router_contact_htab,
                        eid,
                        rc
                );

                if (htab_entry) {

                    rc->index = router_config.num_router_contacts;
                    rc->current_bundle = NULL;
                    rc->next_bundle_candidate = NULL;
                    rc->contact = contact;

                    router_config.router_contacts[router_config.num_router_contacts] = rc;
                    router_config.num_router_contacts++;
                    LOGF("Router: Added router contact %s", eid);
                } else {
                    free(rc);
                    LOG("Router: Error creating htab entry!");
                }
            } else {
                LOGF("Router: Could not allocate memory for routing contact for eid %s", eid);
            }
        } else {
            LOGF("Router: No place left for contact eid %s", eid);
        }
    } else if (!contact->active && rc != NULL) {
        // we remove the routing contact
        htab_remove(&router_config.router_contact_htab, eid);


        // if our contact is not the last in list, we move the last one to this position
        if (rc->index < router_config.num_router_contacts-1) {
            struct router_contact *other = router_config.router_contacts[router_config.num_router_contacts-1];
            // we swap the entries
            other->index = rc->index;
            router_config.router_contacts[other->index] = other;
        }

        router_config.router_contacts[router_config.num_router_contacts-1] = NULL;
        router_config.num_router_contacts--;

        free(rc);
        LOGF("Router: Removed routing contact %s", eid);
    }

    hal_semaphore_release(router_config.router_contact_htab_sem);
}


struct router_config router_get_config() {
    return router_config;
}


enum ud3tn_result router_update_config(struct router_config config) {
    (void)config;
    return UD3TN_OK;
}