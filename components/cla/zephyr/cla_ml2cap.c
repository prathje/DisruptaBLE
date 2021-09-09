
#include "cla/zephyr/cla_ml2cap.h"

#include "cla/mtcp_proto.h"
#include "cla/zephyr/cla_ml2cap.h"

#include "platform/hal_config.h"
#include "platform/hal_io.h"
#include "platform/hal_queue.h"
#include "platform/hal_semaphore.h"
#include "platform/hal_task.h"
#include "platform/hal_types.h"

#include "ud3tn/bundle_agent_interface.h"
#include "ud3tn/common.h"
#include "ud3tn/config.h"
#include "ud3tn/task_tags.h"
#include "ud3tn/node.h"

#include "routing/router_task.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <bluetooth/bluetooth.h>
#include <bluetooth/l2cap.h>
#include <bluetooth/conn.h>
#include <bluetooth/uuid.h>
#include <bluetooth/addr.h>
#include <net/buf.h>

#include "cla/zephyr/nb_ble.h"
#include "routing/router_task.h"

// TODO: Make them configurable
#define ML2CAP_PSM 0x6c
#define ML2CAP_MAX_CONN 1
#define ML2CAP_PARALLEL_BUFFERS 256

// we will disconnect the connection if we did not receive something for X msec
#define IDLE_TIMEOUT_MS 4000

#define TIMEOUT_WARNING_MS 6000

struct ml2cap_link;

struct ml2cap_config {
    struct cla_config base;
    
    struct ml2cap_link *links[ML2CAP_MAX_CONN]; // we should not have really more entries than active connections?
    uint8_t num_links;
    Semaphore_t links_sem; // this prevents parallel access to active links

    struct bt_l2cap_server l2cap_server;
    Task_t management_task;
    bt_addr_le_t own_addr;
};

// it is initialized during the launch task
static struct ml2cap_config *ml2cap_config;

struct ml2cap_link {
    struct cla_link base;

    // Note that we use the MTCP data format!
    struct parser mtcp_parser;


    /* RX queue to handle zephyr's asynchronous recv callbacks */
    // it contains a net_buf reference
    // after usage, bt_l2cap_chan_recv_complete needs to be called on the buffer
    QueueIdentifier_t rx_queue;

    /* ml2cap://<Other ble device address in hex> */
    char *cla_addr;

    /* <Other ble device address in hex> */
    char *mac_addr;

    // we use a simple sem for mutual exclusion
    // if tx_data is available, the management thread will send it
    // if tx_data is not available (= null)
    //Semaphore_t tx_sem;
    //uint8_t *tx_data; // if null, the tx thread can put data in,
    //size_t tx_data_size;
    //size_t tx_data_sent;

    bool shutting_down; // will be set to true to cancel rx / tx tasks

    // basic link properties
    struct bt_conn *conn; // the reference to the zephyr connetion
    struct bt_l2cap_le_chan le_chan; // space for our channel
    bool chan_connected; // whether the channel is connected or not
    uint64_t bytes_sent; // the amount of bytes sent
    uint64_t bytes_received; // the amount of bytes received

    // some event timestamps for easier testing and debugging
    uint64_t connect_ts; // us that the connection was established
    uint64_t disconnect_ts; // us that the disconnect happened
    uint64_t channel_up_ts; // us that the channel was established
    uint64_t channel_down_ts; // us that the channel went down
    uint64_t rx_ts; // the last us to receive bytes
    uint64_t tx_ts; // the last us to send bytes
};

static struct ml2cap_link *ml2cap_link_create(
        struct ml2cap_config *const ml2cap_config,
        struct bt_conn *conn
);
static void ml2cap_link_destroy(struct ml2cap_link *ml2cap_link);

/*
 * Some Event Handling
 */
// we simply reuse own and other address strings for convenience
// This however also means, that the on_ methods should not be called simultaneously! (i.e. with locked active_lists mutex)
static char own_addr_str[BT_ADDR_LE_STR_LEN];

static void on_tx(struct ml2cap_link *link) {
    link->tx_ts = hal_time_get_timestamp_ms();

    /*LOGF("ML2CAP: on_tx | %s | %s | \n",
         own_addr_str,
         link->mac_addr
     );*/
}
static void on_rx(struct ml2cap_link *link) {
    link->rx_ts = hal_time_get_timestamp_ms();
    //int avg_kbits_per_sec = (link->bytes_received*8) / MAX(1, (link->rx_ts-link->channel_up_ts));
    /*LOGF("ML2CAP: on_rx | %s | %s | %d kbps\n",
         own_addr_str,
         link->mac_addr,
         avg_kbits_per_sec);*/
}
static void on_connect(struct ml2cap_link *link) {
    link->connect_ts = hal_time_get_timestamp_ms();

    /*LOGF("ML2CAP: on_connect | %s | %s | \n",
         own_addr_str,
         link->mac_addr);*/
}
static void on_disconnect(struct ml2cap_link *link) {
    link->disconnect_ts = hal_time_get_timestamp_ms();

    /*LOGF("ML2CAP: on_disconnect | %s | %s | \n",
         own_addr_str,
         link->mac_addr);*/
}
static void on_channel_up(struct ml2cap_link *link) {
    link->channel_up_ts = hal_time_get_timestamp_ms();

    /*LOGF("ML2CAP: on_channel_up | %s | %s | \n",
         own_addr_str,
         link->mac_addr);*/
}
static void on_channel_down(struct ml2cap_link *link) {
    link->channel_down_ts = hal_time_get_timestamp_ms();

    /*LOGF("ML2CAP: on_channel_down | %s | %s | \n",
         own_addr_str,
         link->mac_addr);*/
}

void add_active_link(struct ml2cap_link *link) {
    ASSERT(ml2cap_config->num_links < ML2CAP_MAX_CONN);
    ml2cap_config->links[ml2cap_config->num_links] = link;
    ml2cap_config->num_links++;
}

struct ml2cap_link *find_link_by_connection(struct bt_conn *conn) {
    struct ml2cap_link *link = NULL;
    for(int i = 0; i < ml2cap_config->num_links; i++) {
        if (ml2cap_config->links[i]->conn == conn) {
            link = ml2cap_config->links[i];
            break;
        }
    }
    return link;
}

// TODO: This linear search is not really good for scaling ;)
struct ml2cap_link *find_link_by_cla_address(const char *cla_addr) {
    struct ml2cap_link *link = NULL;
    for(int i = 0; i < ml2cap_config->num_links; i++) {
        if (!strcmp(ml2cap_config->links[i]->cla_addr, cla_addr)) {
            link = ml2cap_config->links[i];
            break;
        }
    }
    return link;
}

void remove_active_link(struct ml2cap_link *link) {
    for(int i = 0; i < ml2cap_config->num_links; i++) {
        if (ml2cap_config->links[i] == link) {
            // we first swap the links so we can safely delete the one at the end
            if (i != ml2cap_config->num_links-1) {
                ml2cap_config->links[i] = ml2cap_config->links[ml2cap_config->num_links-1];
            }
            ml2cap_config->links[ml2cap_config->num_links-1] = NULL;
            ml2cap_config->num_links--;
            break;
        }
    }
}

static const char *ml2cap_name_get(void) {
    return "ml2cap";
}


/**
 * We pump discovered neighbors through the CLA layer as we add the correct CLA address.
 */
static void handle_discovered_neighbor_info(void *context, const struct nb_ble_node_info * const ble_node_info, bool connectable) {
    (void)context; // this is just our configuration again :)

    //LOGF("ML2CAP: Found other device with mac_address %s and eid %s", ble_node_info->mac_addr, ble_node_info->eid);

    // we now build the corresponding node entry and push it to the router which would then decide how to proceed with this contact
    // node will be freed by the router
    struct node* node = node_create(ble_node_info->eid);

    if(!node) {
        LOG("ML2CAP: Error while creating the node for NB");
        return;
    }

    node->cla_addr = cla_get_cla_addr(ml2cap_name_get(), ble_node_info->mac_addr);

    struct router_signal rt_signal = {
            .type = ROUTER_SIGNAL_NEIGHBOR_DISCOVERED,
            .data = node,
    };
    const struct bundle_agent_interface *const bundle_agent_interface =
            ml2cap_config->base.bundle_agent_interface;
    hal_queue_push_to_back(bundle_agent_interface->router_signaling_queue,
                           &rt_signal);


    if (!connectable) {
        return;
    }


    // we also check if we reached our limit of active links
    // (so we do not initialized connections we can not handle)
    if (ml2cap_config->num_links == ML2CAP_MAX_CONN) {
        return;
    }


    bt_addr_le_t other_addr;
    bt_addr_le_from_mac_addr(ble_node_info->mac_addr, &other_addr);

    // we first check if we have a connection to this peer
    struct bt_conn *conn = bt_conn_lookup_addr_le(BT_ID_DEFAULT, &other_addr);

    if (conn != NULL) {
        // we already have connection -> abort
        bt_conn_unref(conn);
        return;
    }

    // we do not have a connection yet -> we try to initialize it, IF we are the one with the bigger mac address!
    if(bt_addr_le_cmp(&ml2cap_config->own_addr, &other_addr) <= 0) {
        return; // our addr is smaller :( -> await connection from the other node
    }

    // but in this case, our addr is actually "bigger" -> initialize connection

    // We now try to connect as soon as we received that advertisement
    nb_ble_stop(); // we need to disable the advertisements for that, Note that this cb is called by the NB_BLE TASK
    int err = bt_conn_le_create(&other_addr, BT_CONN_LE_CREATE_CONN, BT_LE_CONN_PARAM_DEFAULT, &conn);

    if (err) {
        // we get EINVAL in case the connection already exists...
        LOGF("ML2CAP: Failed to create connection (err %d)\n", err);
        //nb_ble_adv(); // directly try to start neighbor discovery // TODO: We only do that in the main loop
    } else {
        char *cla_address = cla_get_cla_addr(ml2cap_name_get(), ble_node_info->mac_addr);
        LOG_EV("conn_init", "\"other_mac_addr\": \"%s\", \"other_cla_addr\": \"%s\", \"other_eid\": \"%s\", \"connection\": \"%p\", \"own_eid\": \"%s\"", ble_node_info->mac_addr, cla_address, ble_node_info->eid, conn, ml2cap_config->base.bundle_agent_interface->local_eid);
        free(cla_address);
        bt_conn_unref(conn); // we directly unref here as we will use the callback to handle the connection
    }
}


static void chan_connected_cb(struct bt_l2cap_chan *chan) {
    // TODO: with this semaphore, we also block concurrent sending!
    hal_semaphore_take_blocking(ml2cap_config->links_sem);
    struct ml2cap_link *link = find_link_by_connection(chan->conn);
    if (link != NULL) {
        // TODO: is this the correct place for channel_up?
        ASSERT(!link->chan_connected);
        link->chan_connected = true;

        on_channel_up(link);
        LOG_EV("channel_up", "\"other_mac_addr\": \"%s\", \"connection\": \"%p\"", link->mac_addr, link->conn);

        if (cla_link_init(&link->base, &ml2cap_config->base) == UD3TN_OK) {

            // signal to the router that the connection is up
            struct router_signal rt_signal = {
                    .type = ROUTER_SIGNAL_CONN_UP,
                    .data = strdup(link->cla_addr),
            };
            const struct bundle_agent_interface *const bundle_agent_interface = ml2cap_config->base.bundle_agent_interface;
            hal_queue_push_to_back(bundle_agent_interface->router_signaling_queue, &rt_signal);
        } else {
            link->chan_connected = false;
            LOGF("ML2CAP: Error initializing CLA link for \"%s\"", link->cla_addr);
            bt_conn_disconnect(chan->conn, BT_HCI_ERR_REMOTE_USER_TERM_CONN);
        }
    } else {
        LOG("Could not find link in chan_connected_cb\n");
        bt_conn_disconnect(chan->conn, BT_HCI_ERR_REMOTE_USER_TERM_CONN);
    }
    hal_semaphore_release(ml2cap_config->links_sem);
}

static void chan_disconnected_cb(struct bt_l2cap_chan *chan) {
    hal_semaphore_take_blocking(ml2cap_config->links_sem);
    struct ml2cap_link *link = find_link_by_connection(chan->conn);
    if (link != NULL) {

        // is the right place for that?
        on_channel_down(link);
        LOG_EV("channel_down", "\"other_mac_addr\": \"%s\", \"connection\": \"%p\"", link->mac_addr, link->conn);

        link->shutting_down = true; // this will bring down the rx and tx task

        if (link->chan_connected) {
            // TODO: Move deconstruction to a separate thread
            // the connection is up and running -> rx and tx tasks have been initialized!
            // so we first first disable them!
            cla_generic_disconnect_handler(&link->base);

            // we also notify the router
            {
                struct router_signal rt_signal = {
                        .type = ROUTER_SIGNAL_CONN_DOWN,
                        .data = strdup(link->cla_addr),
                };

                const struct bundle_agent_interface *const bundle_agent_interface =
                        ml2cap_config->base.bundle_agent_interface;
                hal_queue_push_to_back(bundle_agent_interface->router_signaling_queue,
                                       &rt_signal);
            }

            // and wait for clean-up
            // TODO: This could take a while and might block connection handling? (we remove, notify and release therefore before this call)
            cla_link_wait_cleanup(&link->base);
            link->chan_connected = false;
        }
    } else {
        printk("Could not find link in chan_disconnected_cb\n");
    }
    hal_semaphore_release(ml2cap_config->links_sem);
}

static int chan_recv_cb(struct bt_l2cap_chan *chan, struct net_buf *buf) {

    size_t num_bytes_received = net_buf_frags_len(buf);
    hal_semaphore_take_blocking(ml2cap_config->links_sem);
    struct ml2cap_link *link = find_link_by_connection(chan->conn);
    if (link != NULL) {
        link->bytes_received += num_bytes_received;
        //printk("Received %d bytes\n", num_bytes_received);
        on_rx(link);

        //LOG_EV("rx", "\"from_mac_addr\": \"%s\", \"connection\": \"%p\", \"link\": \"%p\", \"num_bytes\": %d", link->mac_addr, chan->conn, link, num_bytes_received);

        size_t num_elements = net_buf_frags_len(buf);
        for (int i = 0; i < num_elements; i++) {
            // TODO: This message queue abuse is quite inefficient!
            // TODO: Check that this conversion is correct!
            size_t b = (size_t) net_buf_pull_u8(buf);
            hal_queue_push_to_back(link->rx_queue, (void *) &b);
        }
    } else {
        printk("Could not find link in chan_recv_cb\n");
    }
    hal_semaphore_release(ml2cap_config->links_sem);
    return 0;
}

int chan_accept(struct bt_conn *conn, struct bt_l2cap_chan **chan) {
    hal_semaphore_take_blocking(ml2cap_config->links_sem);
    struct ml2cap_link *link = find_link_by_connection(conn);
    int ret = 0;
    if (link != NULL) {
        *chan = &link->le_chan.chan;
    } else {
        printk("Could not find link in chan_disconnected_cb\n");
        *chan = NULL;
        ret = -EACCES;
    }
    hal_semaphore_release(ml2cap_config->links_sem);
    return ret;
}


static void connected(struct bt_conn *conn, uint8_t err)
{
    struct ml2cap_link *link = NULL;
    const char *reason = "unknown";

    // we can check the num_active links as this function is the only one that adds links
    if (!err) {
        if (ml2cap_config->num_links == ML2CAP_MAX_CONN) {
            printk("No more free links!\n");
            reason = "no_free_links";
            goto fail;
        }

        link = ml2cap_link_create(ml2cap_config, conn);

        if (link != NULL) {
            struct bt_conn_info info;
            if (!bt_conn_get_info(link->conn, &info)) {
                if (info.role == BT_CONN_ROLE_MASTER) {
                    int err = bt_l2cap_chan_connect(link->conn, &link->le_chan.chan, ML2CAP_PSM);
                    if (err) {
                        // we disconnect, this will eventually also clear this link
                        LOG("Could not connect to channel!\n");
                        reason = "channel_connection_failed";
                        goto fail;
                    } else {
                        hal_semaphore_take_blocking(ml2cap_config->links_sem);
                        add_active_link(link);
                        LOG_EV("connection_success", "\"other_mac_addr\": \"%s\", \"other_cla_addr\": \"%s\", \"connection\": \"%p\", \"link\": \"%p\", \"role\": \"client\"", link->mac_addr, link->cla_addr, conn, link);
                        on_connect(link);
                        hal_semaphore_release(ml2cap_config->links_sem);
                    }
                } else {
                    // NOOP, we simply await a connection...
                    hal_semaphore_take_blocking(ml2cap_config->links_sem);
                    add_active_link(link);
                    LOG_EV("connection_success", "\"other_mac_addr\": \"%s\", \"other_cla_addr\": \"%s\", \"connection\": \"%p\", \"link\": \"%p\", \"role\": \"peripheral\"", link->mac_addr, link->cla_addr, conn, link);
                    on_connect(link);
                    hal_semaphore_release(ml2cap_config->links_sem);
                }
            } else {
                // disconnect handler will free link
                printk("Failed to get connection info!\n");
                reason = "connection_info_failed";
                goto fail;
            }
        } else {
            // seems like we don't have enough memory to connect :(
            printk("Could not allocate link to connect\n");
            reason = "link_allocation_failed";
            goto fail;
        }
    } else {
        printk("BLE Connection failed (err 0x%02x)\n", err);
        reason = "failure";
        goto fail;
    }

    return;
    fail:
    if (link) {
        if (link->conn) {
            bt_conn_unref(conn);
            link->conn = NULL;
        }
        free(link);
    }
    bt_conn_disconnect(conn, BT_HCI_ERR_REMOTE_USER_TERM_CONN);
    LOG_EV("connection_failure", "\"connection\": \"%p\", \"reason\": \"%s\"", conn, reason);
}

static void disconnected(struct bt_conn *conn, uint8_t reason) {
    hal_semaphore_take_blocking(ml2cap_config->links_sem);

    struct ml2cap_link *link = find_link_by_connection(conn);

    if (link != NULL) {
        remove_active_link(link);
        on_disconnect(link);
        LOG_EV("disconnect", "\"other_mac_addr\": \"%s\", \"connection\": \"%p\", \"link\":\"%p\"", link->mac_addr, conn, link);
        ASSERT(!link->chan_connected);
        ml2cap_link_destroy(link);
    } else {
        printk("Could not find link for connection!\n");
    }

    hal_semaphore_release(ml2cap_config->links_sem);
    nb_ble_stop(); // we stop non-connectable advertisements for now
}

static struct ml2cap_link *ml2cap_link_create(
    struct ml2cap_config *const ml2cap_config,
    struct bt_conn *conn
) {
    struct ml2cap_link *ml2cap_link =
            malloc(sizeof(struct ml2cap_link));


    if (!ml2cap_link) {
        LOG("ML2CAP: Failed to allocate memory!");
        return NULL;
    }
    // We zero the whole region just to be safe (this currently also resets tx event times etc)
    memset(ml2cap_link, 0, sizeof(struct ml2cap_link));

    ml2cap_link->conn = bt_conn_ref(conn);
    ml2cap_link->chan_connected = false; // will be initialized once available
    ml2cap_link->shutting_down = false;

    if (!ml2cap_link->conn) {
        LOG("ML2CAP: Failed to ref connection!");
        goto fail_after_alloc;
    }

    struct bt_conn_info info;
    if (!bt_conn_get_info(ml2cap_link->conn, &info)) {
        ml2cap_link->mac_addr = bt_addr_le_to_mac_addr(info.le.dst);
    } else {
        LOG("ML2CAP: Failed to get connection info!");
        goto fail_after_ref;
    }

    if (!ml2cap_link->mac_addr) {
        LOG("ML2CAP: Failed to get mac_addr!");
        goto fail_after_ref;
        
    }

    ml2cap_link->cla_addr = cla_get_cla_addr(ml2cap_name_get(), ml2cap_link->mac_addr);
    
    if (!ml2cap_link->cla_addr) {
        LOG("ML2CAP: Failed to get cla_addr!");
        goto fail_after_mac_addr;
    }

    ml2cap_link->rx_queue = hal_queue_create(
            COMM_RX_QUEUE_LENGTH,
            sizeof(uint8_t)
    );

    if (!ml2cap_link->rx_queue) {
        LOG("ML2CAP: Failed to allocate rx queue!");
        goto fail_after_cla_addr;
    }

    mtcp_parser_reset(&ml2cap_link->mtcp_parser);

    static struct bt_l2cap_chan_ops chan_ops = {
            .connected = chan_connected_cb,
            .disconnected = chan_disconnected_cb,
            .recv = chan_recv_cb,
            .alloc_buf = NULL // TODO: Do we need to provide this callback?
    };
    // reset chan contents TODO: we already set this
    memset(&ml2cap_link->le_chan, 0, sizeof(ml2cap_link->le_chan));

    ml2cap_link->le_chan.chan.ops = &chan_ops;

    return ml2cap_link;
    
    //fail_after_rx_queue:
    //hal_queue_delete(ml2cap_link->rx_queue);

    fail_after_cla_addr:
    free(ml2cap_link->cla_addr);

    fail_after_mac_addr:
    free(ml2cap_link->mac_addr);

    fail_after_ref:
    bt_conn_unref(ml2cap_link->conn);

    fail_after_alloc:
    free(ml2cap_link);
    return NULL;
}

static void ml2cap_link_destroy(struct ml2cap_link *ml2cap_link) {
    mtcp_parser_reset(&ml2cap_link->mtcp_parser);
    hal_queue_delete(ml2cap_link->rx_queue);
    free(ml2cap_link->cla_addr);
    free(ml2cap_link->mac_addr);
    bt_conn_unref(ml2cap_link->conn);
    free(ml2cap_link);
}

/**
 * Because this accept method requires space for a channel,
 *
 * dynamic allocation is also not possible since the disconnect and release cb can not be used to consistently free again..
 */
int l2cap_accept(struct bt_conn *conn, struct bt_l2cap_chan **chan) {
    hal_semaphore_take_blocking(ml2cap_config->links_sem);
    struct ml2cap_link *ml2cap_link = find_link_by_connection(conn);

    // we expect the ml2cap_link to be overall valid as this is also called from within the bt stack
    if (ml2cap_link != NULL) {
        // we can delete this as the tx and rx tasks do not need to lookup the link!
        *chan = &ml2cap_link->le_chan.chan;
        hal_semaphore_release(ml2cap_config->links_sem);
        return 0;
    } else {
        LOG("ML2CAP: l2cap_accept could not find link for channel!");
        hal_semaphore_release(ml2cap_config->links_sem);
        return -EACCES;
    }
}

static void mtcp_management_task(void *param) {

    // we setup the L2CAP server to handle incoming connections

    int err = bt_enable(NULL);
    if (err) {
        LOGF("Bluetooth init failed (err %d)", err);
        goto terminate;
    }

    static struct bt_conn_cb conn_callbacks = {
            .connected = connected,
            .disconnected = disconnected,
    };

    bt_conn_cb_register(&conn_callbacks);
    LOG("Bluetooth init done");


    LOG("Starting NB BLE");

    struct nb_ble_config config = {
            .eid = ml2cap_config->base.bundle_agent_interface->local_eid, // This gets copied
            .discover_cb = handle_discovered_neighbor_info,
            .discover_cb_context = ml2cap_config
    };

    if (nb_ble_init(&config) != UD3TN_OK) {
        goto terminate;
    }


    // initialize local address
    size_t count = 1;
    bt_id_get(&ml2cap_config->own_addr, &count);
    bt_addr_le_to_str(&ml2cap_config->own_addr, own_addr_str, sizeof(own_addr_str));

    char *own_mac_addr = bt_addr_le_to_mac_addr(&ml2cap_config->own_addr);
    LOG_EV("ml2cap_init", "\"own_mac_addr\": \"%s\", \"own_eid\": \"%s\"", own_mac_addr, ml2cap_config->base.bundle_agent_interface->local_eid);
    if (own_mac_addr) {
        free(own_mac_addr);
    }

    ml2cap_config->l2cap_server.psm = ML2CAP_PSM;
    ml2cap_config->l2cap_server.accept = l2cap_accept;

    err = bt_l2cap_server_register(&ml2cap_config->l2cap_server);
    if (err) {
        LOG("ML2CAP: Error while registering L2CAP Server");
        goto terminate;
    }
    LOG("ML2CAP: Registered L2CAP Server");

    uint64_t next_adv_start = 0;

    // we loop through the events
    while (true) {

        // we need to periodically try to activate advertisements again.
        nb_ble_adv(ml2cap_config->num_links < ML2CAP_MAX_CONN);

        hal_semaphore_take_blocking(ml2cap_config->links_sem);
        for(int i = 0; i < ml2cap_config->num_links; ++i) {
            struct ml2cap_link *link = ml2cap_config->links[i];

            uint64_t now = hal_time_get_timestamp_ms();

#if IDLE_TIMEOUT_MS > 0
        uint64_t last_chan_update = MAX(link->channel_up_ts, MAX(link->rx_ts, link->tx_ts));
        if (!link->shutting_down && link->chan_connected && last_chan_update + IDLE_TIMEOUT_MS < now) {
            LOGF("ML2CAP: Disconnecting idle connection to \"%s\"", link->cla_addr);

            LOG_EV("idle_disconnect", "\"other_mac_addr\": \"%s\", \"other_cla_addr\": \"%s\", \"connection\": \"%p\", \"link\": \"%p\"", link->mac_addr, link->cla_addr, link->conn, link);

            bt_conn_disconnect(link->conn, BT_HCI_ERR_REMOTE_USER_TERM_CONN);
            link->shutting_down = true;
        }
#endif

    #if TIMEOUT_WARNING_MS > 0
            bool possibly_broken = false;

            if (link->connect_ts + TIMEOUT_WARNING_MS < now) {
                // connection is old enough!
                if (!link->channel_up_ts) {
                    LOG("ML2CAP: Timeout warning: channel is still not up!\n");
                    possibly_broken = true;
                }
            }

            if (link->channel_down_ts && link->channel_down_ts + TIMEOUT_WARNING_MS < now) {
                LOG("ML2CAP: Timeout warning: channel_down timeout!\n");
                possibly_broken = true;
            }

            if (link->disconnect_ts && link->disconnect_ts + TIMEOUT_WARNING_MS < now) {
                LOG("ML2CAP: Timeout warning: disconnect timeout!\n");
                possibly_broken = true;
            }

            if (possibly_broken) {
                LOGF("ML2CAP: Disconnecting possibly broken connection to \"%s\"", link->cla_addr);
                int res = bt_conn_disconnect(link->conn, BT_HCI_ERR_REMOTE_USER_TERM_CONN);
                LOGF("ML2CAP: Disconnecting result: %d", res);
            }
        }
        #endif
        hal_semaphore_release(ml2cap_config->links_sem);
    }

    terminate:
    hal_task_delete(ml2cap_config->management_task);
    free(param);
}

static enum ud3tn_result ml2cap_launch(struct cla_config *const config) {

    ml2cap_config->management_task = hal_task_create(
            mtcp_management_task,
            "ml2cap_mgmt_t",
            CONTACT_LISTEN_TASK_PRIORITY, // TODO
            ml2cap_config,
            CONTACT_LISTEN_TASK_STACK_SIZE, // TODO
            (void *) CLA_SPECIFIC_TASK_TAG
    );

    if (!ml2cap_config->management_task)
        return UD3TN_FAIL;

    return UD3TN_OK;
}

size_t ml2cap_mbs_get(struct cla_config *const config) {
    (void) config;
    return SIZE_MAX;
}

void ml2cap_reset_parsers(struct cla_link *link) {
    struct ml2cap_link *const ml2cap_link = (struct ml2cap_link *) link;

    rx_task_reset_parsers(&link->rx_task_data);

    mtcp_parser_reset(&ml2cap_link->mtcp_parser);
    link->rx_task_data.cur_parser = &ml2cap_link->mtcp_parser;
}

size_t ml2cap_forward_to_specific_parser(struct cla_link *link,
                                         const uint8_t *buffer, size_t length) {
    struct ml2cap_link *const ml2cap_link = (struct ml2cap_link *) link;
    struct rx_task_data *const rx_data = &link->rx_task_data;
    size_t result = 0;

    // Decode MTCP CBOR byte string header if not done already
    if (!(ml2cap_link->mtcp_parser.flags & PARSER_FLAG_DATA_SUBPARSER))
        return mtcp_parser_parse(&ml2cap_link->mtcp_parser,
                                 buffer, length);

    // We do not allow to parse more than the stated length...
    if (length > ml2cap_link->mtcp_parser.next_bytes)
        length = ml2cap_link->mtcp_parser.next_bytes;

    switch (rx_data->payload_type) {
        case PAYLOAD_UNKNOWN:
            result = select_bundle_parser_version(rx_data, buffer, length);
            if (result == 0)
                ml2cap_reset_parsers(link);
            break;
        case PAYLOAD_BUNDLE6:
            rx_data->cur_parser = rx_data->bundle6_parser.basedata;
            result = bundle6_parser_read(
                    &rx_data->bundle6_parser,
                    buffer,
                    length
            );
            break;
        case PAYLOAD_BUNDLE7:
            rx_data->cur_parser = rx_data->bundle7_parser.basedata;
            result = bundle7_parser_read(
                    &rx_data->bundle7_parser,
                    buffer,
                    length
            );
            break;
        default:
            ml2cap_reset_parsers(link);
            return 0;
    }

    ASSERT(result <= ml2cap_link->mtcp_parser.next_bytes);
    ml2cap_link->mtcp_parser.next_bytes -= result;

    // All done
    if (!ml2cap_link->mtcp_parser.next_bytes)
        ml2cap_reset_parsers(link);

    return result;
}


static enum ud3tn_result ml2cap_read(struct cla_link *link,
                                     uint8_t *buffer, size_t length,
                                     size_t *bytes_read) {
    struct ml2cap_link *const ml2cap_link =
            (struct ml2cap_link *) link;


    // Special case: empty buffer
    if (length == 0) {
        *bytes_read = 0;
        return UD3TN_OK;
    }

    // Write-pointer to the current buffer position
    uint8_t *stream = buffer;

    QueueIdentifier_t rx_queue = ml2cap_link->rx_queue;

    // Receive at least one byte in blocking manner from the RX queue
    while (hal_queue_receive(rx_queue, stream, COMM_RX_TIMEOUT) != UD3TN_OK) {
        // it might be that we have disconnected while waiting...
        if (ml2cap_link->shutting_down) {
            *bytes_read = 0;
            return UD3TN_FAIL;
        }
    }

    

    length--;
    stream++;

    // Emulate the behavior of recv() by reading further bytes with a very
    // small timeout.
    while (length--) {

        if (ml2cap_link->shutting_down) {
            *bytes_read = 0;
            return UD3TN_FAIL;
        }


        if (hal_queue_receive(rx_queue, stream,
                              COMM_RX_TIMEOUT) != UD3TN_OK)
            break;
        stream++;
    }

    *bytes_read = stream - buffer;


    return UD3TN_OK;
}

static enum ud3tn_result ml2cap_start_scheduled_contact(
        struct cla_config *config, const char *eid, const char *cla_addr) {
    // STUB - UNUSED
    (void) config;
    (void) eid;
    (void) cla_addr;

    // TODO: we need to use bt_addr_le_from_str to parse the cla_address again

    return UD3TN_OK;
}

static enum ud3tn_result ml2cap_end_scheduled_contact(
        struct cla_config *config, const char *eid, const char *cla_addr) {
    // STUB - UNUSED
    (void) config;
    (void) eid;
    (void) cla_addr;

    return UD3TN_OK;
}

NET_BUF_POOL_DEFINE(ml2cap_send_packet_data_pool, ML2CAP_PARALLEL_BUFFERS,
    BT_L2CAP_CHAN_SEND_RESERVE+CONFIG_BT_L2CAP_TX_MTU,
    0,
    NULL
);

static void l2cap_chan_tx_resume(struct bt_l2cap_le_chan *ch)
{
    if (!atomic_get(&ch->tx.credits) ||
        (k_fifo_is_empty(&ch->tx_queue) && !ch->tx_buf)) {
        return;
    }

    k_work_submit(&ch->tx_work);
}


/**
 *
 * @param ml2cap_link
 * @param data
 * @param length
 * @return < 0 in case of error, otherwise the amount of bytes transmitted
 */
static int try_chan_send(const struct ml2cap_link *ml2cap_link, const void *data, const size_t length, int timeout_ms) {
    uint32_t mtu = ml2cap_link->le_chan.tx.mtu;
    uint32_t frag_size = Z_MIN(mtu, length);

    struct net_buf *buf = net_buf_alloc_len(&ml2cap_send_packet_data_pool, BT_L2CAP_CHAN_SEND_RESERVE+mtu, K_MSEC(timeout_ms));

    if (buf == NULL) {
        return 0;
    }

    net_buf_reserve(buf, BT_L2CAP_CHAN_SEND_RESERVE);
    net_buf_add_mem(buf, ((char *)data), frag_size);

    int ret = bt_l2cap_chan_send(&ml2cap_link->le_chan.chan, buf);

    if (ret < 0) {
        net_buf_unref(buf);
        if (ret != -EAGAIN) {
            LOGF("ml2cap: ml2cap_send_packet_data failed with ret %d", ret);
        }
        return ret;
    }

    return frag_size;
}

static void l2cap_transmit_bytes(struct cla_link *link, const void *data, const size_t length) {

    struct ml2cap_link *const ml2cap_link = (struct ml2cap_link *) link;
    (void) ml2cap_config;

    // overall length could be more than the supported MTU -> we need to

    //LOG_EV("tx", "\"to_mac_addr\": \"%s\", \"connection\": \"%p\", \"link\": \"%p\", \"num_bytes\": %d", ml2cap_link->mac_addr, ml2cap_link->conn, ml2cap_link, length);

    size_t sent = 0;

    while (!ml2cap_link->shutting_down && sent < length) {

        int send_res = try_chan_send(ml2cap_link, ((char *)data) + sent, length-sent, COMM_RX_TIMEOUT);

        if (send_res < 0) {
            LOGF("ml2cap: ml2cap_send_packet_data failed with ret %d", send_res);
            return;
        }

        sent += send_res;
        ml2cap_link->bytes_sent += send_res;
        on_tx(ml2cap_link);
    }
}

static void ml2cap_begin_packet(struct cla_link *link, size_t length) {

    const size_t BUFFER_SIZE = 9; // max. for uint64_t
    uint8_t buffer[BUFFER_SIZE];

    const size_t hdr_len = mtcp_encode_header(buffer, BUFFER_SIZE, length);

    l2cap_transmit_bytes(link, buffer, hdr_len);
}

static void ml2cap_end_packet(struct cla_link *link) {
    // STUB
    (void) link;
}


void ml2cap_send_packet_data(struct cla_link *link, const void *data, const size_t length) {
    l2cap_transmit_bytes(link, data, length);
}

static struct cla_tx_queue ml2cap_get_tx_queue(
        struct cla_config *config, const char *eid, const char *cla_addr) {
    (void) eid;

    hal_semaphore_take_blocking(ml2cap_config->links_sem);
    struct ml2cap_link *link = find_link_by_cla_address(cla_addr);

    if (link && !link->shutting_down && link->chan_connected) {
        struct cla_link *const cla_link = &link->base;

        hal_semaphore_take_blocking(cla_link->tx_queue_sem);
        hal_semaphore_release(ml2cap_config->links_sem);

        // Freed while trying to obtain it
        if (!cla_link->tx_queue_handle)
            return (struct cla_tx_queue) {NULL, NULL};

        return (struct cla_tx_queue) {
                .tx_queue_handle = cla_link->tx_queue_handle,
                .tx_queue_sem = cla_link->tx_queue_sem,
        };
    }

    hal_semaphore_release(ml2cap_config->links_sem);
    return (struct cla_tx_queue) {NULL, NULL};
}

const struct cla_vtable ml2cap_vtable = {
        .cla_name_get = ml2cap_name_get,
        .cla_launch = ml2cap_launch,
        .cla_mbs_get = ml2cap_mbs_get,

        .cla_get_tx_queue = ml2cap_get_tx_queue,
        .cla_start_scheduled_contact = ml2cap_start_scheduled_contact,
        .cla_end_scheduled_contact = ml2cap_end_scheduled_contact,

        .cla_begin_packet = ml2cap_begin_packet,
        .cla_end_packet = ml2cap_end_packet,
        .cla_send_packet_data = ml2cap_send_packet_data,

        .cla_rx_task_reset_parsers = ml2cap_reset_parsers,
        .cla_rx_task_forward_to_specific_parser =
        ml2cap_forward_to_specific_parser,

        .cla_read = ml2cap_read,

        .cla_disconnect_handler = cla_generic_disconnect_handler,
};

static enum ud3tn_result ml2cap_init(
        struct ml2cap_config *config, const struct bundle_agent_interface *bundle_agent_interface) {
    /* Initialize base_config */
    if (cla_config_init(&config->base, bundle_agent_interface) != UD3TN_OK)
        return UD3TN_FAIL;



    config->links_sem = hal_semaphore_init_binary();
    config->num_links = 0;
    hal_semaphore_release(config->links_sem);


    /* set base_config vtable */
    config->base.vtable = &ml2cap_vtable;

    return UD3TN_OK;
}

struct cla_config *ml2cap_create(
        const char *const options[], const size_t option_count,
        const struct bundle_agent_interface *bundle_agent_interface) {

    (void) options;
    (void) option_count;

    if (ml2cap_config) {
        // TODO: Shall we handle restarts too?
        LOG("ml2cap: Already created");
        return NULL;
    }

    struct ml2cap_config *config = malloc(sizeof(struct ml2cap_config));

    if (!config) {
        LOG("ml2cap: Memory allocation failed!");
        return NULL;
    }

    if (ml2cap_init(config, bundle_agent_interface) != UD3TN_OK) {
        free(config);
        LOG("ml2cap: Initialization failed!");
        return NULL;
    }

    // TODO: Rework this singleton!
    ml2cap_config = config;

    LOG("ml2cap: Creation completed!");
    return &config->base;
}
