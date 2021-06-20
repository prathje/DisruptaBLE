import argparse
import distance
import tempfile
import os
import errno
import time
import numpy
import itertools
from utils import format_dist, iter_nodes
import fcntl
import progressbar


F_SETPIPE_SZ = 1031  # Linux 2.6.35+
F_GETPIPE_SZ = 1032  # Linux 2.6.35+

PIPE_NEW_BUF_SIZE = 4096    # Use non for default size (which needs a lot of time to set)

def get_dist_file_name(a, b):
    return "{}-{}.dist".format(a, b)

def handle_distances(nr_nodes, distances):
    with tempfile.TemporaryDirectory() as dirpath:

        # first create the main distance file to describe the named pipes

        dist_file_path = create_distance_matrix(dirpath, nr_nodes)
        create_dist_pipes(dirpath, nr_nodes)
        # We need to start the simulation but at the same time we need to pipe distances into the files
        # as the named pipes block until opened we move their handling into a separate thread
        #def dist_thread(dirpath, nr_nodes, dist_iterator):
        descriptors = {}
        # first open all the files
        for (a, b) in iter_nodes(nr_nodes):
            filepath = os.path.join(dirpath, get_dist_file_name(a, b))
            descriptors[(a, b)] = open(filepath, "w")

        for t_us in range(0, MAX_US + 1, MODEL_US_PER_STEP):
            dists = next(dist_iterator)
            for (a, b) in iter_nodes(nr_nodes):
                f = descriptors[(a, b)]
                dist = dists[(a,b)]
                f.write("{} {}\n".format(t_us, format_dist(dist)))
        # We now start the simulation


if __name__ == "__main__":
    from pymobility.mobility import random_waypoint

    parser = argparse.ArgumentParser(description='Write distances')

    parser.add_argument('num_proxy', help='The number of proxy nodes', default=100)
    parser.add_argument('--model', help='The model to use', default='rwp')
    parser.add_argument('--model_seconds_per_step', help='The model to use', default=1.0)
    parser.add_argument('--model_dim_width', help='The model width dimension', default=1000.0)
    parser.add_argument('--model_dim_height', help='The model height dimension', default=1000.0)
    parser.add_argument('--rseed', help='The random seed to use', default=0)

    args = parser.parse_args()

    num_proxy_nodes = int(args.num_proxy)
    seconds_per_step = float(args.model_seconds_per_step)
    steps_per_second = 1.0 / seconds_per_step

    us_per_step = int(seconds_per_step * 1000000.0)
    dimensions = (args.model_dim_width, args.model_dim_height)

    # TODO Add those to arguments
    vel_min = 0.1  # m/s
    vel_max = 1.0  # m/s
    max_waiting_time = 1.0  # s

    numpy.random.seed(args.rseed)
    # We scale everything to match the number of steps per second
    # b (units / second) * (second / step) = b (units / step)
    # a seconds * (steps / second) = a steps
    proxy_pos_iter = random_waypoint(num_proxy_nodes, dimensions=dimensions,
                               velocity=(vel_min * seconds_per_step, vel_max * seconds_per_step),
                               wt_max=max_waiting_time * steps_per_second)
    def add_static_source_node(it):
        for pos_list in it:
            yield [()] + pos_list

    pos_iter = add_static_source_node(proxy_pos_iter)

    num_nodes = num_proxy_nodes+1

    with tempfile.TemporaryDirectory() as dirpath:

        # First: Create the distance matrix pipe

        dist_file_path = os.path.join(dirpath, "distances.matrix")
        os.mkfifo(dist_file_path)

        # output distance file path
        print(dist_file_path)

        # create the main distance file to describe the named pipes, this will block (not as all the other pipes!)
        dist_fd = os.open(dist_file_path, os.O_WRONLY)

        os.write(dist_fd, bytes("#<Txnbr> <Rxnbr> : {<distance>|\"<distance_file_name>\"}\n", 'ascii'))


        # Now we can output data for the individual pipes
        # Loop over every pair, write as much as possible (e.g. buffer full) then move to the next element
        time_dist_iterators = distance.time_dist_iter_from_pos_iter(pos_iter, num_nodes, us_per_step)

        files = {}

        # The BabbleSim indoor channel order matches exactly our iter_nodes order
        # as such we first open

        for (a, b) in progressbar.progressbar(list(iter_nodes(num_nodes))):

            filepath = os.path.join(dirpath, get_dist_file_name(a, b))

            # create fifo
            os.mkfifo(filepath)

            # write to distance file
            row = "{} {} \"{}\"\n".format(str(a), str(b), os.path.join(dirpath, get_dist_file_name(a, b)))
            os.write(dist_fd, bytes(row, 'ascii'))

            file = None
            # File not open -> we try to open it before usage
            while file is None :
                try:
                    file = os.open(filepath, os.O_WRONLY | os.O_NONBLOCK)

                    #print("opened " + str((a,b)))

                    if PIPE_NEW_BUF_SIZE is not None:  # TODO: Check the real performance impact
                        fcntl.fcntl(file, F_SETPIPE_SZ, PIPE_NEW_BUF_SIZE)
                except OSError as ex:
                    if ex.errno == errno.ENXIO:
                        time.sleep(0.1)
                        #print("Sleeping open for "+ str((a,b)))
                        pass  # try later
            files[(a, b)] = file

            first_entries = itertools.islice(time_dist_iterators[(a, b)], 2)    # 2

            for (t_us, d) in first_entries:
                row = "{} {}\n".format(t_us, format_dist(d))
                success = False
                while not success:
                    try:
                        os.write(file, bytes(row, 'ascii'))
                        #print("written " + str((a, b)))
                        success = True  # we continue with the next value if written
                    except BlockingIOError as ex:
                        if ex.errno == errno.EAGAIN:
                            time.sleep(0.1)
                            #print("Sleeping write for " + str((a, b)))
                            pass  # try later

        os.close(dist_fd)

        # since everything is initalized, we just loop through the indiviudal entries one by one
        while True:
            for (a,b) in iter_nodes(num_nodes):

                (t_us, d) = next(time_dist_iterators[(a, b)])
                row = "{} {}\n".format(t_us, format_dist(d))
                file = files[(a, b)]

                success = False
                while not success:
                    try:
                        os.write(file, bytes(row, 'ascii'))
                        success = True
                    except BlockingIOError as ex:
                        if ex.errno == errno.EAGAIN:
                            print("Waiting for write " + str((a, b)) + ": " + str((t_us, d)))
                            time.sleep(0.1)
