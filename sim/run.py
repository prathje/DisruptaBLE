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

import tables

config = {
    **dotenv.dotenv_values(".env"),  # load shared development variables
    **dotenv.dotenv_values(".env.local"),  # load sensitive variables
    **dotenv.dotenv_values("run.env"),  # run specific variables TODO: Make this configurable?
    **os.environ,  # override loaded values with environment variables
}

def compile_and_move(rdir, exec_name, overlay_config):
    # TODO allow to skip compilation?
    bdir = os.path.join(rdir, "build", exec_name)

    west_build_command =  "west build -b nrf52_bsim {} --build-dir {} --pristine auto -- -DOVERLAY_CONFIG={}".format(config['SIM_SOURCE_DIR'], bdir, overlay_config)

    subprocess.run(west_build_command, shell=True, check=True)

    # Move resulting executable to main folder
    os.rename(
        os.path.join(bdir, "zephyr", "zephyr.exe"),
        os.path.join(config['BSIM_OUT_PATH'], "bin", exec_name)
    )

def spawn_node_process(exec_name, id, additional_args=[]):

    exec_path = os.path.join(config['BSIM_OUT_PATH'], "bin", exec_name)

    if 'SIM_VALGRIND_SOURCE' in config and int(config['SIM_VALGRIND_SOURCE']) and id == 0:
        additional_args_str = " ".join(additional_args)
        exec_cmd = "valgrind --leak-check=full --show-leak-kinds=all --track-origins=yes --verbose --log-file=valgrind-out.txt " + exec_path + ' -s=' + config['SIM_NAME'] +  ' -d=' + str(id) + " " + additional_args_str
        print(exec_cmd)

        process = subprocess.Popen(exec_cmd, shell=True, text=True,
                                 stdout=subprocess.PIPE,
                                 bufsize=1,
                                 stderr=sys.stderr,
                                 encoding="ISO-8859-1")
    else:
        process = subprocess.Popen([exec_path, '-s=' + config['SIM_NAME'], '-d=' + str(id)] + additional_args,
                                   cwd=config['BSIM_OUT_PATH']+"/bin",
                                   text=True,
                                   stdout=subprocess.PIPE,
                                   bufsize=1,
                                   stderr=sys.stderr,
        encoding="ISO-8859-1")

    return process


event_re = re.compile(r"d\_(\d+):\s\@(\d\d:\d\d:\d\d\.\d+)\s\sEVENT\s([^\s]+)\s(.+)")

def output_to_event_iter(o):
    global max_us
    for line in o:
        re_match = event_re.match(line.rstrip())
        #print(line.rstrip())
        if re_match:
            device, ts, event_type, data_str = re_match.groups()
            try:
                data = json.loads(data_str)
            except:
                print(line.rstrip())
                yield None
                return

            # time format: "00:00:00.010328"
            h = int(ts[0:2])
            m = int(ts[3:5])
            s = int(ts[6:8])
            us = int(ts[9:])

            overall_us = us + 1000000 * (s+60*m+3600*h)

            #print(overall_us, line.rstrip())

            yield {
                "device": int(device),
                "us": overall_us,
                "type": event_type,
                "data_json": data_str
            }

if __name__ == "__main__":

    now = datetime.now()

    for i in range(1, len(sys.argv)):
        if not os.path.isfile(sys.argv[i]):
            print("Could not load env file {}".format(sys.argv[i]))
            exit(1)

        param_override = dotenv.dotenv_values(sys.argv[i])

        for k in param_override:
            config[k] = param_override[k]

    # auto generate missing env parameters

    if config['SIM_NAME'] == "":
        config['SIM_NAME'] = str(uuid.uuid1())
        fixed_sim_name = False
    else:
        fixed_sim_name = True
    if config['SIM_RANDOM_SEED'] == "":
        config['SIM_RANDOM_SEED'] = round(time.time())


    run_name = config['SIM_NAME']
    print("########################")
    print("Starting run {}".format(run_name))
    pprint(config)
    print("########################")

    logdir = config['SIM_LOG_DIR']

    os.makedirs(logdir, exist_ok=True)

    # Get access to the database (create if necessary!)
    db = DAL("sqlite://sqlite.db", folder=logdir)

    tables.init_tables(db)


    rseed = int(config['SIM_RANDOM_SEED'])
    random.seed(rseed)

    run = db['run'].insert(**{
        "name": run_name,
        "group": config['SIM_GROUP'] if 'SIM_GROUP' in config and config['SIM_GROUP'] != "" else None,
        "start_ts": now,
        "end_ts": None,
        "status": "starting",
        "seed": rseed,
        "simulation_time": int(float(config['SIM_LENGTH'])),
        "progress": 0,
        "num_proxy_devices": int(config['SIM_PROXY_NUM_NODES']),
        "configuration_json": json.dumps(config)
    })

    db.commit() # directly insert the run

    # Create the parent run directory
    #os.makedirs(config['SIM_RUN_DIRECTORY'], exist_ok=True)
    rdir = os.path.join("/tmp/sim", run_name)

    os.makedirs(rdir, exist_ok=True)

    compile_and_move(rdir, run_name+"_source", config['SIM_OVERLAY_CONFIG_SOURCE'])
    compile_and_move(rdir, run_name+"_proxy", config['SIM_OVERLAY_CONFIG_PROXY'])

    subprocess.run("${BSIM_COMPONENTS_PATH}/common/stop_bsim.sh || 1", shell=True, check=True)

    node_processes = []

    node_processes.append(
        spawn_node_process(run_name+"_source", len(node_processes))
    )

    for i in range(0, int(config['SIM_PROXY_NUM_NODES'])):
        node_processes.append(
            spawn_node_process(run_name+"_proxy", len(node_processes))
        )

    wifi_interference_proceses = []
    for i in range(2, 13, 2):
        wifi_interference_proceses.append(
            spawn_node_process(
                "bs_device_2G4_WLAN_actmod",
                len(node_processes)+len(wifi_interference_proceses),
                [
                    "-ConfigSet={}".format(int(config['SIM_WIFI_INTERFERENCE'])),
                    "-channel={}".format(i)
                ]
            )
        )


    model = config['SIM_MODEL']
    model_options = {}

    if 'SIM_MODEL_OPTIONS' in config and config['SIM_MODEL_OPTIONS']:
        model_options = json.loads(config['SIM_MODEL_OPTIONS'])

    dist_dir = os.path.join(rdir, "distances")
    os.makedirs(dist_dir, exist_ok=True)
    dist_file_path = dist_writer.start(dist_dir, int(config['SIM_PROXY_NUM_NODES']), rseed, model, model_options)

    num_overall_devices = len(node_processes)+len(wifi_interference_proceses)
    phy_exec_path = os.path.join(config['BSIM_OUT_PATH'], "bin", "bs_2G4_phy_v1")

    phy_process = subprocess.Popen([phy_exec_path,
                                    '-s='+config['SIM_NAME'],
                                    '-sim_length='+config['SIM_LENGTH'],
                                    '-D='+str(num_overall_devices),
                                    '-rs='+str(int(rseed)),
                                    '-defmodem=BLE_simple',
                                    '-channel=Indoorv1',
                                    '-argschannel',
                                    '-preset=Huge3',
                                    '-speed=1.1',
                                    '-dist=' + dist_file_path,
                                    '-at='+str(int(config['SIM_FIXED_ATTENUATION']))
                                    ],
                                   cwd=config['BSIM_OUT_PATH']+"/bin",
       encoding="ISO-8859-1",
        stdout=sys.stdout,
       bufsize=1,
        stderr=sys.stderr
    )

    db(db.run.id == run).update(
        status='started'
    )
    db.commit()

    max_us = -1

    event_queue_size = 250

    event_queue = queue.Queue(maxsize=event_queue_size)

    def process_events(p):
        global max_us

        for e in output_to_event_iter(p.stdout):
            e['run'] = run_name
            if e['us'] > max_us:
                max_us = e['us']
                print(max_us/1000000)

            e['run'] = run
            event_queue.put(e)

    log_threads = []
    for p in node_processes:
        t = threading.Thread(target=process_events, args=(p,))
        t.start()
        log_threads.append(t)

    commit_thread_running = True

    def commit_thread():
        while commit_thread_running:

            #print("event_queue.qsize()")
            #print(event_queue.qsize())

            db(db.run.id == run).update(
                progress=max_us
            )

            batch_size = event_queue_size # the maximum amount of inserts per commit
            events = []

            try:
                while batch_size > 0:
                    ev = event_queue.get_nowait()
                    events.append(ev)
                    event_queue.task_done()
                    batch_size -= 1
            except queue.Empty:
                pass

            if len(events) > 0:
                db['event'].bulk_insert(events)

            if event_queue.qsize() == 0:
                # seems like there are not really many events for us to process atm
                time.sleep(0.5)  # sleep 5 secs
            db.commit()

    commit_thread = threading.Thread(target= commit_thread, args=(), daemon=True)
    commit_thread.start()

    done = False
    while not done:
        done = True
        for p in [phy_process]+node_processes:
            if p.poll() is None:
                done = False
        time.sleep(5.0)  # sleep 5 secs

    for t in log_threads:
        t.join()

    for p in [phy_process]+node_processes+wifi_interference_proceses:
        p.wait()

    event_queue.join()

    commit_thread_running = False
    commit_thread.join()

    success = True
    for p in [phy_process]+node_processes:
        if p.returncode != 0:
            success = False
            print("Got weird response code: "+ str(p.returncode))

    db(db.run.id == run).update(
        status='finished' if success else 'error',
        end_ts=datetime.now()
    )

    db.commit()
    print("DONE!")

    print("Cleaning up...")

    if not fixed_sim_name and rdir.startswith('/tmp'):
        print("Removing temporary directory right away...")
        subprocess.run("rm -rf {}".format(rdir), shell=True, check=True)


    subprocess.run("${BSIM_COMPONENTS_PATH}/common/stop_bsim.sh {} || 1".format(config['SIM_NAME']), shell=True, check=True)
    # TODO: Register Simulation in a database?
    # TODO: Spawn dist_write process!