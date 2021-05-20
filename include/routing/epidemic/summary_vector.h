#ifndef SUMMARYVECTOR_H_INCLUDED
#define SUMMARYVECTOR_H_INCLUDED
#include "ud3tn/known_bundle_list.h"
#include "ud3tn/node.h"
#include <stdbool.h>
#include "platform/hal_io.h"

// TODO: This hash length determines the probability that a message is wrongfully marked as "delivered"
// The current 64 bits should be enough as bundles tend to expire eventually
// TODO: A bloom filter would greatly increase space efficiency
// if changed, please update function summary_vector_entry_print
#define SUMMARY_VECTOR_ENTRY_HASH_LENGTH 8

// this is 64 bytes just for 8
#define SUMMARY_VECTOR_DEFAULT_CAPACITY 8

// 8 bytes for each summary vector entry (that is quite big!)
struct __attribute__((__packed__)) summary_vector_entry {
    uint8_t hash[SUMMARY_VECTOR_ENTRY_HASH_LENGTH];
};

struct summary_vector {
    uint32_t length; // the number of filled entries
    uint32_t capacity; // the maximum capacity of filled entries
    struct summary_vector_entry *entries;
};



bool summary_vector_entry_equal(struct summary_vector_entry *a, struct summary_vector_entry *b);

void summary_vector_entry_from_bundle_unique_identifier(struct summary_vector_entry *dest, struct bundle_unique_identifier *uid);
void summary_vector_entry_from_bundle(struct summary_vector_entry *dest, struct bundle *bundle);


struct summary_vector* summary_vector_create();
struct summary_vector* summary_vector_create_with_capacity(uint32_t capacity);
void summary_vector_destroy(struct summary_vector* sv);

/**
 * entry is not freed!
 */
enum ud3tn_result summary_vector_add_entry_by_copy(struct summary_vector *sv, struct summary_vector_entry *entry);

/**
 * Some memory handling
 */
struct summary_vector* summary_vector_create_from_memory(const void *src, size_t num_bytes);

size_t summary_vector_memory_size(struct summary_vector* sv);
void summary_vector_copy_to_memory(struct summary_vector* sv, void *dest);

bool summary_vector_contains_bundle_unique_identifier(struct summary_vector *sv, struct bundle_unique_identifier *uid);
bool summary_vector_contains_entry(struct summary_vector *sv, struct summary_vector_entry *entry);

struct summary_vector *summary_vector_create_diff(struct summary_vector *a, struct summary_vector *b);



// TODO: THis currently depends on the SUMMARY_VECTOR_ENTRY_HASH_LENGTH
static inline void summary_vector_entry_print(const char *msg, struct summary_vector_entry *entry)  {
    LOGF("%s%x%x%x%x%x%x%x%x",
         msg,
         hash[0],
         hash[1],
         hash[2],
         hash[3],
         hash[4],
         hash[5],
         hash[6],
         hash[7]);
};

static inline void summary_vector_print_bundle_identifier(const char *msg,struct bundle_unique_identifier *uid)  {
    struct summary_vector_entry entry;
    summary_vector_entry_from_bundle_unique_identifier(&entry, uid);
    summary_vector_entry_print(msg, &entry);
};

static inline void summary_vector_print_bundle(const char *msg, struct bundle *bundle)  {
    struct summary_vector_entry entry;
    summary_vector_entry_from_bundle(&entry, bundle);
    summary_vector_entry_print(msg, &entry);
};


static inline void summary_vector_print(const char *msg, struct summary_vector *sv)  {
    LOGF("========== %s(%p with %d elements)", msg, sv, sv->length);
    for(int i = 0; i < sv->length; i++) {
        summary_vector_entry_print(""; &v->entries[i]);
    }
    LOGF("========== End summary of vector %p ", sv);
};

#endif //SUMMARYVECTOR_H_INCLUDED