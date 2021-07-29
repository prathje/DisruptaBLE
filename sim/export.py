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
import math

config = {
    **dotenv.dotenv_values(".env"),  # load shared development variables
    **dotenv.dotenv_values(".env.local"),  # load sensitive variables
    **os.environ,  # override loaded values with environment variables
}


CONFIDENCE_FILL_COLOR = '0.8'
COLOR_MAP = 'tab10'

def configure_plots():
    plt.rc('lines', linewidth=2.5)
    plt.rc('legend', framealpha=1.0, fancybox=True)
    plt.rc('errorbar', capsize=3)
    font = {'size': '12'}
    plt.rc('font', **font)

configure_plots()

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
JOIN run r ON r.id = adv.run
JOIN distance_pair dp ON dp.device_a = adv.sender AND dp.device_b = adv.receiver AND dp.us = FLOOR(adv.received_us/1000000)*1000000
WHERE r.status = 'finished' LIMIT 10000) as a
GROUP BY de
    '''
    pass

def export_bundle_transmission_success_per_distance(db, base_path):
    '''
SELECT ROUND(d/5)*5 as de, AVG(end_us IS NOT NULL) FROM (

SELECT bt.*, dp.d + (dp.d_next-dp.d)* ((bt.start_us-dp.us)/(dp.us_next-dp.us)) as d

FROM bundle_transmission bt
JOIN stored_bundle ssb ON ssb.id = bt.source_stored_bundle
JOIN conn_info ci ON ci.id = bt.conn_info
JOIN bundle b ON b.id = ssb.bundle AND b.destination_eid = 'dtn://fake' AND b.is_sv = 'F'
JOIN run r ON r.id = bt.run
JOIN distance_pair dp ON dp.device_a = ci.client AND dp.device_b = ci.peripheral AND dp.us = FLOOR(bt.start_us/1000000)*1000000
WHERE r.status = 'finished' LIMIT 10000) as a
GROUP BY de
 '''
    pass

def export_bundle_transmission_time_per_distance(db, base_path):
    '''
SELECT ROUND(d/5)*5 as de, AVG(end_us-start_us)/1000000 FROM (

SELECT bt.*, dp.d + (dp.d_next-dp.d)* ((bt.start_us-dp.us)/(dp.us_next-dp.us)) as d

FROM bundle_transmission bt
JOIN stored_bundle ssb ON ssb.id = bt.source_stored_bundle
JOIN conn_info ci ON ci.id = bt.conn_info
JOIN bundle b ON b.id = ssb.bundle AND b.b.destination_eid = 'dtn://fake' AND b.is_sv = 'F'
JOIN run r ON r.id = bt.run
JOIN distance_pair dp ON dp.device_a = ci.client AND dp.device_b = ci.peripheral AND dp.us = FLOOR(bt.start_us/1000000)*1000000
WHERE r.status = 'finished') as a
GROUP BY de
 '''
    pass


def export_fake_bundle_propagation_epidemic(db, base_path):

    length_s = 3000
    step = 1.0


    runs = db((db.run.status == 'processed') & (db.run.group == 'app')).select()


    max_step = math.ceil(length_s/step)


    num_bundles = 0
    for r in runs:

        run_reception_steps = []

        # & (db.bundle.creation_timestamp_ms <= ((r.simulation_time/1000)-(length_s*1000)))
        bundles = db((db.bundle.run == r) & (db.bundle.destination_eid == 'dtn://fake')).iterselect()
        for b in bundles:
            # TODO: this creation time is currently needed due to formatting bugs.. see f602e6d6d909aff4cd89ee371b4d955fb61ce7ef
            b_creation_time_ms = (db.executesql(
                '''
                    SELECT MIN(created_us) FROM stored_bundle
                    WHERE device = {} AND bundle = {}
                    GROUP BY bundle
                '''.format(b.source, b.id)
            )[0][0]) / 1000

            if b_creation_time_ms > ((r.simulation_time/1000)-(length_s*1000)):
                continue    # this bundle is too late


            receptions_steps = [0]*(max_step+1)
            num_bundles += 1

            res = db.executesql(
                '''
                    SELECT us, receiver_eid = destination_eid FROM bundle_reception
                    WHERE bundle = {}
                    ORDER BY us ASC
                '''.format(b.id)
            )

            for row in res:
                ms = (row[0]/1000)-b_creation_time_ms #b.creation_timestamp_ms

                ts = round((ms/1000) / step)

                for x in range(ts, max_step+1):
                    receptions_steps[x] += 1

            run_reception_steps.append(receptions_steps)

        run_config = json.loads(r.configuration_json)

        run_reception_steps = np.array(run_reception_steps, dtype=np.float64)
        run_reception_steps = run_reception_steps / (float(run_config['SIM_PROXY_NUM_NODES']))

        print(r.id)
        print(r.name)
        run_reception_steps = np.swapaxes(run_reception_steps, 0, 1) # we swap the axes to get all t=0 values at the first position together


        # Export one graph per run for now
        positions = range(0, max_step+1)
        plt.clf()

        mean = np.mean(run_reception_steps, axis=1)
        plt.plot(positions, mean, linestyle='-', label="Mean")
        (lq, uq) = np.percentile(run_reception_steps, [2.5, 97.5], axis=1)

        plt.fill_between(positions, lq, uq, color=CONFIDENCE_FILL_COLOR, label='95% Confidence Interval')

        plt.legend()
        # plt.title("Chaos Network Size")
        plt.xlabel("Time")
        plt.ylabel('Bundle Reception Rate')
        plt.axis([None, None, None, None])
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(base_path + str(r.name) + str(r.id) + ".pdf", format="pdf")
        plt.close()



def export_fake_bundle_propagation_direct(db, base_path):

    length_s = 3000
    step = 1.0

    runs = db((db.run.status == 'processed') & (db.run.group == 'app')).select()

    max_step = math.ceil(length_s/step)

    num_bundles = 0
    for r in runs:

        run_reception_steps = []
        # & (db.bundle.creation_timestamp_ms <= ((r.simulation_time/1000)-(length_s*1000)))
        bundles = db((db.bundle.run == r) & (db.bundle.destination_eid == 'dtn://source')).iterselect()
        for b in bundles:
            # TODO: this creation time is currently needed due to formatting bugs.. see f602e6d6d909aff4cd89ee371b4d955fb61ce7ef
            b_creation_time_ms = (db.executesql(
                '''
                    SELECT MIN(created_us) FROM stored_bundle
                    WHERE device = {} AND bundle = {}
                    GROUP BY bundle
                '''.format(b.source, b.id)
            )[0][0]) /  1000

            if b_creation_time_ms > ((r.simulation_time/1000)-(length_s*1000)):
                continue    # this bundle is too late

            receptions_steps = [0]*(max_step+1)
            num_bundles += 1

            res = db.executesql(
                '''
                    SELECT us FROM bundle_reception
                    WHERE bundle = {} AND receiver_eid = destination_eid
                    ORDER BY us ASC
                '''.format(b.id)
            )

            for row in res:
                ms = (row[0]/1000)-b_creation_time_ms #b.creation_timestamp_ms

                ts = round((ms/1000) / step)

                for x in range(ts, max_step+1):
                    receptions_steps[x] += 1

            run_reception_steps.append(receptions_steps)


        run_config = json.loads(r.configuration_json)

        run_reception_steps = np.array(run_reception_steps, dtype=np.float64)

        print(r.id)
        print(r.name)
        run_reception_steps = np.swapaxes(run_reception_steps, 0,
                                          1)  # we swap the axes to get all t=0 values at the first position together

        # Export one graph per run for now
        positions = range(0, max_step + 1)
        plt.clf()

        mean = np.mean(run_reception_steps, axis=1)
        plt.plot(positions, mean, linestyle='-', label="Mean")
        (lq, uq) = np.percentile(run_reception_steps, [2.5, 97.5], axis=1)

        plt.fill_between(positions, lq, uq, color=CONFIDENCE_FILL_COLOR, label='95% Confidence Interval')

        plt.legend()
        # plt.title("Chaos Network Size")
        plt.xlabel("Time")
        plt.ylabel('Bundle Reception Rate')
        plt.axis([None, None, None, None])
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(base_path + str(r.name) + str(r.id) + ".pdf", format="pdf")
        plt.close()


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
        #export_pair_packets,
        #export_pair_timings
        export_fake_bundle_propagation_direct,
        #export_fake_bundle_propagation_epidemic
    ]

    for e in exports:
        print("Handling {}".format(e.__name__))
        file_prefix = e.__name__[len("export_"):] + "_"
        base_path = os.path.join(export_dir, file_prefix)
        e(db, base_path)