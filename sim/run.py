import dotenv
import os
import subprocess
import sys
import tinydb
import re
import threading
import json
import time
import random

from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

config = {
    **dotenv.dotenv_values(".env"),  # load shared development variables
    **dotenv.dotenv_values(".env.local"),  # load sensitive variables
    **dotenv.dotenv_values("run.env"),  # run specific variables TODO: Make this configurable?
    **os.environ,  # override loaded values with environment variables
}

def compile_and_move(rdir, exec_name, overlay_config):

    bdir = os.path.join(rdir, "build", exec_name)

    west_build_command =  "west build -b nrf52_bsim {} --build-dir {} --pristine auto -- -DOVERLAY_CONFIG={}".format(config['SIM_SOURCE_DIR'], bdir, overlay_config)

    subprocess.run(west_build_command, shell=True, check=True)

    # Move resulting executable to main folder
    os.rename(
        os.path.join(bdir, "zephyr", "zephyr.exe"),
        os.path.join(config['BSIM_OUT_PATH'], "bin", exec_name)
    )

def spawn_node_process(exec_name, id):
    exec_path = os.path.join(config['BSIM_OUT_PATH'], "bin", exec_name)

    print(exec_path + " " + '-s={} -d={}'.format(config['SIM_NAME'], id))
    process = subprocess.Popen([exec_path, '-s=' + config['SIM_NAME'], '-d=' + str(id)],
                               cwd=config['BSIM_OUT_PATH']+"/bin",
                               text=True,
                               stdout=subprocess.PIPE,
                               bufsize=1,
                               stderr=sys.stderr,
    encoding="ISO-8859-1")

    return process


event_re = re.compile(r"d\_(\d\d):\s\@(\d\d:\d\d:\d\d\.\d+)\s\sEVENT\s([^\s]+)\s(.+)")

def output_to_event_iter(o):
    global max_us
    for line in o:
        #print(line.rstrip())
        re_match = event_re.match(line.rstrip())
        if re_match:
            device, ts, event_type, data_str = re_match.groups()
            try:
                data = json.loads(data_str)
            except:
                print(line.rstrip())
                return
            us = int(ts.replace(":", "").replace(".", ""))

            yield {
                "device_id": int(device),
                "us": us,
                "type": event_type,
                "data": data
            }

if __name__ == "__main__":
    if config['SIM_RANDOM_SEED'] != "":
        rseed = int(config['SIM_RANDOM_SEED'])
    else:
        rseed = round(time.time())

    random.seed(rseed)

    run_name = 'test'
    # Create the parent run directory
    #os.makedirs(config['SIM_RUN_DIRECTORY'], exist_ok=True)
    rdir = os.path.join("/tmp/sim", run_name)
    logdir = os.path.join(config['SIM_LOG_DIR'], run_name)

    os.makedirs(rdir, exist_ok=True)
    os.makedirs(logdir, exist_ok=True)

    compile_and_move(rdir, "source", "source.conf")
    compile_and_move(rdir, "proxy", "proxy.conf")

    subprocess.run("${BSIM_COMPONENTS_PATH}/common/stop_bsim.sh || 1", shell=True, check=True)

    node_processes = []

    node_processes.append(
        spawn_node_process("source", len(node_processes))
    )

    for i in range(0, int(config['SIM_PROXY_NUM_NODES'])):
        node_processes.append(
            spawn_node_process("proxy", len(node_processes))
        )


    phy_exec_path = os.path.join(config['BSIM_OUT_PATH'], "bin", "bs_2G4_phy_v1")

    phy_process = subprocess.Popen([phy_exec_path,
                                    '-s='+config['SIM_NAME'],
                                    '-sim_length='+config['SIM_LENGTH'],
                                    '-D='+str(int(config['SIM_PROXY_NUM_NODES'])+1),
                                    '-rs='+str(int(rseed)),
                                    '-defmodem=BLE_simple',
                                    '-channel=Indoorv1',
                                    '-argschannel',
                                    '-preset=Huge3',
                                    '-speed=1.1',
                                    '-at='+str(int(config['SIM_FIXED_ATTENUATION']))
                                    ],
                                   cwd=config['BSIM_OUT_PATH']+"/bin",
       encoding="ISO-8859-1",
        stdout=sys.stdout,
       bufsize=1,
        stderr=sys.stderr
    )

    db = tinydb.TinyDB(os.path.join(logdir, 'db.json'), storage=CachingMiddleware(JSONStorage))

    db_lock = threading.Lock()

    max_us = -1

    def process_events(p):
        global max_us

        for e in output_to_event_iter(p.stdout):
            e['run'] = run_name
            if e['us'] > max_us:
                max_us = e['us']
                print(max_us/1000000)

            db_lock.acquire()
            db.insert(e)
            db_lock.release()

    log_threads = []
    for p in node_processes:
        t = threading.Thread(target=process_events, args=(p,))
        t.start()
        log_threads.append(t)

    done = False
    while not done:
        done = True
        for p in [phy_process]+node_processes:
            if p.poll() is None:
                done = False

    
    for t in log_threads:
        t.join()

    db.close()

    for p in [phy_process]+node_processes:
        if p.returncode != 0:
            print("Got weird response code: "+ str(p.returncode))
    print("DONE!")
    # TODO: Register Simulation in a database?
    # TODO: Spawn dist_write process!