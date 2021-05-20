#include "routing/epidemic/summary_vector.h"
#include "platform/hal_crypto.h"

#include <stdlib.h>

// TODO: This format will not work in a different endianess!
struct __attribute__((__packed__)) summary_vector_entry_hashable {
    uint8_t source_hash[UD3TN_HASH_LENGTH];
    uint64_t creation_timestamp_ms;
    uint64_t sequence_number;
    uint32_t fragment_offset;
    uint32_t payload_length;
    uint8_t protocol_version; // TODO: Is this important?
};

static void summary_vector_increase_size(struct summary_vector *sv) {

    uint32_t new_capacity = sv->capacity * 2;

    struct summary_vector_entry *new_entries = malloc(new_capacity * sizeof(struct summary_vector_entry));

    if (new_entries == NULL) {
        return; // we do not change anything
    }

    // copy all existing entries
    memcpy(new_entries, sv->entries, sv->length*sizeof(struct summary_vector_entry));
    free(sv->entries); // free old entries

    sv->capacity = new_capacity; // save new capacity
    sv->entries = new_entries; // use the new entries
}

struct summary_vector *summary_vector_create_with_capacity(uint32_t capacity) {
    struct summary_vector *sv = malloc(sizeof(struct summary_vector));

    if (sv == NULL) {
        return NULL;
    }

    sv->length = 0;
    sv->capacity = capacity;

    sv->entries = malloc(sv->capacity * sizeof(struct summary_vector_entry));

    if (!sv->entries) {
        free(sv);
        return NULL;
    }

    return sv;
}

struct summary_vector *summary_vector_create() {
    return summary_vector_create_with_capacity(SUMMARY_VECTOR_DEFAULT_CAPACITY);
}

struct summary_vector *summary_vector_create_from_memory(const void *src, size_t num_bytes) {

    if (num_bytes % sizeof(struct summary_vector_entry) != 0) {
        return NULL;
    }

    uint32_t capacity = num_bytes / sizeof(struct summary_vector_entry);

    struct summary_vector *sv = summary_vector_create_with_capacity(capacity);

    if (sv == NULL) {
        return NULL;
    }

    sv->length = capacity;

    memcpy(sv->entries, src, num_bytes);

    return sv;
}


size_t summary_vector_memory_size(struct summary_vector *sv) {

    return sv->length * sizeof(struct summary_vector_entry);
}


void summary_vector_copy_to_memory(struct summary_vector *sv, void *dest) {
    size_t num_bytes = summary_vector_memory_size(sv);
    memcpy(dest, sv->entries, num_bytes);
}

void summary_vector_destroy(struct summary_vector *sv) {

    free(sv->entries);
    sv->entries = NULL;
    sv->length = 0;

    free(sv);
}


bool summary_vector_entry_equal(struct summary_vector_entry *a, struct summary_vector_entry *b) {
    return memcmp(a->hash, b->hash, SUMMARY_VECTOR_ENTRY_HASH_LENGTH) == 0;
}

void summary_vector_entry_from_bundle_unique_identifier(struct summary_vector_entry *dest,
                                                        struct bundle_unique_identifier *id) {

    struct summary_vector_entry_hashable hashable;
    hashable.creation_timestamp_ms = id->creation_timestamp_ms;
    hashable.sequence_number = id->sequence_number;
    hashable.fragment_offset = id->fragment_offset;
    hashable.payload_length = id->payload_length;
    hashable.protocol_version = id->protocol_version;

    // we now hash the source address
    char *source = id->source ? id->source : EID_NONE;
    hal_hash(source, strlen(source), hashable.source_hash);

    uint8_t hash_result[UD3TN_HASH_LENGTH];
    hal_hash((uint8_t *)&hashable, sizeof(struct summary_vector_entry_hashable), hash_result);

    memcpy(dest->hash, hash_result, SUMMARY_VECTOR_ENTRY_HASH_LENGTH);
}

void summary_vector_entry_from_bundle(struct summary_vector_entry *dest, struct bundle *bundle) {
    struct bundle_unique_identifier id = bundle_get_unique_identifier(bundle);
    summary_vector_entry_from_bundle_unique_identifier(dest, &id);
    bundle_free_unique_identifier(&id);
}

bool summary_vector_contains_entry(struct summary_vector *sv, struct summary_vector_entry *entry) {

    // TODO: Do not loop through all entries, build a hashmap or bloom filter instead?
    for (int i = 0; i < sv->length; i++) {
        if (summary_vector_entry_equal(entry, &sv->entries[i])) {
            return true;
        }
    }

    return false;
}

bool summary_vector_contains_bundle_unique_identifier(struct summary_vector *sv, struct bundle_unique_identifier *uid) {
    struct summary_vector_entry entry;
    summary_vector_entry_from_bundle_unique_identifier(&entry, uid);
    return summary_vector_contains_entry(sv, &entry);
}


enum ud3tn_result summary_vector_add_entry_by_copy(struct summary_vector *sv, struct summary_vector_entry *entry) {
    if (sv->entries == NULL) {
        return UD3TN_FAIL;
    }

    if (sv->length == sv->capacity) {
        summary_vector_increase_size(sv);
        if (sv->length == sv->capacity) {
            // we could not increase size!
            return UD3TN_FAIL;
        }
    }
    memcpy(&sv->entries[sv->length], entry, sizeof(struct summary_vector_entry));
    sv->length++;
    return UD3TN_OK;
}

// TODO: This is very inefficient (just as the other methods...)
struct summary_vector *summary_vector_create_diff(struct summary_vector *a, struct summary_vector *b) {

    // TODO: we might want to initialize the capacity?
    struct summary_vector *diff = summary_vector_create();

    if (!diff) {
        return NULL;
    }

    for(uint32_t i = 0; i < a->length; i++) {
        struct summary_vector_entry *entry = &a->entries[i];
        if (!summary_vector_contains_entry(b, entry)) {
            if (summary_vector_add_entry_by_copy(diff, entry) != UD3TN_OK) {
                free(diff);
                return NULL;
            }
        }
    }

    return diff;
}