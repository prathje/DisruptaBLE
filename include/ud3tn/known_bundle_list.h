#ifndef KNOWNBUNDLELIST_H_INCLUDED
#define KNOWNBUNDLELIST_H_INCLUDED

#include "platform/hal_semaphore.h"
#include "ud3tn/bundle.h"

// This requires manual locking before and after the loop!
#define KNOWN_BUNDLE_LIST_FOREACH(l, e) for(struct known_bundle_list_entry *(e) = (l)->head; (e) != NULL; (e) = (e)->next)

struct known_bundle_list_entry {
    struct bundle_unique_identifier unique_identifier;
    bundleid_t id;
    uint64_t deadline;
    struct known_bundle_list_entry *next;
};

/**
 * Bundles are ordered from oldest to most recent deadline
 */
struct known_bundle_list {
    struct known_bundle_list_entry *head;
    Semaphore_t sem;
};


struct known_bundle_list *known_bundle_list_create();
void known_bundle_list_destroy(struct known_bundle_list *list);


/**
 * Lock the list to e.g. loop through it, all other methods internally use this method, so there is no need to lock them
 */
void known_bundle_list_lock(struct known_bundle_list *list);

/**
 * Unlock the list to e.g. loop through it
 */
void known_bundle_list_unlock(struct known_bundle_list *list);


/**
 * Checks the oldest deadline, if the deadline is smaller than remove_before_ts, the entry will be removed from the list and returned
 * the entry needs to be freed using known_bundle_list_free_entry after processing is done!
 * returns null if no entry needs to be removed, needs to be called multiple times to remove
 */
struct known_bundle_list_entry *known_bundle_list_pop_before(struct known_bundle_list *list, uint64_t remove_before_ts);

void known_bundle_list_remove_before(struct known_bundle_list *list, uint64_t remove_before_ts);

void known_bundle_list_free_entry(struct known_bundle_list_entry* entry);

bool known_bundle_list_add(struct known_bundle_list *list, const struct bundle *bundle);
bool known_bundle_list_add_reassembled_parent(struct known_bundle_list *list, const struct bundle *bundle);

bool known_bundle_list_contains_reassembled_parent(struct known_bundle_list *list, const struct bundle *bundle);

/*
bool known_bundle_list_contains(struct known_bundle_list *list, const struct bundle *bundle);

bool known_bundle_list_contains_id(struct known_bundle_list *list, bundleid_t id);

bool known_bundle_list_remove(struct known_bundle_list *list, const struct bundle *bundle);
bool known_bundle_list_remove_bundleid(struct known_bundle_list *list, bundleid_t id);
*/

#endif