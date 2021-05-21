
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

bool bundle_should_be_offered(struct router_contact *rc, struct bundle_info_list_entry *candidate) {
    uint64_t cur_time = hal_time_get_timestamp_s();

    if (candidate->num_pending_transmissions == 0) {
        LOG("candidate->num_pending_transmissions == 0");
        // TODO: Shall we do direct delivery in case the bundle destination is actually this contact? -> hash the eid of the contact and the destination of bundles!
        return false;
    }

    if (candidate->exp_time < cur_time) {
        return false; // bundle is sadly expired -> will be removed eventually
    }
    return true;
}

/**
 * This sv contains all bundles that our router has to offer for the contact, used by the router agent
 * @return pointer to summary_vector if successfull, null otherwise
 */
static struct summary_vector *create_offer_sv(struct router_contact *rc) {

    struct summary_vector *offer_sv = summary_vector_create();

    if (offer_sv) {
        struct bundle_info_list_entry *current = router_config.bundle_info_list.head;
        while(current != NULL) {
            if (bundle_should_be_offered(rc, current)) {
                if (summary_vector_add_entry_by_copy(offer_sv, &current->sv_entry) != UD3TN_OK) {
                    LOGF("Router: Failed to create offer sv for eid %s", rc->contact->node->eid);
                    summary_vector_destroy(offer_sv);
                    offer_sv = NULL;
                    break;
                }
            }
            current = current->next;
        }
    }
    return offer_sv;
}


static void send_offer_sv(struct router_contact *rc) {
    struct summary_vector *offer_sv = create_offer_sv(rc);

    if (offer_sv) {
        routing_agent_send_offer_sv(rc->contact->node->eid, offer_sv);
        summary_vector_destroy(offer_sv);
    } else {
        LOGF("Router: Could not create offer sv for %s", rc->contact->node->eid);
    }
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
                //LOGF("update_bundle_info_list urrent == router_config.bundle_info_list.hea List head %p", router_config.bundle_info_list.head);
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

            summary_vector_entry_print("Router: Deleting Bundle ", &current->sv_entry);

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

    // we need to wait to know the request summary vector
    if (router_contact->request_sv != NULL) {
        if (router_contact->current_bundle == NULL) {

            // we need a new transmission!
            struct bundle_info_list_entry *candidate = router_contact->next_bundle_candidate;

            while(candidate != NULL) {
                //LOGF("C %d, %d", bundle_should_be_offered(router_contact, candidate), summary_vector_contains_entry(router_contact->request_sv, &candidate->sv_entry));

                if (bundle_should_be_offered(router_contact, candidate)
                    && summary_vector_contains_entry(router_contact->request_sv, &candidate->sv_entry)) {

                    break; // we found a possible candidate! -> keep the candidate for now!
                } else {
                    // try the next entry!
                    candidate = candidate->next;
                }
            }

            // we found a good candidate!
            if (candidate != NULL) {
                // next candidate is the following bundle, ignoring the success of transmisions (for now)
                router_contact->next_bundle_candidate = candidate->next;

                //summary_vector_entry_print("Router: CANDIDATE!!!!!! ", &candidate->sv_entry);

                // we try to schedule it
                if (try_to_send_bundle(eid, candidate) == UD3TN_OK) {

                    if (candidate->num_pending_transmissions > 0) {
                        candidate->num_pending_transmissions--;
                    }

                    // we could schedule the send process! this means that we get a transmission success / fail in all cases (even in case of a connection failure)
                    // we therefore set the curret bundle and further increment to the next_bundle_candidate (which could be null (!))
                    router_contact->current_bundle = candidate;
                } else {
                    summary_vector_entry_print("Router: Failed to send_bundle ", &candidate->sv_entry);
                }
            } else {
                //LOG("Router: NO CANDIDATE!!!!!!");
                router_contact->next_bundle_candidate = NULL;
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


bool route_epidemic_bundle(struct bundle *bundle) {

    summary_vector_print_bundle("Router: Routing Epidemic Bundle ", bundle);

    struct bundle_info_list_entry *info = malloc(sizeof(struct bundle_info_list_entry));

    if (!info) {
        return false;
    }

    summary_vector_entry_from_bundle(&info->sv_entry, bundle);

    // we now check if this entry is already present in our list
    struct bundle_info_list_entry *current = router_config.bundle_info_list.head;
    while (current != NULL) {
        if (summary_vector_entry_equal(&info->sv_entry, &current->sv_entry)) {
            summary_vector_entry_print("Router: Dropping duplicate bundle ", &info->sv_entry);

            // oh yes, that's a match...
            free(info);
            return false;
        }
        current = current->next;
    }

    info->id = bundle->id;

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

    // we now add this bundle to every currently known contact that has no other candidates
    for(int i = router_config.num_router_contacts-1; i >= 0; i--) {
        struct router_contact *rc = router_config.router_contacts[i];
        if (rc->current_bundle == NULL && rc->next_bundle_candidate == NULL) {
            // OOOPS! It seems like we don't have any bundles to send for this contact -> let's offer some :)
            // TODO: We are currently sending our whole offer sv everytime, we might want to sent individual entries ;)
            send_offer_sv(rc);
        }
    }
    return true; //routing is otherwise always successfull!
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
    hal_semaphore_take_blocking(router_config.router_contact_htab_sem);

    LOGF("Router: Routing info bundle %d to %s", bundle->id, bundle->destination);

    bool success = false;
    if(routing_agent_is_info_bundle(bundle->destination)) {
        success = route_info_bundle(bundle);
    } else {
        success = route_epidemic_bundle(bundle);
    }

    const enum bundle_status_report_reason reason = success ? BUNDLE_SR_REASON_NO_INFO : BUNDLE_SR_REASON_NO_KNOWN_ROUTE;
    const enum bundle_processor_signal_type signal = success ? BP_SIGNAL_BUNDLE_ROUTED : BP_SIGNAL_FORWARDING_CONTRAINDICATED;

    bundle_processor_inform(
            router_config.bundle_agent_interface->bundle_signaling_queue,
            bundle->id,
            signal,
            reason
    );

    hal_semaphore_release(router_config.router_contact_htab_sem);
}

void router_signal_bundle_transmission(struct routed_bundle *routed_bundle, bool success) {

    if(routing_agent_is_info_bundle(routed_bundle->destination)) {
        LOGF("Router: info bundle %d transmission status %d", routed_bundle->id, (int)success);
        bundle_processor_inform(
                router_config.bundle_agent_interface->bundle_signaling_queue,
                routed_bundle->id,
                success
                ? BP_SIGNAL_TRANSMISSION_SUCCESS
                : BP_SIGNAL_TRANSMISSION_FAILURE,
                BUNDLE_SR_REASON_NO_INFO
        );
    } else {

        LOGF("Router: epidemic bundle %d transmission status %d", routed_bundle->id, (int)success);

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
                        summary_vector_entry_print("Router: transmission success for bundle ", &rc->current_bundle->sv_entry);
                        // TODO: We might be able to transmit more if we have multiple bundles available
                    } else {
                        // we increase the transmissions at this point so we already limit transmissions
                        if (rc->current_bundle->num_pending_transmissions >= 0) {
                            rc->current_bundle->num_pending_transmissions++;
                        }
                        LOGF("Router: transmission failed %d for contact %s", routed_bundle->id, eid);
                    }

                    rc->current_bundle = NULL; // signals that we are done with transmission
                    send_bundles_to_contact(rc); // try to reschedule directly

                    if (rc->current_bundle == NULL && rc->next_bundle_candidate == NULL) {
                        // OOOPS! It seems like we don't have any bundles to send for this contact -> let's offer some :)
                        // TODO: We are currently sending our whole offer sv everytime, we might want to sent individual entries ;)
                        // TODO: We might have scheduled two offers as soon as another bundle is available
                        //       But the other offer would be more up-to-date anyway
                        send_offer_sv(rc);
                    }
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
    //struct summary_vector *known_sv = router_create_known_sv();
    //LOG("ROUTER_UPDATE");
    //summary_vector_print(known_sv);

    hal_semaphore_take_blocking(router_config.router_contact_htab_sem);
    update_bundle_info_list();

    /*LOGF("==== Router: Summary of contacts start (%d)", router_config.num_router_contacts);
    for(int i = router_config.num_router_contacts-1; i >= 0; i--) {
        LOGF("%s  %s", router_config.router_contacts[i]->contact->node->eid, router_config.router_contacts[i]->contact->node->cla_addr);
    }
    LOG("==== Router: Summary of contacts end");*/

    //send_bundles();
    hal_semaphore_release(router_config.router_contact_htab_sem);
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

            if (rc != NULL) {

                struct htab_entrylist *htab_entry = htab_add(
                        &router_config.router_contact_htab,
                        eid,
                        rc
                );

                if (htab_entry) {

                    rc->index = router_config.num_router_contacts;
                    rc->current_bundle = NULL;
                    rc->next_bundle_candidate = NULL;
                    rc->request_sv = NULL;
                    rc->contact = contact;

                    router_config.router_contacts[router_config.num_router_contacts] = rc;
                    router_config.num_router_contacts++;
                    LOGF("Router: Added router contact %s", eid);

                    send_offer_sv(rc); // we directly offer our "bundles"
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


        // destroy other resources
        if (rc->request_sv) {
            summary_vector_destroy(rc->request_sv);
            rc->request_sv = NULL;
        }

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

void router_update_request_sv(const char* eid, struct summary_vector *request_sv) {
    hal_semaphore_take_blocking(router_config.router_contact_htab_sem);

    //summary_vector_print("router_update_request_sv ", request_sv);

    struct router_contact *rc = htab_get(
            &router_config.router_contact_htab,
            eid
    );

    if (rc) {
        // destroy current summary_vector!
        if (rc->request_sv) {
            summary_vector_destroy(rc->request_sv);
        }

        rc->request_sv = request_sv;

        // as we updated the requested sv, we schedule all bundles again
        rc->next_bundle_candidate = router_config.bundle_info_list.head;

        if (rc->current_bundle == NULL) {
            // reschedule directly
            send_bundles_to_contact(rc);
        }
    } else {
        summary_vector_destroy(request_sv);
        LOGF("Router: Could not update request_sv for %s", eid);
    }

    hal_semaphore_release(router_config.router_contact_htab_sem);
}


struct summary_vector *router_create_known_sv() {
    hal_semaphore_take_blocking(router_config.router_contact_htab_sem);

    struct summary_vector *known_sv = summary_vector_create();

    if (known_sv) {
        struct bundle_info_list_entry *current = router_config.bundle_info_list.head;

        while (current != NULL) {
            if (summary_vector_add_entry_by_copy(known_sv, &current->sv_entry) != UD3TN_OK) {
                free(known_sv);
                break;
            }
            current = current->next;
        }
    }

    hal_semaphore_release(router_config.router_contact_htab_sem);

    return known_sv;
}
