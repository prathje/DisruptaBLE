#ifndef NB_BLE_INCLUDE_H
#define NB_BLE_INCLUDE_H

#include <bluetooth/addr.h>

#include "ud3tn/node.h"
#include "ud3tn/result.h"

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
};

/*
 * INITS advertisements. The discovery will be launched immediately
 */
enum ud3tn_result nb_ble_init(const struct nb_ble_config * const config);

/**
 * Resume the neighbor discovery (NOOP if already running).
 */
void nb_ble_start(bool connectable);

/**
 * Pause the neighbor discovery (NOOP if already paused)
 */
void nb_ble_stop();



char* bt_addr_le_to_mac_addr(const bt_addr_le_t *addr);
int bt_addr_le_from_mac_addr(const char *str, bt_addr_le_t *addr);

#endif