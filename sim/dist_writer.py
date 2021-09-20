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
import threading
from pymobility.mobility import random_waypoint


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


def rwp_iterators(num_proxy_nodes, model_options):

    (dim_width, dim_height) = model_options['dimensions'] if 'dimensions' in model_options else (1000.0, 1000.0)
    seconds_per_step = model_options['seconds_per_step'] if 'seconds_per_step' in model_options else 1.0


    # TODO Add those to arguments
    vel_min = model_options['vel_min'] if 'vel_min' in model_options else 1.0
    vel_max = model_options['vel_max'] if 'vel_max' in model_options else 1.0

    max_waiting_time = model_options['max_waiting_time'] if 'max_waiting_time' in model_options else 0.0 # we run without waiting time for now!

    assert seconds_per_step > 0.0
    assert dim_width > 0
    assert 0.0 <= vel_min <= vel_max
    assert dim_height > 0
    assert max_waiting_time >= 0

    steps_per_second = 1.0 / seconds_per_step

    us_per_step = int(seconds_per_step * 1000000.0)

    # We scale everything to match the number of steps per second
    # b (units / second) * (second / step) = b (units / step)
    # a seconds * (steps / second) = a steps
    proxy_pos_iter = random_waypoint(num_proxy_nodes, dimensions=(dim_width, dim_height),
                                     velocity=(vel_min * seconds_per_step, vel_max * seconds_per_step),
                                     wt_max=max_waiting_time * steps_per_second,
                                     init_stationary=False
                                     )

    def add_static_source_node(it):
        for pos_list in it:
            yield ([(dim_width/2, dim_height/2)] + list(pos_list))

    pos_iter = add_static_source_node(proxy_pos_iter)

    # Now we can output data for the individual pipes
    # Loop over every pair, write as much as possible (e.g. buffer full) then move to the next element
    time_dist_iterators = distance.time_dist_iter_from_pos_iter(pos_iter, num_proxy_nodes+1, us_per_step)

    return time_dist_iterators

def rwp_raw_positions(rseed, num_proxy_nodes, model_options):
    numpy.random.seed(rseed)

    (dim_width, dim_height) = model_options['dimensions'] if 'dimensions' in model_options else (1000.0, 1000.0)
    seconds_per_step = model_options['seconds_per_step'] if 'seconds_per_step' in model_options else 1.0


    # TODO Add those to arguments
    vel_min = model_options['vel_min'] if 'vel_min' in model_options else 1.0
    vel_max = model_options['vel_max'] if 'vel_max' in model_options else 1.0

    max_waiting_time = model_options['max_waiting_time'] if 'max_waiting_time' in model_options else 0.0 # we run without waiting time for now!

    assert seconds_per_step > 0.0
    assert dim_width > 0
    assert 0.0 <= vel_min <= vel_max
    assert dim_height > 0
    assert max_waiting_time >= 0

    steps_per_second = 1.0 / seconds_per_step

    us_per_step = int(seconds_per_step * 1000000.0)

    # We scale everything to match the number of steps per second
    # b (units / second) * (second / step) = b (units / step)
    # a seconds * (steps / second) = a steps
    proxy_pos_iter = random_waypoint(num_proxy_nodes, dimensions=(dim_width, dim_height),
                                     velocity=(vel_min * seconds_per_step, vel_max * seconds_per_step),
                                     wt_max=max_waiting_time * steps_per_second,
                                     init_stationary=False
                                     )

    def add_static_source_node(it):
        for pos_list in it:
            yield ([(dim_width/2, dim_height/2)] + list(pos_list))


    pos_iter = add_static_source_node(proxy_pos_iter)
    us = 0

    for positions in pos_iter:
        yield (us, positions)
        us += us_per_step


def model_to_iterators(num_proxy_nodes, model, model_options, rseed):
    numpy.random.seed(rseed)

    if model =='rwp':
        return rwp_iterators(num_proxy_nodes, model_options)
    else:

        if 'distance' not in model_options:
            print("key distance not in model_options")
            exit(1)

        d = float(model_options['distance'])
        def fixed_iter():
            # Hacky stuff!
            ts = 0
            while True:
                yield (ts, d)
                ts += 1000000

        iterators = {}
        for (a,b) in iter_nodes(num_proxy_nodes+1):
            iterators[(a,b)] = fixed_iter()

        return iterators


def distance_writer_thread(tmp_dir, num_nodes, iterators):

    dist_file_path = os.path.join(tmp_dir, "distances.matrix")

    # create the main distance file to describe the named pipes, this will block (not as all the other pipes!)
    dist_fd = os.open(dist_file_path, os.O_WRONLY)

    os.write(dist_fd, bytes("#<Txnbr> <Rxnbr> : {<distance>|\"<distance_file_name>\"}\n", 'ascii'))

    files = {}

    # The BabbleSim indoor channel order matches exactly our iter_nodes order
    # as such we first open

    for (a, b) in progressbar.progressbar(list(iter_nodes(num_nodes))):

        filepath = os.path.join(tmp_dir, get_dist_file_name(a, b))

        # create fifo
        os.mkfifo(filepath)

        # write to distance file
        row = "{} {} \"{}\"\n".format(str(a), str(b), os.path.join(tmp_dir, get_dist_file_name(a, b)))
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
                    print("Sleeping open for "+ str((a,b)))
                    pass  # try later
        files[(a, b)] = file

        first_entries = itertools.islice(iterators[(a, b)], 2)    # 2

        for (t_us, d) in first_entries:
            row = "{} {}\n".format(t_us, format_dist(d))
            success = False
            while not success:
                try:
                    os.write(file, bytes(row, 'ascii'))
                    success = True  # we continue with the next value if written
                except BlockingIOError as ex:
                    if ex.errno == errno.EAGAIN:
                        time.sleep(0.1)
                        #print("Sleeping write for " + str((a, b)))
                        pass  # try later
                except BrokenPipeError as e:
                    print("Broken pipe from beginning?!" + str(e))
                    pass  # try later

    # we finished writing the dist file
    os.close(dist_fd)

    all_pairs = list(iter_nodes(num_nodes))
    num_writer_threads = max(1, min(10, num_nodes))

    def partial_writer_thread(partial_pairs, partial_files, partial_iterators):
        # we cache all lines that still require sending
        line_cache = {}
        for (a, b) in partial_pairs:
            line_cache[(a,b)] = None

        while True:
            # get the next entry for every pair (if not already cached!)
            for (a,b) in partial_pairs:
                if line_cache[(a,b)] is None:
                    line_cache[(a,b)] = next(partial_iterators[(a, b)], None) # this might still be None afterward!

            entry_found = False # check if we have at least one more entry to write!
            one_successful_write = False # check if we have at least one more entry to write!

            for (a,b) in partial_pairs:
                if line_cache[(a,b)] is None:
                    continue

                entry_found = True
                # we now try to write this line
                (t_us, d) = line_cache[(a,b)]
                row = "{} {}\n".format(t_us, format_dist(d))
                try:
                    os.write(partial_files[(a, b)], bytes(row, 'ascii'))
                    line_cache[(a,b)] = None # Reset in case of success!
                    one_successful_write = True
                except BlockingIOError as ex:
                    pass    # nothing
                except BrokenPipeError as e:
                    print("BrokenPipeError!" + str(e))
                    break   # we close this writer thread straight away TODO: This could deadlock the execution?

            if not one_successful_write:
                time.sleep(1.0) # we sleep a bit if we could not write anything...

            if not entry_found:
                break   # Seems like we wrote everything \o/


    partial_writer_threads = []
    for i in range(num_writer_threads):
        partial_pairs = all_pairs[i::num_writer_threads]    # we equally distribute

        partial_files = {}
        partial_iterators = {}

        for (a, b) in partial_pairs:
            partial_files[(a,b)] = files[(a,b)]
            partial_iterators[(a,b)] = iterators[(a,b)]

        t = threading.Thread(target=partial_writer_thread, args=(partial_pairs, partial_files, partial_iterators), daemon=True)
        t.start()
        partial_writer_threads.append(t)

    for p in partial_writer_threads:
        p.join()
    # since everything is initalized, we just loop through the indiviudal entries one by one



def start(directory, num_proxy, rseed, model, model_options={}, num_wifi_devices=0, wifi_devices_distance=0):

    tmp_dir = tempfile.mkdtemp(dir=directory)

    iterators = model_to_iterators(num_proxy, model, model_options, rseed)

    # we now expand the iterators to match our wifi devices
    wifi_devices_distance = float(wifi_devices_distance)

    def fixed_wifi_dist_iter():
        ts = 0
        while True:
            yield (ts, wifi_devices_distance)
            ts += 1000000

    print("USING {} wifi devices at fixed dist {}".format(num_wifi_devices, wifi_devices_distance))

    for (a,b) in iter_nodes(num_proxy+1+num_wifi_devices):
        if (a,b) not in iterators:
            assert (a >= num_proxy+1 or b >= num_proxy+1)
            iterators[(a,b)] = fixed_wifi_dist_iter()

    # First: Create the distance matrix pipe so we can return the filepath
    # note that this will block bsim as long as the data has not yet been written to the pipe
    dist_file_path = os.path.join(tmp_dir, "distances.matrix")
    os.mkfifo(dist_file_path)

    # we can now start the thread that actually writes the file contents
    t = threading.Thread(target=distance_writer_thread, args=(tmp_dir, num_proxy+1+num_wifi_devices, iterators), daemon=True)
    t.start()

    return dist_file_path


def cleanup(dist_file_path):
      dir = os.path.dirname(dist_file_path)
      print("TODO: Delete distance directory!")
      print(dir)


if __name__ == "__main__":


    parser = argparse.ArgumentParser(description='Write distances')

    parser.add_argument('num_proxy', help='The number of proxy nodes', default=100)
    parser.add_argument('--model', help='The model to use', default='rwp')
    parser.add_argument('--rseed', help='The random seed to use', default=0)

    args = parser.parse_args()

    print(start(int(args.num_proxy), int(args.rseed), args.model))