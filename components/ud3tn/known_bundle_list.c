#include <stdlib.h>
#include <stdbool.h>

#include "ud3tn/known_bundle_list.h"


static struct known_bundle_list_entry *create_entry(const struct bundle *bundle) {
    struct known_bundle_list_entry *entry = malloc(sizeof(struct known_bundle_list_entry));

    if (!entry) {
        return NULL;
    }

    entry->id = bundle->id;
    entry->unique_identifier = bundle_get_unique_identifier(bundle);
    entry->deadline = bundle_get_expiration_time_s(bundle);
    entry->next = NULL;

    return entry;
}

void known_bundle_list_free_entry(struct known_bundle_list_entry *entry) {
    bundle_free_unique_identifier(&entry->unique_identifier);
    free(entry);
}

void known_bundle_list_lock(struct known_bundle_list *list) {
    hal_semaphore_take_blocking(list->sem);
}

void known_bundle_list_unlock(struct known_bundle_list *list) {
    hal_semaphore_release(list->sem);
}

struct known_bundle_list *known_bundle_list_create() {

    Semaphore_t sem = hal_semaphore_init_binary();

    if (!sem) {
        return NULL; // TODO: This check is actually platform dependent
    }
    hal_semaphore_release(sem);

    struct known_bundle_list * list = malloc(sizeof(struct known_bundle_list));

    if (!list) {
        return NULL;
    }

    list->sem = sem;
    list->head = NULL; // empty list at the beginning!

    return list;
}
void known_bundle_list_destroy(struct known_bundle_list *list) {

    known_bundle_list_lock(list);

    struct known_bundle_list_entry *cur = list->head;
    list->head = NULL;

    // Loop through all entries and free them
    while (cur != NULL) {
        struct known_bundle_list_entry *next = cur->next;
        known_bundle_list_free_entry(cur);
        cur = next;
    }

    hal_semaphore_delete(list->sem);
    list->sem = NULL;
    free(list); // release memory of main list
}


static struct known_bundle_list_entry *pop_before_unsafe(struct known_bundle_list *list, uint64_t remove_before_ts) {
    struct known_bundle_list_entry *ret = NULL;

    struct known_bundle_list_entry *cur = list->head;
    if (cur->deadline < remove_before_ts) {

        // move list to next element
        list->head = cur->next;
        // reset next element
        cur->next = NULL;
        ret = cur;
    }
    return ret;
}


struct known_bundle_list_entry *known_bundle_list_pop_before(struct known_bundle_list *list, uint64_t remove_before_ts) {
    known_bundle_list_lock(list);
    struct known_bundle_list_entry *ret = pop_before_unsafe(list, remove_before_ts);
    known_bundle_list_unlock(list);
    return ret;
}

void known_bundle_list_remove_before(struct known_bundle_list *list, uint64_t remove_before_ts) {
    known_bundle_list_lock(list);

    struct known_bundle_list_entry *e = pop_before_unsafe(list, remove_before_ts);

    while (e != NULL) {
        known_bundle_list_free_entry(e);
        e = pop_before_unsafe(list, remove_before_ts);
    }

    known_bundle_list_unlock(list);
}


bool add_if_not_exists(struct known_bundle_list *list, const struct bundle *bundle, bool as_parent) {
    const uint64_t bundle_deadline = bundle_get_expiration_time_s(bundle);

    known_bundle_list_lock(list);

    // the reference that needs to be updated to the new element
    struct known_bundle_list_entry **ref = &list->head;

    // search for the position in the list
    struct known_bundle_list_entry *cur = list->head;

    while (cur != NULL) {
        // we do not check if for equality
        if (as_parent && bundle_is_equal_parent(bundle, &cur->unique_identifier) &&
            cur->unique_identifier.fragment_offset == 0 &&
            cur->unique_identifier.payload_length == bundle->total_adu_length
        ) {
            known_bundle_list_unlock(list);
            return true; // parent bundle already exists -> abort
        } else if (!as_parent && bundle_is_equal(bundle, &cur->unique_identifier)) {
            known_bundle_list_unlock(list);
            return true; // bundle already exists -> abort
        } else if (bundle_deadline < cur->deadline) {
            // the bundle needs to be inserted at the place of cur
            // the bundle is not part of this list
            // TODO: This assumption is only true for bundles with a creation timestamp
            break;
        }

        ref = &cur->next;
        cur = cur->next;
    }

    // element has not been found but the position was -> insert
    struct known_bundle_list_entry *entry = create_entry(bundle);

    if (entry != NULL) {
        entry->next = *ref; // use the old reference
        *ref = entry; // and update the reference to the new entry

        if (as_parent) {
            entry->unique_identifier.fragment_offset = 0;
            entry->unique_identifier.payload_length = bundle->total_adu_length;
        }
    } else {
        //TODO: handle error!
    }

    known_bundle_list_unlock(list);
    return false;
}


bool known_bundle_list_add(struct known_bundle_list *list, const struct bundle *bundle) {
    return add_if_not_exists(list, bundle, false);
}

bool known_bundle_list_add_reassembled_parent(struct known_bundle_list *list, const struct bundle *bundle) {
    return add_if_not_exists(list, bundle, true);
}

bool known_bundle_list_contains_reassembled_parent(struct known_bundle_list *list, const struct bundle *bundle) {
    known_bundle_list_lock(list);
    KNOWN_BUNDLE_LIST_FOREACH(list, entry) {
        if (
                bundle_is_equal_parent(bundle, &entry->unique_identifier) &&
                entry->unique_identifier.fragment_offset == 0 &&
                entry->unique_identifier.payload_length == bundle->total_adu_length
                ){
            known_bundle_list_unlock(list);
            return true;
        }
    }
    known_bundle_list_unlock(list);
    return false;
}

/*
bool known_bundle_list_contains(struct known_bundle_list *list, const struct bundle *bundle) {
    known_bundle_list_lock(list);
    KNOWN_BUNDLE_LIST_FOREACH(list, entry) {
        if (bundle_is_equal(bundle, &entry->unique_identifier)) {
            known_bundle_list_unlock(list);
            return true;
        }
    }
    known_bundle_list_unlock(list);
    return false;
}



bool known_bundle_list_contains_id(struct known_bundle_list *list, bundleid_t id) {
    known_bundle_list_lock(list);
    KNOWN_BUNDLE_LIST_FOREACH(list, entry) {
        if (entry->id == id) {
            known_bundle_list_unlock(list);
            return true;
        }
    }
    known_bundle_list_unlock(list);
    return false;
}

bool known_bundle_list_remove(struct known_bundle_list *list, const struct bundle *bundle) {
    const uint64_t bundle_deadline = bundle_get_expiration_time_s(bundle);

    known_bundle_list_lock(list);

    // the reference that needs to be updated to the new element
    struct known_bundle_list_entry **ref = &list->head;

    // search for the position in the list
    struct known_bundle_list_entry *cur = list->head;

    while (cur != NULL) {
        if (bundle_is_equal(bundle, &cur->unique_identifier)) {

            // current needs to be deleted -> set reference to the following element
            *ref = cur->next;

            // free cur
            known_bundle_list_free_entry(cur);
            // and we are done
            known_bundle_list_unlock(list);
            return true; // bundle already exists -> abort
        } else if (bundle_deadline < cur->deadline) {
            // the bundle is not part of this list
            // TODO: This assumption is only true for bundles with a creation timestamp
            break;
        }

        ref = &cur->next;
        cur = cur->next;
    }

    known_bundle_list_unlock(list);
    return false;
}

bool known_bundle_list_remove_bundleid(struct known_bundle_list *list, bundleid_t id) {
    known_bundle_list_lock(list);

    // the reference that needs to be updated to the new element
    struct known_bundle_list_entry **ref = &list->head;

    // search for the position in the list
    struct known_bundle_list_entry *cur = list->head;

    while (cur != NULL) {
        if (cur->id == id) {
            // current needs to be deleted -> set reference to the following element
            *ref = cur->next;

            // free cur
            known_bundle_list_free_entry(cur);

            // and we are done
            known_bundle_list_unlock(list);
            return true;
        }

        ref = &cur->next;
        cur = cur->next;
    }

    known_bundle_list_unlock(list);
    return false;
}*/