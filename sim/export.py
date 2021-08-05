import json
import os

from pprint import pprint

from pydal import DAL, Field
import tables
import numpy as np
import math

from dist_eval import extract_contact_pairs, dist_time_iters_from_run

import matplotlib.pyplot as plt
from export_utility import slugify, cached, init_cache, load_env_config


METHOD_PREFIX = 'export_'

CONFIDENCE_FILL_COLOR = '0.8'
COLOR_MAP = 'tab10'

def load_plot_defaults():
    # Configure as needed
    plt.rc('lines', linewidth=2.0)
    plt.rc('legend', framealpha=1.0, fancybox=True)
    plt.rc('errorbar', capsize=3)
    plt.rc('pdf', fonttype=42)
    plt.rc('ps', fonttype=42)
    plt.rc('font', size=11)




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

    runs = db((db.run.status == 'processed') & (db.run.group == 'app')).select()

    overall_limit = 5000
    overall_data = []


    def handle_adv_data(name, data):
        max_dist = 200

        xs = range(0, max_dist+1)

        per_dist = [[] for x in xs]

        for d in data:
            dist = round(d[1])
            if dist <= max_dist:
                per_dist[dist].append(d[0])

        per_dist_mean = [np.nanmean(vals) for vals in per_dist]
        per_dist_lq = [np.nanpercentile(vals, 2.5) for vals in per_dist]
        per_dist_uq = [np.nanpercentile(vals, 97.5) for vals in per_dist]

        plt.clf()
        plt.plot(xs, per_dist_mean, linestyle='-', label="Mean", color='C1')
        plt.fill_between(xs, per_dist_lq, per_dist_uq, color=CONFIDENCE_FILL_COLOR, label='95% Confidence Interval')
        plt.legend()
        plt.xlabel("Distance [m]")
        plt.ylabel("RSSI [dBm]")
        plt.axis([0, max_dist, -100, -40])
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(export_dir + slugify(name) + ".pdf", format="pdf")
        plt.close()


    for r in runs:
        name = slugify(("rssi per distance", str(r.name), str(r.id), str(overall_limit)))
        print("Handling {}".format(name))

        def proc():
            limit = 1000   # batch processing slows down everything right now
            offset = 0

            data = []

            while True:
                rows = db.executesql('''
                    SELECT adv.rssi as rssi, dp.d + (dp.d_next-dp.d)* ((adv.received_us-dp.us)/(dp.us_next-dp.us)) as d
                    FROM advertisements adv
                    JOIN distance_pair dp ON dp.run = adv.run AND dp.device_a = adv.sender AND dp.device_b = adv.receiver AND dp.us = FLOOR(adv.received_us/1000000)*1000000
                    WHERE adv.run = {} LIMIT {} OFFSET {}
                '''.format(r.id, limit, offset))

                # rows = db.executesql('''
                #     SELECT adv.rssi as rssi, adv.received_us, pr.pa_x, pr.pa_y, pr.pb_x, pr.pb_y, pr.pc_x, pr.pc_y, pr.pd_x, pr.pd_y
                #     FROM advertisements adv
                #     JOIN pos_pair pr ON pr.run = adv.run AND pr.device_a = adv.sender AND pr.device_b = adv.receiver AND pr.us = FLOOR(adv.received_us/1000000)*1000000
                #     WHERE adv.run = {} LIMIT {} OFFSET {}
                # '''.format(r.id, limit, offset))

                for row in rows:
                    if len(data) < overall_limit:
                        data.append(row)

                if len(data) == overall_limit:
                    break

                offset += limit

                if len(rows) < limit:
                    break

            return data

        data = cached(name, proc)
        handle_adv_data(name, data)

        overall_data += data

    handle_adv_data(slugify("RSSI per Distance (overall)"), overall_data)

    # SELECT * FROM distance_pair WHERE device_a = 326 AND device_b = 327 AND us = FLOOR(2028932/1000000)*1000000

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


    for r in runs:

        run_config = json.loads(r.configuration_json)
        name = slugify(("epidemic propagation", str(r.name), str(r.id)))

        def proc():
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
            return run_reception_steps

        run_reception_steps = cached(name, proc)
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

    for r in runs:
        run_config = json.loads(r.configuration_json)
        name = slugify(("direct propagation", str(r.name), str(r.id)))

        def proc():
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
            return run_reception_steps

        run_reception_steps = cached(name, proc)
        run_reception_steps = np.array(run_reception_steps, dtype=np.float64)

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
        plt.savefig(base_path + name + ".pdf", format="pdf")
        plt.close()


def export_ict(db, base_path):

    runs = db((db.run.status == 'processed') & (db.run.group == 'app')).select()


    for max_dist in [50,100]:
        for r in runs:
            name = slugify(("ict", str(max_dist), str(r.name), str(r.id)))

            run_config = json.loads(r.configuration_json)
            max_s = math.floor(r.simulation_time/1000000)

            def proc():
                # build ict map
                contact_pairs = extract_contact_pairs(dist_time_iters_from_run(run_config), r.simulation_time, max_dist)

                s = []

                for (a,b) in contact_pairs:
                    for (start, end) in contact_pairs[(a,b)]:
                        s.append((end-start)/1000000)

                xs = []
                for t in range(0, max_s+1, 1):
                    p =  len([x for x in s if x > t]) / len(s)
                    xs.append(p)
                return np.array(xs, dtype=np.float64)


            xs = cached(name, proc)

            # Export one graph per run for now
            positions = range(0, max_s + 1)
            plt.clf()

            plt.plot(positions, xs, linestyle='-', label="ICT")
            plt.legend()
            # plt.title("Chaos Network Size")
            plt.xlabel("Time")
            plt.ylabel('P(X>x)')
            plt.axis([None, None, None, None])
            plt.grid(True)
            plt.tight_layout()
            plt.savefig(base_path + name + ".pdf", format="pdf")
            plt.close()




def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return text


if __name__ == "__main__":
    config = load_env_config()

    load_plot_defaults()

    logdir = config['SIM_LOG_DIR']
    export_dir = config['SIM_EXPORT_DIR']
    export_cache_dir = config['SIM_EXPORT_CACHE_DIR']
    os.makedirs(logdir, exist_ok=True)

    assert 'SIM_EXPORT_DIR' in config and config['SIM_EXPORT_DIR']

    if 'SIM_EXPORT_CACHE_DIR' in config and config['SIM_EXPORT_CACHE_DIR']:
        init_cache(config['SIM_EXPORT_CACHE_DIR'])

    db = DAL(config['SIM_DB_URI'], folder=logdir)

    tables.init_tables(db)
    tables.init_eval_tables(db)

    db.commit() # we need to commit

    exports = [
        export_rssi_per_distance,
        export_fake_bundle_propagation_epidemic,
        export_fake_bundle_propagation_direct,
        export_ict,
    ]

    for step in exports:
        name = remove_prefix(step.__name__, METHOD_PREFIX)
        print("Handling {}".format(name))
        export_dir = os.path.join(config['SIM_EXPORT_DIR'], name) + '/'
        os.makedirs(export_dir, exist_ok=True)
        step(db, export_dir)