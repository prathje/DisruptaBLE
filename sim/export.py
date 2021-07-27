import sys
import json
import dotenv
import os

from pprint import pprint
import sqlite3

from pydal import DAL, Field
import tables
import matplotlib.pyplot as plt
import numpy as np

config = {
    **dotenv.dotenv_values(".env"),  # load shared development variables
    **dotenv.dotenv_values(".env.local"),  # load sensitive variables
    **os.environ,  # override loaded values with environment variables
}

def run_in(runs):
    s = "run IN ("
    s += ", ".join([str(r.id) for r in runs])
    s += ")"
    return s


def export_pair_packets(db, base_path):

    res = db.executesql('''
        SELECT
        r.id, COUNT(DISTINCT b.id)
        FROM run r 
        LEFT JOIN bundle_transmission bt ON bt.run = r.id
        LEFT JOIN stored_bundle sb ON sb.id = bt.source_stored_bundle
        LEFT JOIN bundle b ON sb.bundle = b.id AND b.destination_eid = "dtn://fake"
        GROUP BY r.id
        ORDER BY r.name ASC
    ''')

    data = {}

    for r in res:
        run = db.run[r[0]]
        config = json.loads(run.configuration_json)
        model_options = json.loads(config['SIM_MODEL_OPTIONS'])

        k = round(model_options['distance'])
        if k not in data:
            data[k] = []
        data[k].append(r[1])

    sorted_keys = sorted(data.keys())

    avg = []

    for k in sorted_keys:
        assert len(data[k])
        avg.append(sum(data[k]) / len(data[k]))


    pprint(sorted_keys)
    pprint(avg)

    # TODO: Calculate error bars and export as graph!

    pass

def export_pair_timings(db, base_path):

    # ONLY times for the source node!
    # AVG: advertising (the time without an active connection)
    # AVG: conn_init -> channel_up_us
    # AVG: channel_up_us -> channel_down_us (of which bundle and sv transmissions? -> just use the direction source -> proxy
    # AVG: channel_disconnect -> conn_init


    # AVG idle/advertisement time


    res = db.executesql('''
        SELECT
        r.id, ci.id, ci.client_conn_init_us,
        MIN(ci.client_channel_up_us, ci.peripheral_channel_up_us),
        MIN(ci.client_connection_success_us, ci.peripheral_connection_success_us),
        MIN(COALESCE(ci.client_channel_down_us, r.simulation_time), COALESCE(ci.peripheral_channel_down_us, r.simulation_time)),
        MIN(COALESCE(ci.client_disconnect_us, r.simulation_time), COALESCE(ci.peripheral_disconnect_us, r.simulation_time)),
        MAX(ci.client_channel_up_us, ci.peripheral_channel_up_us),
        MAX(ci.client_connection_success_us, ci.peripheral_connection_success_us),
        MAX(COALESCE(ci.client_channel_down_us, r.simulation_time), COALESCE(ci.peripheral_channel_down_us, r.simulation_time)),
        MAX(COALESCE(ci.client_disconnect_us, r.simulation_time), COALESCE(ci.peripheral_disconnect_us, r.simulation_time))
        FROM run r
        JOIN conn_info ci ON ci.run = r.id
        WHERE (ci.client_channel_up_us + ci.peripheral_channel_up_us + ci.client_connection_success_us + ci.peripheral_connection_success_us) IS NOT NULL 
    ''')

    pprint(res)
    # TODO: Calculate error bars and export as graph!

    pass

def export_rssi_per_distance(db, base_path):

    # SELECT * FROM distance_pair WHERE device_a = 326 AND device_b = 327 AND us = FLOOR(2028932/1000000)*1000000
    '''
    SELECT ROUND(d) as de, AVG(rssi) FROM (
SELECT adv.id, adv.received_us, adv.rssi, dp.d + (dp.d_next-dp.d)* ((adv.received_us-dp.us)/(dp.us_next-dp.us)) as d
FROM advertisements adv
LEFT JOIN run r ON r.id = adv.run
LEFT JOIN distance_pair dp ON dp.device_a = adv.sender AND dp.device_b = adv.receiver AND dp.us = FLOOR(adv.received_us/1000000)*1000000
WHERE r.status = 'finished' LIMIT 10000) as a
GROUP BY de
    '''
    pass

def export_bundle_transmission_success_per_distance(db, base_path):
    '''
 SELECT ROUND(d) as de, AVG(rssi) FROM (
SELECT adv.id, adv.received_us, adv.rssi, dp.d + (dp.d_next-dp.d)* ((adv.received_us-dp.us)/(dp.us_next-dp.us)) as d
FROM advertisements adv
LEFT JOIN run r ON r.id = adv.run
LEFT JOIN distance_pair dp ON dp.device_a = adv.sender AND dp.device_b = adv.receiver AND dp.us = FLOOR(adv.received_us/1000000)*1000000
WHERE r.status = 'finished' LIMIT 10000) as a
GROUP BY de
 '''
    pass

if __name__ == "__main__":

    logdir = config['SIM_LOG_DIR']
    export_dir = config['SIM_EXPORT_DIR']
    os.makedirs(logdir, exist_ok=True)
    os.makedirs(export_dir, exist_ok=True)

    db = DAL(config['SIM_DB_URI'], folder=logdir)

    tables.init_tables(db)
    tables.init_eval_tables(db)

    db.commit() # we need to commit

    exports = [
        export_pair_packets,
        export_pair_timings
    ]

    for e in exports:
        print("Handling {}".format(e.__name__))
        file_prefix = e.__name__[len("export_"):] + "_"
        base_path = os.path.join(export_dir, file_prefix)
        e(db, base_path)