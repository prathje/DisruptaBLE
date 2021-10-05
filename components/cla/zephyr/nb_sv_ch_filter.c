#include "cla/zephyr/nb_sv_ch_filter.h"


#ifndef CONFIG_NB_SV_FILTER_SIZE
#define CONFIG_NB_SV_FILTER_SIZE 0
#endif


#if CONFIG_NB_SV_FILTER_SIZE > 0

#define NB_SV_FILTER_DEBUG 0

Semaphore_t nb_sv_filter_sem;
struct summary_vector_characteristic nb_sv_filter_characteristics[CONFIG_NB_SV_FILTER_SIZE];
uint32_t nb_sv_filter_next_index;


void nb_sv_ch_filter_init() {
    nb_sv_filter_sem = hal_semaphore_init_binary();

    nb_sv_filter_next_index = 0;

    for(int i = 0; i < CONFIG_NB_SV_FILTER_SIZE; i++) {
        summary_vector_characteristic_init(&nb_sv_filter_characteristics[i]);
    }

    hal_semaphore_release(nb_sv_filter_sem);
}

void print_sv_ch(struct summary_vector_characteristic *sv_ch) {
    LOG("sv_ch print");
    for(size_t i = 0; i < sizeof (sv_ch); i++) {
        printk("%02hhx", ((char *)sv_ch)[i]);
    }
    printk("\n");
}

void print_list() {
    LOG("sv_ch print list");
    for(int k = 0; k < CONFIG_NB_SV_FILTER_SIZE; k++) {
        struct summary_vector_characteristic *sv_ch = &nb_sv_filter_characteristics[k];
        for(size_t i = 0; i < sizeof (sv_ch); i++) {
            printk("%02hhx", ((char *)sv_ch)[i]);
        }
        printk("\n");
    }
}

void filter_add(struct summary_vector_characteristic *sv_ch) {
    memcpy(&nb_sv_filter_characteristics[nb_sv_filter_next_index], sv_ch, sizeof(nb_sv_filter_characteristics[nb_sv_filter_next_index]));
    nb_sv_filter_next_index = (nb_sv_filter_next_index+1) % CONFIG_NB_SV_FILTER_SIZE;
}

bool filter_contains(struct summary_vector_characteristic *sv_ch) {
    bool res = false;
    for(int i = 0; i < CONFIG_NB_SV_FILTER_SIZE; i++) {
        if (summary_vector_characteristic_equals(sv_ch, &nb_sv_filter_characteristics[i])) {
            res = true;
            break;
        }
    }
    return res;
}

void nb_sv_ch_filter_add(struct summary_vector_characteristic *sv_ch) {
    #if NB_SV_FILTER_DEBUG
    LOG("Filter: Adding sv_ch");
    print_sv_ch(sv_ch);
    #endif

    hal_semaphore_take_blocking(nb_sv_filter_sem);
    if (!filter_contains(sv_ch)) {
        filter_add(sv_ch);
    }
    hal_semaphore_release(nb_sv_filter_sem);
    #if NB_SV_FILTER_DEBUG
    print_list();
    #endif
}

bool nb_sv_ch_filter_contains(struct summary_vector_characteristic *sv_ch) {
    hal_semaphore_take_blocking(nb_sv_filter_sem);
    bool res = filter_contains(sv_ch);
    hal_semaphore_release(nb_sv_filter_sem);
    #if NB_SV_FILTER_DEBUG
    LOGF("Filter: Checked sv_ch contains: %d", res);
    print_list();
    #endif

    return res;
}

#else
// just use dummy methods

void nb_sv_ch_filter_init() {}
void nb_sv_ch_filter_add(struct summary_vector_characteristic *sv_ch) {}
bool nb_sv_ch_filter_contains(struct summary_vector_characteristic *sv_ch) {
    return false;
}

#endif
