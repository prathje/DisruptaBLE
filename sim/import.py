import dotenv
import os
import subprocess
import sys
import re
import threading
import json
import time
import random
from pydal import DAL, Field
from datetime import datetime
import queue
import dist_writer
import uuid
from pprint import pprint
from io import open

import tables

config = {
    **dotenv.dotenv_values(".env"),  # load shared development variables
    **dotenv.dotenv_values(".env.local"),  # load sensitive variables
    **os.environ,  # override loaded values with environment variables
}


event_re = re.compile(r"(\d+)\tID:(\d+)\tEVENT\s([^\s]+)\s(\{.+\})")
error_re = re.compile(r"(\d+)\tID:(\d+)(.*(?:not|error|fail|invalid|warning|broken).*)", re.IGNORECASE)


def lines_to_event_iter(lines):
    for line in lines:
        re_match = event_re.match(line.rstrip())
        #print(line.rstrip())
        if re_match:
            ts, device, event_type, data_str = re_match.groups()

            try:
                data = json.loads(data_str)
            except:
                print(line.rstrip())
                yield None
                return

            overall_us = int(ts)

            yield {
                "device": int(device),
                "us": overall_us,
                "type": event_type,
                "data_json": data_str
            }
        else:
            error_match = error_re.match(line.rstrip())
            if error_match:
                ts, device, error_str = error_match.groups()
                # time format: "00:00:00.010328"
                overall_us = int(ts)
                #print(overall_us, line.rstrip())
                yield {
                    "device": int(device),
                    "us": overall_us,
                    "type": "error",
                    "data_json": json.dumps({"msg": error_str})
                }

if __name__ == "__main__":

    assert len(sys.argv) == 3
    now = datetime.now()

    # auto generate missing env parameters

    config['SIM_NAME'] = sys.argv[1]
    group_name = sys.argv[1]
    config['IMPORTED'] = True
    config['SIM_RANDOM_SEED'] = "0"

    import_file_path = sys.argv[2]

    run_name = os.path.splitext(os.path.basename(import_file_path))[0]


    print("########################")
    print("Importing run {} for group {}".format(run_name, group_name))
    pprint(config)
    print("########################")


    logdir = config['SIM_LOG_DIR']
    os.makedirs(logdir, exist_ok=True)

    # Get access to the database (create if necessary!)
    db = DAL(config['SIM_DB_URI'], folder=logdir, attempts=30)

    tables.init_tables(db)


    run = db['run'].insert(**{
        "name": run_name, # we use the filename
        "group": group_name,
        "start_ts": now,     # TODO This is not correct for imports
        "end_ts": None,      # TODO This is not correct for imports
        "status": "starting",
        "seed": "0",  # TODO This is not correct for imports
        "simulation_time": int(float(config['SIM_LENGTH'])),  # TODO This is not correct for imports
        "progress": 0,  # TODO This is not correct for imports
        "num_proxy_devices": int(config['SIM_PROXY_NUM_NODES']), # TODO This is not correct for imports
        "configuration_json": json.dumps(config)
    })

    db.commit() # directly insert the run

    db(db.run.id == run).update(
        status='importing'
    )
    db.commit()

    offset_us = None
    
    max_us = 0

    with open(import_file_path, encoding='ISO-8859-1') as file:
        events = lines_to_event_iter(file)

        batch_size = 250 # the maximum amount of inserts per commit
        batch = []

        for e in events:
            assert e
            device = e['device']

            if not offset_us:
                if e['type'] == 'ml2cap_init':
                    offset_us = e['us']
                else:
                    print(e)
                    continue # we ignore this entry!

            e['us'] -= offset_us
            e['run'] = run.id

            if e['us'] > int(float(config['SIM_LENGTH'])):
                continue # we ignore entries beyond our experiment length
                
            assert e['us'] >= 0
            batch.append(e)

            max_us = max(max_us, e['us'])

            if len(batch) >= batch_size:
                db['event'].bulk_insert(batch)
                db.commit()
                batch = []

        if len(batch) > 0:
            db['event'].bulk_insert(batch)
            db.commit()

    print("Ignored {} overflow seconds".format(max(0, int((max_us-run.simulation_time)/1000000)))

    db(db.run.id == run).update(
        status='finished',
        #simulation_time= int(float(config['SIM_LENGTH'])),
        end_ts=datetime.now()
    )
    db.commit()
    print("DONE!")