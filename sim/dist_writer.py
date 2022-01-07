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
import math


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

def density_to_side_length(density, num_proxy_nodes):
    density_in_km_sq = density
    density_in_m_sq = density_in_km_sq / 1000000.0
    # a is the side-length
    a = math.sqrt((num_proxy_nodes+1) / density_in_m_sq)
    return a

def rwp_position_iterator(rseed, num_proxy_nodes, model_options):
    numpy.random.seed(rseed)

    (dim_width, dim_height) = (1000.0, 1000.0)
    if 'dimensions' in model_options:
        (dim_width, dim_height) = model_options['dimensions'] if 'dimensions' in model_options else (1000.0, 1000.0)
    elif 'density' in model_options:
        # a is the side-length
        a = density_to_side_length(float(model_options['density']), num_proxy_nodes)
        (dim_width, dim_height) = (a,a)


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

    return distance.time_pos_iter(pos_iter, us_per_step)

def rwp_dist_iterators(rseed, num_proxy_nodes, model_options):
    raw_position_iter = rwp_position_iterator(rseed, num_proxy_nodes, model_options)
    return distance.time_dist_iters_from_pos_iter(raw_position_iter, num_proxy_nodes+1)

def rwp_line_iterator(rseed, num_proxy_nodes, model_options):
    raw_position_iter = rwp_position_iterator(rseed, num_proxy_nodes, model_options)
    for (t_us, positions) in raw_position_iter:
        for (d, p) in enumerate(positions):
            x,y = p
            z = 0
            yield "{} set {} {} {} {}\n".format(t_us, d, x, y, z)

def model_to_line_iterator(num_proxy_nodes, model, model_options, rseed):
    if model =='rwp':
        yield from rwp_line_iterator(rseed, num_proxy_nodes, model_options)
    elif model == 'raw':
        if 'file_content' not in model_options:
            print("key file_content not in model_options")
            exit(1)

        # we simply use the raw file contents
        file_content_str = model_options['file_content']
        yield from file_content_str.splitlines(True)

def start(directory, num_proxy, rseed, model, model_options={}):

    tmp_dir = tempfile.mkdtemp(dir=directory)
    line_iter = model_to_line_iterator(num_proxy, model, model_options, rseed)

    # First: Create the distance matrix pipe so we can return the filepath
    # note that this will block bsim as long as the data has not yet been written to the pipe
    position_file_path = os.path.join(tmp_dir, "positions.txt")
    os.mkfifo(position_file_path)


    def file_writer_thread():
        # create the main distance file to describe the named pipes, this will block (not as all the other pipes!)
        pos_fd = os.open(position_file_path, os.O_WRONLY)
        for line in line_iter:
            if line[-1] != "\n": # force new lines
                line += "\n"
            os.write(pos_fd, bytes(line, 'ascii'))
        # we finished writing the dist file, so we gently close it :)
        os.close(pos_fd)

    # we can now start the thread that actually writes the file contents
    t = threading.Thread(target=file_writer_thread, args=(), daemon=True)
    t.start()

    return position_file_path


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