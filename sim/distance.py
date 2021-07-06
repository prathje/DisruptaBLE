import math
from utils import iter_nodes
import threading
import itertools

# Important: We need to iterate the same way as BabbleSim for the best efficiency
def iter_nodes(nr_nodes):
    for a in range(nr_nodes):
        for b in range(nr_nodes):
            if a > b:
                yield (a,b)

def distances_from_positions(position_iter):
    for positions in position_iter:
        num_nodes = len(positions)

        distances = {}

        for (a, b) in [(x, y) for x in range(num_nodes) for y in range(num_nodes) if x > y]:
            pos_a = positions[a]
            pos_b = positions[b]
            diff_x = pos_a[0] - pos_b[0]
            diff_y = pos_a[1] - pos_b[1]
            distances[(a, b)] = math.sqrt(diff_x * diff_x + diff_y * diff_y)

        yield distances


def dist_iter_from_pos_iter(pos_iter, a, b):
    for positions in pos_iter:
        pos_a = positions[a]
        pos_b = positions[b]
        diff_x = pos_a[0] - pos_b[0]
        diff_y = pos_a[1] - pos_b[1]
        yield math.sqrt(diff_x * diff_x + diff_y * diff_y)


def dist_iters_from_pos_iter(num_nodes, pos_iter):

    # we multiply
    pos_iters = yield from itertools.tee(pos_iter, n=len(list(iter_nodes(num_nodes))))

    distance_iters = {}
    for (a,b) in iter_nodes(num_nodes):
        distance_iters[(a, b)] = dist_iter_from_pos_iter(next(pos_iters), a, b)

    return distance_iters



def time_pos_iter(pos_iter, step_us):
    t_us = 0
    for positions in pos_iter:
        yield t_us, positions
        t_us += step_us

def time_dist_iter_from_time_pos_iter(time_pos_iter, a, b):
    for (t_us, positions) in time_pos_iter:
        pos_a = positions[a]
        pos_b = positions[b]
        diff_x = pos_a[0] - pos_b[0]
        diff_y = pos_a[1] - pos_b[1]

        yield t_us, math.sqrt(diff_x * diff_x + diff_y * diff_y)


# https://stackoverflow.com/a/44638570/6669161
class safeteeobject(object):
    """tee object wrapped to make it thread-safe"""
    def __init__(self, teeobj, lock):
        self.teeobj = teeobj
        self.lock = lock
    def __iter__(self):
        return self
    def __next__(self):
        with self.lock:
            return next(self.teeobj)
    def __copy__(self):
        return safeteeobject(self.teeobj.__copy__(), self.lock)

def time_dist_iter_from_pos_iter(pos_iter, num_nodes, step_us):
    lock = threading.Lock()

    tp_iter = time_pos_iter(pos_iter, step_us)

    time_pos_iters = list(itertools.tee(tp_iter, len(list(iter_nodes(num_nodes)))))
    time_pos_iters = [safeteeobject(it, lock) for it in time_pos_iters]

    time_dist_iters = {}
    i = 0
    for (a, b) in iter_nodes(num_nodes):
        time_dist_iters[(a, b)] = time_dist_iter_from_time_pos_iter(time_pos_iters[i], a, b)
        i += 1

    return time_dist_iters