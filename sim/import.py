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
    run_name = sys.argv[1]
    config['IMPORTED'] = True

    import_file_path = sys.argv[2]


    print("########################")
    print("Importing run {}".format(run_name))
    pprint(config)
    print("########################")


    logdir = config['SIM_LOG_DIR']
    os.makedirs(logdir, exist_ok=True)

    # Get access to the database (create if necessary!)
    db = DAL(config['SIM_DB_URI'], folder=logdir, attempts=30)

    tables.init_tables(db)


    run = db['run'].insert(**{
        "name": run_name, # we use the
        "group": config['SIM_GROUP'] if 'SIM_GROUP' in config and config['SIM_GROUP'] != "" else "",
        "start_ts": now,     # TODO This is not correct for imports
        "end_ts": None,      # TODO This is not correct for imports
        "status": "starting",
        "seed": "import",  # TODO This is not correct for imports
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

    with open(import_file_path, encoding='ISO-8859-1') as file:
        events = lines_to_event_iter(file)

        batch_size = 250 # the maximum amount of inserts per commit
        batch = []

        for e in events:
            assert e
            if not offset_us:
                offset_us = e['us']
            e['us'] -= offset_us
            e['run'] = run.id

            assert e['us'] >= 0
            batch.append(e)
            if len(batch) >= batch_size:
                db['event'].bulk_insert(batch)
                db.commit()
                batch = []

        if len(batch) > 0:
            db['event'].bulk_insert(batch)
            db.commit()

    db(db.run.id == run).update(
        status='finished',
        end_ts=datetime.now()
    )
    db.commit()
    print("DONE!")