#include "cla/zephyr/nb_ble.h"


#include "ud3tn/common.h"
#include "ud3tn/config.h"
#include "ud3tn/task_tags.h"

#include "platform/hal_config.h"
#include "platform/hal_io.h"
#include "platform/hal_random.h"
#include "platform/hal_queue.h"
#include "platform/hal_semaphore.h"
#include "platform/hal_task.h"
#include "platform/hal_types.h"

#include <bluetooth/bluetooth.h>
#include <bluetooth/l2cap.h>
#include <bluetooth/conn.h>
#include <bluetooth/uuid.h>
#include <net/buf.h>
#include <stdlib.h>

// TODO: Make this configurable?
#define NB_BLE_UUID 0xFFFF

#ifndef CONFIG_NB_BLE_QUEUE_SIZE
#define CONFIG_NB_BLE_QUEUE_SIZE 10
#endif

#ifndef CONFIG_NB_BLE_DEBUG
#define CONFIG_NB_BLE_DEBUG 0
#endif

// TODO: Not the best to define them statically...
static struct nb_ble_config nb_ble_config;


static void device_found_cb(const bt_addr_le_t *addr, int8_t rssi, uint8_t adv_type,
                            struct net_buf_simple *ad) {

    /* filter devices with too poor quality */

    char dev[BT_ADDR_LE_STR_LEN];

    bt_addr_le_to_str(addr, dev, sizeof(dev));

    if (adv_type == BT_GAP_ADV_TYPE_ADV_IND ||
        adv_type == BT_GAP_ADV_TYPE_ADV_DIRECT_IND ||
        adv_type == BT_GAP_ADV_TYPE_ADV_SCAN_IND ||
        adv_type == BT_GAP_ADV_TYPE_ADV_NONCONN_IND
            ) {

        // TODO: This is not standard-conform advertisement parsing!
        if (ad->len >= 7) {
            /*uint8_t _flags_len = */ net_buf_simple_pull_u8(ad);
            /*uint8_t _flags_type = */ net_buf_simple_pull_u8(ad);
            /*uint8_t _flags = */ net_buf_simple_pull_u8(ad);
            uint8_t entry_len = net_buf_simple_pull_u8(ad);
            uint8_t type = net_buf_simple_pull_u8(ad);


            if (type == BT_DATA_SVC_DATA16 && entry_len >= 4) {

                uint8_t uuid_low = net_buf_simple_pull_u8(ad);
                uint8_t uuid_high = net_buf_simple_pull_u8(ad);

                if (((uuid_high<<8)|uuid_low) == NB_BLE_UUID) {

                    size_t eid_len = entry_len-3;
                    void *eid_buf = net_buf_simple_pull_mem(ad, eid_len);

                    // This will be freed later!
                    char *eid = malloc(eid_len+1);
                    memcpy(eid, eid_buf, eid_len);
                    eid[eid_len] = '\0';

                    struct nb_ble_node_info node_info = {
                            .eid = eid,
                            .mac_addr = bt_addr_le_to_mac_addr(addr)
                    };

                    bool connectable = adv_type == BT_GAP_ADV_TYPE_ADV_IND || adv_type == BT_GAP_ADV_TYPE_ADV_DIRECT_IND;
                    LOG_EV("adv_received", "\"other_mac_addr\": \"%s\", \"rssi\": %d, \"other_eid\": \"%s\", \"connectable\": %d",
                           node_info.mac_addr, rssi, eid, connectable);

                    if (rssi >= CONFIG_NB_BLE_MIN_RSSI) {
                        nb_ble_config.discover_cb(nb_ble_config.discover_cb_context, &node_info, connectable);
                    }

                    free((void*)node_info.eid);
                    free((void*)node_info.mac_addr);
                }
            }
        }
    } else {
    }
}


static void scan_start() {
    if (nb_ble_config.scanner_is_enabled) {
        return; // no need to start again
    }

    struct bt_le_scan_param scan_param = {
            .type       = BT_LE_SCAN_TYPE_PASSIVE,
            .options    = BT_LE_ADV_OPT_ONE_TIME,
            .interval   = 0x0010,    // TODO: Adapt interval and window
            .window     = 0x0010,
    };

    int err = bt_le_scan_start(&scan_param, device_found_cb);


    if(!err) {
        nb_ble_config.scanner_is_enabled = true;
    }

#if CONFIG_NB_BLE_DEBUG
    if (err) {
            LOGF("NB BLE: Scanning failed to start (err %d)\n", err);
    }
#endif
}

static void scan_stop() {
    int err = bt_le_scan_stop();

    if (!err) {
        //LOG_EV_NO_DATA("scan_stopped");
    }

    #if CONFIG_NB_BLE_DEBUG
        if (err) {
                    LOGF("NB BLE: Scanning failed to stop (err %d)\n", err);
                }
    #endif
    nb_ble_config.scanner_is_enabled = false;
}

static void adv_start() {

    size_t data_len = strlen(nb_ble_config.eid) + 2; // 2 byte uuid
    char *data = malloc(data_len);

    // Store the UUID in little endian format
    *data = NB_BLE_UUID & 0xFF;
    *(data + 1) = (NB_BLE_UUID >> 8) & 0xFF;
    memcpy(data + 2, nb_ble_config.eid, data_len - 2);  // this copies the data without the null terminator


   struct bt_data ad[] = {
            BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
            BT_DATA(BT_DATA_SVC_DATA16, data, data_len)
    };

   int err =  bt_le_adv_start(
         BT_LE_ADV_PARAM(
                 (nb_ble_config.advertising_as_connectable ? (BT_LE_ADV_OPT_CONNECTABLE | BT_LE_ADV_OPT_ONE_TIME) : BT_LE_ADV_OPT_NONE)
                 | BT_LE_ADV_OPT_USE_IDENTITY,
                 BT_GAP_ADV_SLOW_INT_MIN,
                 BT_GAP_ADV_SLOW_INT_MAX,
                 NULL),
         ad,
         ARRAY_SIZE(ad), NULL, 0);


    if (err) {
#if CONFIG_NB_BLE_DEBUG
        LOGF("NB BLE: advertising failed to start (err %d)\n", err);
#endif
    }

    free(data);
}

static void adv_stop() {
    int err = bt_le_adv_stop();

#if CONFIG_NB_BLE_DEBUG
    if (err) {
        LOGF("NB BLE: advertising failed to stop (err %d)\n", err);
    }
#endif
}


void nb_ble_set_connectable(bool connectable) {

    if (!nb_ble_config.enabled) {
        nb_ble_config.advertising_as_connectable = connectable; // we save this so we start correctly if we get enabled at some point
        return; // directly return since not enabled right now, no need to take the lock
    }

    hal_semaphore_take_blocking(nb_ble_config.sem);

    // if this does not match the wanted connectable state, we might need to stop current advertisements before
    if (nb_ble_config.advertising_as_connectable != connectable) {
        nb_ble_config.advertising_as_connectable = connectable;
        adv_stop();
        scan_stop();
        // advertisements will be restarted by the management task
    }
    hal_semaphore_release(nb_ble_config.sem);
}

void nb_ble_enable() {
    if (nb_ble_config.enabled) {
        return; // no need to lock it
    }

    hal_semaphore_take_blocking(nb_ble_config.sem);
    nb_ble_config.enabled = true;   // TODO: does locking make a difference here at all?
    hal_semaphore_release(nb_ble_config.sem);
}

/*
void nb_ble_stop() {
    hal_semaphore_take_blocking(nb_ble_config.sem);
    nb_ble_stop_unsafe();
    hal_semaphore_release(nb_ble_config.sem);
}
*/

void nb_ble_disable_and_stop() {
    hal_semaphore_take_blocking(nb_ble_config.sem);
    nb_ble_config.enabled = false;
    adv_stop();
    scan_stop();
    hal_semaphore_release(nb_ble_config.sem);
}



static void nb_ble_management_task(void *param) {
    (void)param; // unused

    while (true) {
        hal_semaphore_take_blocking(nb_ble_config.sem);
        if (nb_ble_config.enabled) {
            scan_start();
            adv_start();
        }
        hal_semaphore_release(nb_ble_config.sem);
        hal_task_delay(50);
    }
}

/*
 * Launches a new task to handle BLE advertisements
 */
enum ud3tn_result nb_ble_init(const struct nb_ble_config * const config) {

    if(config->discover_cb == NULL) {
        return UD3TN_FAIL;
    }

    if(config->eid == NULL) {
        return UD3TN_FAIL;
    }

    memcpy(&nb_ble_config, config, sizeof(struct nb_ble_config));

    nb_ble_config.eid = strdup(config->eid);
    nb_ble_config.sem = hal_semaphore_init_binary();
    hal_semaphore_release(nb_ble_config.sem);

    nb_ble_config.enabled = true; // enabled right from the start
    nb_ble_config.advertising_as_connectable = false; // enabled right from the start
    nb_ble_config.scanner_is_enabled = false; // enabled right from the start

    nb_ble_config.task = hal_task_create(
            nb_ble_management_task,
            "nb_ble_mgmt_t",
            CONTACT_LISTEN_TASK_PRIORITY, // TODO
            &nb_ble_config,
            CONTACT_LISTEN_TASK_STACK_SIZE, // TODO
            (void *) CLA_SPECIFIC_TASK_TAG
    );

    if (!nb_ble_config.task)
        return UD3TN_FAIL;

    return UD3TN_OK;
}

/**
 * Format is "ED-71-8F-C2-E4-6E.random" while the zephyr format is "ED:71:8F:C2:E4:6E (random)"
 * Returns new string which needs to be freed afterward
 */
char* bt_addr_le_to_mac_addr(const bt_addr_le_t *addr) {

    ASSERT(addr);
    char type[10];

    switch (addr->type) {
        case BT_ADDR_LE_PUBLIC:
            strcpy(type, "public");
            break;
        case BT_ADDR_LE_RANDOM:
            strcpy(type, "random");
            break;
        case BT_ADDR_LE_PUBLIC_ID:
            strcpy(type, "public-id");
            break;
        case BT_ADDR_LE_RANDOM_ID:
            strcpy(type, "random-id");
            break;
        default:
            snprintk(type, sizeof(type), "0x%02x", addr->type);
            break;
    }

    char buf[BT_ADDR_LE_STR_LEN+1];
    snprintk(buf, BT_ADDR_LE_STR_LEN, "%02X-%02X-%02X-%02X-%02X-%02X.%s",
                    addr->a.val[5], addr->a.val[4], addr->a.val[3],
                    addr->a.val[2], addr->a.val[1], addr->a.val[0], type);

    buf[BT_ADDR_LE_STR_LEN] = '\0';
    return strdup(buf);
}

/**
 * We split "ED-71-8F-C2-E4-6E.random" -> into "ED-71-8F-C2-E4-6E" and "random"
 * @return Zero on success or (negative) error code otherwise.
 */
int bt_addr_le_from_mac_addr(const char *str, bt_addr_le_t *addr) {

    ASSERT(addr);
    ASSERT(str);
    ASSERT(strlen(str) > 18);

    char buf[BT_ADDR_LE_STR_LEN+1];
    strncpy(buf, str, BT_ADDR_LE_STR_LEN);
    buf[BT_ADDR_LE_STR_LEN] = '\0';

    // split the string
    buf[17] = '\0';
    char *mac = &buf[0];
    char *type = &buf[18];

    for(size_t i = 0; i < 17; i++) {
        char a = buf[i];
        if (a == '-') {
            buf[i] = ':';
        }
    }

    return bt_addr_le_from_str(mac, type, addr);
}