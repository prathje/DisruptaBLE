#ifndef NB_BLE_INCLUDE_H
#define NB_BLE_INCLUDE_H

#include <bluetooth/addr.h>

#include "ud3tn/node.h"
#include "ud3tn/result.h"

#include "platform/hal_semaphore.h"

struct nb_ble_node_info {
    char *eid;
    char *mac_addr;
};

/**
 * Callback is invoked everytime a node was discovered.
 * node_info is automatically freed afterward
 */
typedef void (*nb_ble_discovered_cb)(void * context, const struct nb_ble_node_info * const ble_node_info, bool connectable);

struct nb_ble_config {
    nb_ble_discovered_cb discover_cb;
    void * discover_cb_context;
    char *eid;
    Semaphore_t sem;
    bool enabled;
    uint64_t scanner_enabled_ms;
    bool advertising_as_connectable;
    Task_t task;
};

/*
 * INIT advertisements. The discovery will be launched immediately
 */
enum ud3tn_result nb_ble_init(const struct nb_ble_config * const config);

void nb_ble_enable();
void nb_ble_disable_and_stop();
void nb_ble_set_connectable(bool connectable);

void nb_ble_stop();
void nb_ble_start_if_enabled();


char* bt_addr_le_to_mac_addr(const bt_addr_le_t *addr);
int bt_addr_le_from_mac_addr(const char *str, bt_addr_le_t *addr);

#endif