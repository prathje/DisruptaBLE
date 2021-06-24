import sys
import tinydb

from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

from pprint import pprint
import sqlite3

def find_mac_addr_by_eid(db, run, eid):
    query = tinydb.Query()
    x = db.get((query.type == 'ml2cap_init') & (query.run == run) & (query.data.own_eid == eid))
    return x['data']['own_mac_addr']

def find_eid_by_mac_addr(db, run, mac_addr):
    query = tinydb.Query()
    x = db.get((query.type == 'ml2cap_init') & (query.run == run) & (query.data.own_mac_addr == mac_addr))
    return x['data']['own_eid']

def find_eid_by_device_id(db, run, device_id):
    query = tinydb.Query()
    x = db.get((query.type == 'ml2cap_init') & (query.run == run) & (query.device_id == device_id))
    return x['data']['own_eid']

def handle_connections(db):
    # Select all conn_init calls:

    db.drop_table('connections')
    conn_table = db.table('connections')

    query = tinydb.Query()
    for e in db.search(query.type == 'conn_init'):
        ce = {
                "run": e['run'],
                "us": e['us'],
                "client": {
                    "eid": find_eid_by_device_id(db, e['run'], e['device_id']),
                    "rx_bytes": 0,
                    "tx_bytes": 0,
                    "events": {
                        "conn_init": {
                            "us": e['us']
                        },
                        "channel_up": None,
                        "channel_down": None,
                        "connection_success": None,
                        "connection_failure": None,
                        "disconnect": None,
                        "idle_disconnect": None
                    }
                },
                "peripheral": {
                    "eid": e['data']['other_eid'],
                    "rx_bytes": 0,  # TODO: Make first_us, last_us?
                    "tx_bytes": 0,  # TODO: Number of bundles? and which bundles?
                    "events": {
                        "channel_up": None,
                        "channel_down": None,
                        "connection_success": None,
                        "connection_failure": None,
                        "disconnect": None,
                        "idle_disconnect": None
                    }
                }
            }
        conn_table.insert(ce)

    def find_conn_event(run, eid_a, eid_b, up_to_us):
        us_window_end = up_to_us
        while True:
            query = tinydb.Query()
            res = conn_table.search((query.run == run) & (query.us > (us_window_end-1000000)) & (query.us <= us_window_end) &  (((query.client.eid == eid_a) & (query.peripheral.eid == eid_b)) | ((query.client.eid == eid_b) & (query.peripheral.eid == eid_a))))

            if len(res) > 0:
                s = sorted(res, key=lambda x: x['us'])
                return s[-1]

            if us_window_end <= 0:
                return None # could not find it
            else:
                us_window_end -= 1000000


    # We now loop through all relevant connection events
    event_types = ["disconnect", "connection_success", "channel_up", "channel_down", "idle_disconnect"]
    for et in event_types:
        for e in db.search(query.type == et):
            eid_a = find_eid_by_device_id(db, e['run'], e['device_id'])
            eid_b = find_eid_by_mac_addr(db, e['run'], e['data']['other_mac_addr'])
            conn_ev = find_conn_event(e['run'], eid_a, eid_b, e['us'])

            assert conn_ev['us'] < e['us']

            if conn_ev['client']['eid'] == eid_a:
                assert conn_ev['client']['events'][et] is None
                conn_ev['client']['events'][et] = {"us": e['us']}
            else:
                assert conn_ev['peripheral']['events'][et] is None
                conn_ev['peripheral']['events'][et] = {"us": e['us']}

            conn_table.update(conn_ev, doc_ids=[conn_ev.doc_id])

    for et in ["rx", "tx"]:
        for e in db.search(query.type == et):
            eid_a = find_eid_by_device_id(db, e['run'], e['device_id'])
            eid_b = find_eid_by_mac_addr(db, e['run'], e['data']['from_mac_addr'])
            conn_ev = find_conn_event(e['run'], eid_a, eid_b, e['us'])

            assert conn_ev['us'] < e['us']

            if conn_ev['client']['eid'] == eid_a:
                conn_ev['client'][et + '_bytes'] += e['data']['num_bytes']
            else:
                conn_ev['peripheral'][et + '_bytes'] += e['data']['num_bytes']

            conn_table.update(conn_ev, doc_ids=[conn_ev.doc_id])

    # TODO: Handle disconnect reasons!

    con = sqlite3.connect(':memory:')
    cur = con.cursor()
    cur.execute('''CREATE TABLE conn_info
               (
               client_eid TEXT,
               client_rx_bytes INTEGER,
               client_tx_bytes INTEGER,
               client_channel_init_us INTEGER,
               client_channel_up_us INTEGER,
               client_channel_down_us INTEGER,
               client_connection_success_us INTEGER,
               client_connection_failure_us INTEGER,
               client_disconnect_us INTEGER,
               client_disconnect_reason text,
               client_idle_disconnect_us INTEGER,
               peripheral_eid TEXT,
               peripheral_rx_bytes INTEGER,
               peripheral_tx_bytes INTEGER,
               peripheral_channel_up_us INTEGER,
               peripheral_channel_down_us INTEGER,
               peripheral_connection_success_us INTEGER,
               peripheral_connection_failure_us INTEGER,
               peripheral_disconnect_us INTEGER,
               peripheral_disconnect_reason text,
               peripheral_idle_disconnect_us INTEGER
               )
               ''')
    # TODO: connection_failure_reason!!!
    con.commit()

    insert_sql = '''INSERT INTO conn_info VALUES (
               :client_eid,
               :client_rx_bytes,
               :client_tx_bytes,
               :client_channel_init_us,
               :client_channel_up_us,
               :client_channel_down_us,
               :client_connection_success_us,
               :client_connection_failure_us,
               :client_disconnect_us,
               :client_disconnect_reason,
               :client_idle_disconnect_us,
               :peripheral_eid,
               :peripheral_rx_bytes,
               :peripheral_tx_bytes,
               :peripheral_channel_up_us,
               :peripheral_channel_down_us,
               :peripheral_connection_success_us,
               :peripheral_connection_failure_us,
               :peripheral_disconnect_us,
               :peripheral_disconnect_reason,
               :peripheral_idle_disconnect_us)'''


    def get_val_if_not_none(v, attr):
        if v is not None:
            return v.get(attr, None)
        else:
            return None

    for e in conn_table.all():
        e_d = {
            "client_eid": e['client']['eid'],
            "client_rx_bytes": e['client']['rx_bytes'],
            "client_tx_bytes": e['client']['tx_bytes'],
            "client_channel_init_us": get_val_if_not_none(e['client']['events']['conn_init'], 'us'),
            "client_channel_up_us": get_val_if_not_none(e['client']['events']['channel_up'], 'us'),
            "client_channel_down_us":get_val_if_not_none(e['client']['events']['channel_down'], 'us'),
            "client_connection_success_us": get_val_if_not_none(e['client']['events']['connection_success'], 'us'),
            "client_connection_failure_us": get_val_if_not_none(e['client']['events']['connection_failure'], 'us'),
            "client_disconnect_us": get_val_if_not_none(e['client']['events']['disconnect'], 'us'),
            "client_disconnect_reason": get_val_if_not_none(e['client']['events']['disconnect'], 'reason'),
            "client_idle_disconnect_us": get_val_if_not_none(e['client']['events']['idle_disconnect'], 'reason'),
            "peripheral_eid": e['peripheral']['eid'],
            "peripheral_rx_bytes": e['peripheral']['rx_bytes'],
            "peripheral_tx_bytes": e['peripheral']['tx_bytes'],
            "peripheral_channel_up_us": get_val_if_not_none(e['peripheral']['events']['channel_up'], 'us'),
            "peripheral_channel_down_us":get_val_if_not_none(e['peripheral']['events']['channel_down'], 'us'),
            "peripheral_connection_success_us": get_val_if_not_none(e['peripheral']['events']['connection_success'], 'us'),
            "peripheral_connection_failure_us": get_val_if_not_none(e['peripheral']['events']['connection_failure'], 'us'),
            "peripheral_disconnect_us": get_val_if_not_none(e['peripheral']['events']['disconnect'], 'us'),
            "peripheral_disconnect_reason": get_val_if_not_none(e['peripheral']['events']['disconnect'], 'reason'),
            "peripheral_idle_disconnect_us": get_val_if_not_none(e['peripheral']['events']['idle_disconnect'], 'reason'),
        }
        con.executemany(insert_sql, [e_d])

    con.commit()
    pprint(list(cur.execute('''
        SELECT
        AVG(client_connection_success_us-client_channel_init_us) / 1000000,
        AVG(client_channel_up_us-client_connection_success_us)/ 1000000,
        AVG(client_channel_down_us-client_channel_up_us)/ 1000000,
        AVG(client_disconnect_us-client_connection_success_us)/ 1000000,
        AVG(client_connection_success_us-peripheral_connection_success_us) / 1000000,
        AVG(client_disconnect_us-peripheral_disconnect_us)/ 1000000,
        AVG(client_rx_bytes / ((client_channel_down_us-client_channel_up_us)/ 1000000)),
        AVG(peripheral_rx_bytes / ((peripheral_channel_down_us-peripheral_channel_up_us)/ 1000000))
        FROM conn_info
    ''')))


    # How to find the correct connection event?
    # Just use the latest one would not work as another device might tried to connect to us in the meantime
    # we thus need to use the connection and mac_address to filter the correct conn_init entry

    # TODO: connection_failure (but only the client!)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("No path to db given")
        exit()

    db_path = sys.argv[1]

    db = tinydb.TinyDB(db_path, storage=CachingMiddleware(JSONStorage))

    handlers = [
        handle_connections
    ]

    for h in handlers:
        h(db)