import argparse
import os
import dist_writer
from pymobility.mobility import random_waypoint
import dotenv
import os
import json
import sys
from pydal import DAL, Field
from utils import iter_nodes
import tables
from pprint import pprint

config = {
    **dotenv.dotenv_values(".env"),  # load shared development variables
    **dotenv.dotenv_values(".env.local"),  # load sensitive variables
    **os.environ,  # override loaded values with environment variables
}


def dist_time_iters_from_run(run_config):
    return dist_writer.model_to_iterators(
        int(run_config['SIM_PROXY_NUM_NODES']),
        run_config['SIM_MODEL'],
        json.loads(run_config['SIM_MODEL_OPTIONS'] or "{}"),
        int(run_config['SIM_RANDOM_SEED'])
    )

def contact_pairs_iter(dist_time_iter, max_us, max_dist):
    last_contact_start = None

    ts = 0
    while ts < max_us:
        ts, d = next(dist_time_iter)

        if d <= max_dist:
            if last_contact_start is None:
                last_contact_start = ts
        else:
            if last_contact_start is not None:
                yield (last_contact_start, ts)
                last_contact_start = None

    if last_contact_start is not None:
        yield (last_contact_start, max_us)


def extract_contact_pairs(dist_time_iters, max_us, max_dist):

    contact_pairs = {}
    cp_iters = {}
    for (a,b) in dist_time_iters:
        cp_iters[(a,b)] = contact_pairs_iter(dist_time_iters[(a,b)], max_us, max_dist)
        contact_pairs[(a,b)] = []

    still_looping = True
    while still_looping:
        still_looping = False
        for (a,b) in dist_time_iters:
            next_pair = next(cp_iters[(a,b)], None)
            if next_pair is not None:
                contact_pairs[(a,b)].append(next_pair)
                still_looping = True

    return contact_pairs

#
# def extract_contact_pairs(config, max_dist):
#     #num_proxy_nodes, model, model_options, rseedmax_us, max_dist):
#     dist_time_iters = dist_writer.model_to_iterators(
#         int(config['SIM_PROXY_NUM_NODES']),
#         config['SIM_MODEL'],
#         json.loads(config['SIM_MODEL_OPTIONS'] or "{}"),
#         int(config['SIM_RANDOM_SEED'])
#     )
#
#     max_us = int(float(config['SIM_LENGTH']))
#
#     us = 0
#     # we loop through all pairs at each timestamp
#     # for each pairs, we append a list of tuples that describe the start and end-date
#     cur_pairs = {}
#     nr_nodes = int(config['SIM_PROXY_NUM_NODES'])+1
#
#     contact_pairs = {}
#     for (a,b) in iter_nodes(nr_nodes):
#         contact_pairs[(a,b)] = []
#
#     still_looping = True
#     while still_looping:
#         still_looping = False
#
#         for (a,b) in iter_nodes(nr_nodes):
#             ts, d = next(dist_time_iters[(a,b)])
#
#             if ts > max_us:
#                 continue
#
#             still_looping = True
#
#             print(round(100*ts/max_us))
#
#             if d <= max_dist:
#                 if (a,b) not in cur_pairs:
#                     cur_pairs[(a,b)] = ts
#             else:
#                 if (a,b) in cur_pairs:
#                     start_us = cur_pairs.pop((a,b))
#                     contact_pairs[(a,b)].append((start_us, ts))
#
#     for (a,b) in iter_nodes(nr_nodes):
#         if (a,b) in cur_pairs:
#             start_us = cur_pairs.pop((a,b))
#             contact_pairs[(a,b)].append((start_us, max_us))
#
#     return contact_pairs


if __name__ == "__main__":
    logdir = config['SIM_LOG_DIR']
    os.makedirs(logdir, exist_ok=True)

    db = DAL("sqlite://sqlite.db", folder=logdir)

    tables.init_tables(db)
    tables.init_eval_tables(db)

    runs = list(db(db.run.status == 'finished').select())

    max_dist = 50.0 # TODO: Derive this based on the pair-wise advertisement reception and connection quality!
    for run in runs:
        print("Handling run {}".format(run.name))
        run_config = json.loads(run.configuration_json)

        run_config['SIM_PROXY_NUM_NODES'] = 99
        run_config['SIM_LENGTH'] = 3600000000

        max_us = int(float(run_config['SIM_LENGTH']))

        contact_pairs = extract_contact_pairs(dist_time_iters_from_run(run_config), max_us, max_dist)

        pprint(contact_pairs)


