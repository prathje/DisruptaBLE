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

#def find_device_by_number(db, run, device_number):
#    return db((db.device.run == run) & (db.device.number == device_number)).select()[0]

def find_device_by_eid(db, run, eid):
    if eid == "dtn://fake":
        return None

    service = eid.find("/routing")

    if service >= 0:
        eid = eid[:service]

    return db((db.device.run == run) & (db.device.eid == eid)).select()[0]


def find_bundle(db, run, source_eid, dest_eid, creation_timestamp_ms):
    res = list(
        db(
            (db.bundle.run == run)
            & (db.bundle.source_eid == source_eid)
            & (db.bundle.destination_eid == dest_eid)
            & (db.bundle.creation_timestamp_ms == creation_timestamp_ms)
        ).select()
    )
    assert len(res) == 1
    return res[0]

# We need a specific us as bundles might get deleted afterward
def find_stored_bundle_or_none(db, run, device, bundle_id, max_us=None):

    if max_us is None:
        max_us = run.simulation_time

    res = list(
        db(
                (db.stored_bundle.run == run)
              & (db.stored_bundle.device == device)
              & (db.stored_bundle.created_us <= max_us)
              & (db.stored_bundle.local_id == bundle_id)
        ).select(orderby=~db.stored_bundle.created_us) # limitby=(0,1)?
    )

    assert len(res) <= 1

    if len(res) == 1:
        return res[0]
    else:
        return None

def find_stored_bundle(db, run, device, bundle_id, max_us):
    res = find_stored_bundle_or_none(db, run, device, bundle_id, max_us)
    assert res
    return res


def find_device_by_mac_addr(db, run, mac_addr):
    return db((db.device.run == run) & (db.device.mac_addr == mac_addr)).select()[0]


def iter_events(db, run, type):
    entries = db((db.event.run == run) & (db.event.type == type)).iterselect(orderby=db.event.us|db.event.device)

    for e in entries:
        e.data = json.loads(e.data_json)
        yield e

def iter_events_with_devices(db, run, type):
    device_list = list(
        db((db.device.run == run)).select(orderby=db.device.number)
    )

    entries = db((db.event.run == run) & (db.event.type == type)).iterselect(orderby=db.event.us|db.event.device)

    for e in entries:
        e.data = json.loads(e.data_json)
        e.device = device_list[e.device]
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

def find_conn_info_for_device(db, run, device, at_us):

    # The device is either a peripheral or a client in this connection
    res = list(db(
        (db.conn_info.run == run) &
        (
                ((db.conn_info.client == device) & (db.conn_info.client_connection_success_us <= at_us) & ((db.conn_info.client_disconnect_us == None) | (db.conn_info.client_disconnect_us >= at_us)))
                | ((db.conn_info.peripheral == device) & (db.conn_info.peripheral_connection_success_us <= at_us) & ((db.conn_info.peripheral_disconnect_us == None) | (db.conn_info.peripheral_disconnect_us >= at_us)))
        )).select())

    assert len(res) == 1

    return res[0]



def handle_connections(db, run):
    # Select all conn_init calls:

    for e in iter_events_with_devices(db, run, 'conn_init'):
        db.conn_info.insert(**{
            "run": run,
            "client": e.device,
            "peripheral": find_device_by_eid(db, run, e.data['other_eid']),
            "client_rx_bytes": 0,
            "client_tx_bytes": 0,
            "peripheral_rx_bytes": 0,
            "peripheral_tx_bytes": 0,
            "client_channel_init_us": e.us
        })

    db.commit()

    def find_conn_event(device_a, other_mac, up_to_us):
        device_b = find_device_by_mac_addr(db, run, other_mac)

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
        for e in iter_events_with_devices(db, run, et):
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
        for e in iter_events_with_devices(db, run, et):
            other_mac_addr_prop = 'from_mac_addr' if et == 'rx' else 'to_mac_addr'
            (is_client, conn_ev) = find_conn_event(e.device, e['data'][other_mac_addr_prop], e['us'])
            assert conn_ev.client_channel_init_us < e['us']

            property = "{}_{}_bytes".format('client' if is_client else 'peripheral', et)

            conn_ev[property] += e['data']['num_bytes']

            db(db.conn_info.id == conn_ev).update(**{
                property: conn_ev[property]
            })

            db.commit()


    # Some assertions, safety first!
    print("Asserting connection info...")
    for conn_ev in db(db.conn_info.run == run).iterselect():
        # some timing assertions
        assert conn_ev.client_connection_success_us is None or conn_ev.client_connection_success_us >= conn_ev.client_channel_init_us

        assert conn_ev.client_disconnect_us is None or conn_ev.client_disconnect_us >= conn_ev.client_connection_success_us
        assert conn_ev.client_channel_up_us is None or conn_ev.client_channel_up_us >= conn_ev.client_connection_success_us
        assert conn_ev.client_channel_down_us is None or conn_ev.client_connection_success_us <= conn_ev.client_channel_down_us
        assert conn_ev.client_idle_disconnect_us is None or conn_ev.client_connection_success_us <= conn_ev.client_idle_disconnect_us <= conn_ev.client_disconnect_us
        assert conn_ev.client_channel_up_us is None or conn_ev.client_channel_down_us is None or conn_ev.client_channel_up_us <= conn_ev.client_channel_down_us

        assert conn_ev.peripheral_disconnect_us is None or conn_ev.peripheral_disconnect_us >= conn_ev.peripheral_connection_success_us
        assert conn_ev.peripheral_channel_up_us is None or conn_ev.peripheral_channel_up_us >= conn_ev.peripheral_connection_success_us
        assert conn_ev.peripheral_channel_down_us is None or conn_ev.peripheral_connection_success_us <= conn_ev.peripheral_channel_down_us
        assert conn_ev.peripheral_idle_disconnect_us is None or conn_ev.peripheral_connection_success_us <= conn_ev.peripheral_idle_disconnect_us <= conn_ev.peripheral_disconnect_us
        assert conn_ev.peripheral_channel_up_us is None or conn_ev.peripheral_channel_down_us is None or conn_ev.peripheral_channel_up_us <= conn_ev.peripheral_channel_down_us

        # each side should not receive more than what was transmitted
        assert conn_ev.client_rx_bytes <= conn_ev.peripheral_tx_bytes and conn_ev.peripheral_rx_bytes <= conn_ev.client_tx_bytes

        # and most importantly there should just be this one connection that lies within the timing bounds <success_us, disconnect_us> for both the client and the peripheral!

        # we check first for the client
        if conn_ev.client_connection_success_us:
            find_conn_info_for_device(db, run, conn_ev.client, conn_ev.client_connection_success_us)
        if conn_ev.client_disconnect_us:
            find_conn_info_for_device(db, run, conn_ev.client, conn_ev.client_disconnect_us)

        if conn_ev.peripheral_connection_success_us:
            find_conn_info_for_device(db, run, conn_ev.peripheral, conn_ev.peripheral_connection_success_us)
        if conn_ev.peripheral_disconnect_us:
            find_conn_info_for_device(db, run, conn_ev.peripheral, conn_ev.peripheral_disconnect_us)

    print("Done!")


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

def handle_bundles(db, run):

    # first handle bundle generation, those are created locally and are thus not the result of a reception
    for et in ['generate_fake_bundle', 'sv_bundle']:
        for e in iter_events(db, run, et):

            bundle = db['bundle'].insert(
                run=run,
                source=find_device_by_eid(db, run, e.data['source']),
                source_eid=e.data['source'],
                destination=find_device_by_eid(db, run, e.data['destination']),
                destination_eid=e.data['destination'],
                creation_timestamp_ms=e.data['creation_timestamp_ms'],
                payload_length=e.data['payload_length'],
                is_sv=et == 'sv_bundle',
                lifetime_ms=e.data['lifetime_ms'],
                hop_count=e.data['hop_count']
            )

            db.stored_bundle.insert(
                run=run,
                device=find_device_by_eid(db, run, e.data['source']),
                bundle=bundle,
                created_us=e['us'],
                local_id=e.data['local_id'],
                remaining_hops=e.data['hop_count']
            )

            db.commit()

    # we no handle all received bundles as we need to reference them in the following transmissions
    # "bundle_receive", "\"local_id\": %d, \"source\": \"%s\", \"destination\": \"%s\", \"creation_timestamp_ms\": %d"
    num_reception_events = 0
    for e in iter_events_with_devices(db, run, 'bundle_receive'):
        bundle = find_bundle(db, run, e.data['source'], e.data['destination'], e.data['creation_timestamp_ms'])

        db.stored_bundle.insert(
            run=run,
            device=e.device,
            bundle=bundle,
            created_us=e['us'],
            local_id=e.data['local_id']
        )
        num_reception_events += 1
        db.commit()

    # now handle expiration of bundles
    #"bundle_delete", "\"local_id\": %d, \"source\": \"%s\", \"destination\": \"%s\", \"creation_timestamp_ms\": %d"
    for e in iter_events_with_devices(db, run, 'bundle_delete'):
        stored_bundle = find_stored_bundle(db, run, e.device, e.data['local_id'], e.us)
        db(db.stored_bundle.id == stored_bundle).update(deleted_us=e.us)
        db.commit()


    # we then handle all bundle_transmissions
    # "send_bundle", "\"to_eid\": \"%s\", \"to_cla_addr\": \"%s\", \"bundle_id\": %d"

    num_receptions = 0
    for e in iter_events_with_devices(db, run, 'send_bundle'):
        conn_info = find_conn_info_for_device(db, run, e.device, e.us)
        is_client = conn_info.client.id == e.device.id
        stored_bundle = find_stored_bundle(db, run, e.device, e.data['bundle_id'], e.us)
        bundle = stored_bundle.bundle
        receive_stored_max_us = conn_info.peripheral_disconnect_us if is_client else conn_info.client_disconnect_us

        other_device = conn_info.peripheral if is_client else conn_info.client
        min_rx_us = conn_info.peripheral_connection_success_us if is_client else conn_info.client_connection_success_us
        max_rx_us = (conn_info.peripheral_disconnect_us if is_client else conn_info.client_disconnect_us) or run.simulation_time

        # we now search for the stored bundle on the receiver side
        res = list(db(
            (db.stored_bundle.run == run) &
            (db.stored_bundle.bundle == bundle) &
            (db.stored_bundle.device == other_device) &
            (db.stored_bundle.created_us >= min_rx_us) &
            (db.stored_bundle.created_us <= max_rx_us)
        ).select())

        assert len(res) <= 1

        if len(res) == 1:
            received_stored_bundle = res[0]
        else:
            received_stored_bundle = None


        if received_stored_bundle:
            num_receptions += 1
            end_us = received_stored_bundle.created_us
            assert db(db.bundle_transmission.received_stored_bundle == received_stored_bundle).count() == 0
            assert e.us <= end_us
        else:
            end_us = None
        # make sure that we send it to the correct device :)
        if is_client:
            assert e.data['to_eid'] == conn_info.peripheral.eid
        else:
            assert e.data['to_eid'] == conn_info.client.eid

        bundle_transmission = db.bundle_transmission.insert(
            run=run,
            conn_info=conn_info,
            source_stored_bundle=stored_bundle,
            received_stored_bundle=received_stored_bundle,
            start_us=e.us,
            end_us=end_us
        )



        db.commit()

    assert num_receptions == num_reception_events

    db.commit()
    #pprint(list(db(db.device).select()))


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
        handle_connections,
        handle_bundles
    ]


    runs = db(db.run.status == 'finished').iterselect()

    for run in runs:
        for h in handlers:
            h(db, run)