import sys
import json
import dotenv
import os
import random
import dist_writer
import traceback

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

if __name__ == "__main__":

    groups = None

    if len(sys.argv) >= 2:
        print("Using group {}".format(sys.argv[1]))
        groups = [sys.argv[1]]

    exp_dir = config['SIM_TO_ENV_CONVERSION_PATH']
    os.makedirs(exp_dir, exist_ok=True)

    logdir = config['SIM_LOG_DIR']
    os.makedirs(logdir, exist_ok=True)

    db = DAL(config['SIM_DB_URI'], folder=logdir)

    tables.init_tables(db)

    # we reset everything for testing purposes
    tables.init_eval_tables(db)
    db.commit()

    if not groups:
        res = db.executesql('''
                SELECT
                r.group
                FROM run r
                GROUP BY r.group
            ''')

        groups = [r[0] for r in res]
        print(groups)

    runs = db((db.run.group.belongs(groups) & (db.run.id < 400))).iterselect()

    for run in runs:
        name = "{}-{}".format(run.id, run.name)
        print("Handling run " + name)

        run_config = json.loads(run.configuration_json)

        with open(os.path.join(exp_dir, name + ".env"), "w") as f:  # Opens file and casts as f
            for k in run_config:
                if k.startswith("SIM_") or k.startswith("CONFIG_") or k.startswith("PROXY_CONFIG_") or k.startswith("SOURCE_CONFIG_"):
                    val = str(run_config[k])
                    if not val.startswith('"') or not val.endswith('"'):
                        if k in ['SIM_MODEL_OPTIONS']:
                            val = "'{}'".format(val)
                        else:
                            val = "\"{}\"".format(val)
                    f.write("{}={}\n".format(k, val))

    print("Finished! \\o/")
