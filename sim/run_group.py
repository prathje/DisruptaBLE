import os
import subprocess
import sys
import itertools
import re
import dotenv
import threading
import time
from concurrent.futures import ThreadPoolExecutor

def input_env_to_iter(path):
    if os.path.isfile(path):
        yield path
    elif os.path.isdir(path):
        files = [os.path.join(path, f) for f in os.listdir(path)]

        for f in files:
            if not os.path.isfile(f):
                print("Could not find file: " + f)
                exit(1)

        yield from files
    else:
        print("Could not find file/diretory: " + path)
        exit(1)


if __name__ == "__main__":

    config = {
        **dotenv.dotenv_values(".env"),  # load shared development variables
        **dotenv.dotenv_values(".env.local"),  # load sensitive variables
        **os.environ,  # override loaded values with environment variables
    }

    if len(sys.argv) < 2:
        print("Group name required!")
        exit()

    group_name = sys.argv[1]
    input_envs = sys.argv[2:]

    num_parallel = 1

    if 'GROUP_PARALLEL_RUNS' in config and int(config['GROUP_PARALLEL_RUNS']) > 1:
        num_parallel = int(config['GROUP_PARALLEL_RUNS'])

    if 'GROUP_NUM_EXECUTIONS' in config and int(config['GROUP_NUM_EXECUTIONS']) > 1:
        assert 'SIM_RANDOM_SEED' not in config or not config['SIM_RANDOM_SEED']
        rseed = round(time.time())
    else:
        rseed = None


    iterators = []
    for ie in input_envs:
        iterators.append(input_env_to_iter(ie))

    rseed_lock = threading.Lock()

    def run_with_args(args):
        global rseed
        run_env = os.environ.copy()
        run_env["SIM_NAME"] = re.sub('[^0-9a-zA-Z]+', '-', group_name + "-" + "-".join(args))
        run_env["SIM_GROUP"] = group_name

        if rseed is not None:
            rseed_lock.acquire()
            run_env["SIM_RANDOM_SEED"] = str(rseed)
            run_env["SIM_NAME"] += "-" + str(rseed)
            rseed += 1
            rseed_lock.release()

        subprocess.run(["python3", "run.py"] + list(args), check=True, env=run_env)  # TODO: Check for errors?

    with ThreadPoolExecutor(max_workers=num_parallel) as executor:
        try:
            single_run_arg_iter = list(itertools.product(*iterators))
            run_arg_iter = single_run_arg_iter*int(config['GROUP_NUM_EXECUTIONS'])
            futures = executor.map(run_with_args, run_arg_iter)
        except:
            executor.shutdown(wait=False, cancel_futures=True)