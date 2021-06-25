import sys
import json
import dotenv
import os


from pprint import pprint
import sqlite3

from pydal import DAL, Field
import tables

config = {
    **dotenv.dotenv_values(".env"),  # load shared development variables
    **dotenv.dotenv_values(".env.local"),  # load sensitive variables
    **dotenv.dotenv_values("run.env"),  # run specific variables TODO: Make this configurable?
    **os.environ,  # override loaded values with environment variables
}

def find_mac_addr_by_eid(db, run, eid):
    query = tinydb.Query()
    x = db.get((query.type == 'ml2cap_init') & (query.run == run) & (query.data.own_eid == eid))
    return x['data']['own_mac_addr']

def find_eid_by_mac_addr(db, run, mac_addr):
    query = tinydb.Query()
    x = db.get((query.type == 'ml2cap_init') & (query.run == run) & (query.data.own_mac_addr == mac_addr))
    return x['data']['own_eid']

def find_device_by_number(db, run, device_number):
    return db((db.device.run == run) & (db.device.number == device_number)).select()[0]

def find_device_by_eid(db, run, eid):
    return db((db.device.run == run) & (db.device.eid == eid)).select()[0]

def find_device_by_mac_addr(db, run, mac_addr):
    return db((db.device.run == run) & (db.device.mac_addr == mac_addr)).select()[0]


def iter_events(db, run, type):
    entries = db((db.event.run == run) & (db.event.type == type)).iterselect(orderby=db.event.us|db.event.device)

    for e in entries:
        e.data = json.loads(e.data_json)
        yield e

def handle_devices(db, run):
    for e in iter_events(db, run, 'ml2cap_init'):
        db['device'].insert(
            run=run,
            number=e.device,
            eid=e.data['own_eid'],
            mac_addr=e.data['own_mac_addr']
        )

    db.commit()
    #pprint(list(db(db.device).select()))


def handle_connections(db, run):
    # Select all conn_init calls:

    for e in iter_events(db, run, 'conn_init'):
        db.conn_info.insert(**{
            "run": run,
            "client": find_device_by_number(db, run, e.device),
            "peripheral": find_device_by_eid(db, run, e.data['other_eid']),
            "client_rx_bytes": 0,
            "client_tx_bytes": 0,
            "peripheral_rx_bytes": 0,
            "peripheral_tx_bytes": 0,
            "client_channel_init_us": e.us
        })

    db.commit()

    def find_conn_event(own_id, other_mac, up_to_us):
        device_a = find_device_by_number(db, run, own_id)
        device_b = find_device_by_mac_addr(db, run, other_mac)

        assert device_a
        assert device_b

        conn_ev = db(
                (db.conn_info.run == run) & (db.conn_info.client_channel_init_us <= up_to_us)
                & (((db.conn_info.client == device_a) & (db.conn_info.peripheral == device_b)) | ((db.conn_info.client == device_b) & (db.conn_info.peripheral == device_a)))
            ).select(db.conn_info.ALL, orderby=~db.conn_info.client_channel_init_us, limitby=(0,1))[0]

        return (device_a.id == conn_ev.client.id, conn_ev)

    # We now loop through all relevant connection events
    event_types = ["disconnect", "connection_success", "channel_up", "channel_down", "idle_disconnect"]

    # TODO: Handle  "connection_failure"

    for et in event_types:
        for e in iter_events(db, run, et):
            (is_client, conn_ev) = find_conn_event(e.device, e['data']['other_mac_addr'], e['us'])
            assert conn_ev.client_channel_init_us < e['us']

            us_property = "{}_{}_us".format('client' if is_client else 'peripheral', et)
            assert conn_ev[us_property] is None

            # Does this work?
            db(db.conn_info.id == conn_ev).update(**{
                us_property: e['us']
            })

            if et == "connection_failure":
                if is_client:
                    db(db.conn_info.id == conn_ev).update(client_disconnect_reason=e.data['reason'])
                else:
                    db(db.conn_info.id == conn_ev).update(peripheral_disconnect_reason=e.data['reason'])

            db.commit()


    for et in ["rx", "tx"]:
        for e in iter_events(db, run, et):
            other_mac_addr_prop = 'from_mac_addr' if et == 'rx' else 'to_mac_addr'
            (is_client, conn_ev) = find_conn_event(e.device, e['data'][other_mac_addr_prop], e['us'])
            assert conn_ev.client_channel_init_us < e['us']

            property = "{}_{}_bytes".format('client' if is_client else 'peripheral', et)

            conn_ev[property] += e['data']['num_bytes']

            # Does this work?
            db(db.conn_info.id == conn_ev).update(**{
                property: conn_ev[property]
            })

            db.commit()

    pprint(db.executesql('''
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
    '''))


    # How to find the correct connection event?
    # Just use the latest one would not work as another device might tried to connect to us in the meantime
    # we thus need to use the connection and mac_address    to filter the correct conn_init entry

    # TODO: connection_failure (but only the client!)




if __name__ == "__main__":

    logdir = config['SIM_LOG_DIR']
    os.makedirs(logdir, exist_ok=True)

    db = DAL("sqlite://sqlite.db", folder=logdir)

    tables.init_tables(db)

    # we reset everything for testing purposes
    tables.init_eval_tables(db)
    tables.reset_eval_tables(db)

    # And init again ;)
    tables.init_eval_tables(db)

    handlers = [
        handle_devices,
        handle_connections
    ]


    runs = db(db.run.status == 'finished').iterselect()

    for run in runs:
        for h in handlers:
            h(db, run)