import os
import subprocess
import sys
import itertools
import re

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

    if len(sys.argv) < 2:
        print("Group name required!")
        exit()

    group_name = sys.argv[1]
    input_envs = sys.argv[2:]

    iterators = []
    for ie in input_envs:
        iterators.append(input_env_to_iter(ie))

    for args in itertools.product(*iterators):
        run_env = os.environ.copy()
        run_env["SIM_NAME"] = re.sub('[^0-9a-zA-Z]+', '-', group_name + "-" + "-".join(args))
        run_env["SIM_GROUP"] = group_name
        subprocess.run(["python3", "run.py"] + list(args), check=False, env=run_env)  # TODO: Check for errors?