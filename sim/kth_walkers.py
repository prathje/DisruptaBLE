import gzip
import csv
import math
import distance

def create_kth_walkers_reader(model_options, max_time = None):
    assert 'filepath' in model_options

    # To support offsets, we would introduce a dictionary to translate ids and ignore ids that are destroyed before the offset
    # we would then create all the nodes and set their respective initial positions
    # for all other lines, we need to translate the ids and subtract the offset (also handling the destination time!)

    path = model_options['filepath']
    path = path.replace('/app/sim/data/kth_walkers', 'data/kth_walkers')

    with gzip.open(path,'rt') as f:
        reader = csv.reader(f, delimiter=' ')
        for r in reader:
            if max_time is not None and float(r[0]) > max_time:
                break
            yield r

def walkers_to_line_gen(num_proxy_nodes, model_options):
    assert 'filepath' in model_options

    kw_reader = create_kth_walkers_reader(model_options)

    # we first disable all nodes (including node 0)
    for i in range(num_proxy_nodes+1):
        yield "0 disable {}".format(i)

    # we then set node 0 position and enable it
    yield "0 set 0 783.2 1639.4 0"
    # we then enable node 0
    yield "0 enable 0"

    # we then go read through walkers file and translate the commands, ignoring non-existant devices
    for r in kw_reader:
        ts = r[0]
        us = math.floor(float(ts)*1000000)
        cmd = r[1]
        id = r[2]

        if int(id) > num_proxy_nodes:
            continue    # we ignore this node since it does have a corresponding device anyway

        if cmd == 'setdest': # "6.0 setdest 1 818.0 1453.0 0.0 0.8 6.6"
            pos_x = r[3]
            pos_y = r[4]
            pos_z = r[5]
            dest_time_us = math.floor(float(r[7])*1000000)

            assert dest_time_us >= us
            # <ts> move <id> <x> <y> <z> <duration>
            yield "{} move {} {} {} {} {}".format(str(us), id, pos_x, pos_y, pos_z, str(dest_time_us-us))
        elif cmd == 'create': # 6.0 create 2 628.2 1812.1 0.0
            pos_x = r[3]
            pos_y = r[4]
            pos_z = r[5]
            yield "{} set {} {} {} {}".format(str(us), id, pos_x, pos_y, pos_z)
            yield "{} enable {}".format(str(us), id)
        elif cmd == 'destroy': # 132.6 destroy 4
            yield "{} disable {}".format(str(us), id)
            yield "{} set {} 0 0 0".format(str(us), id)
        else:
            print("Warning: could not find cmd: " + r)

def walkers_get_num_created_nodes_until(max_time, model_options):
    num_created = 0

    kw_reader = create_kth_walkers_reader(model_options, max_time=max_time)
    for r in kw_reader:
        if r[1] == 'create':
            num_created += 1
    return num_created

def get_node_lifetimes(max_time, model_options):
    assert max_time > 0

    kw_reader = create_kth_walkers_reader(model_options, max_time=max_time)

    lifetimes = {}
    lifetimes[0] = (0.0, max_time)

    for r in kw_reader:
        if r[1] == 'create':
            assert int(r[2]) not in lifetimes
            lifetimes[int(r[2])] = (float(r[0]), max_time) # we assume they stay "alive" until the end
        if r[1] == 'destroy':
            assert int(r[2]) in lifetimes
            lifetimes[int(r[2])] = (lifetimes[int(r[2])][0], min(lifetimes[int(r[2])][1], float(r[0]))) # we assume they stay "alive" until the end
    return lifetimes

def get_bounds(model_options):

    xs = []
    ys = []

    kw_reader = create_kth_walkers_reader(model_options)

    for r in kw_reader:
        if r[1] == 'create' or r[1] == 'setdest':
            xs.append(float(r[3]))
            ys.append(float(r[4]))

    return (min(xs), min(ys)), (max(xs), max(ys))

def get_max_density(model_options, max_time = None):
    ((min_x, min_y), (max_x, max_y)) = get_bounds(model_options)

    kw_reader = create_kth_walkers_reader(model_options, max_time=max_time)

    num_created = 0
    num_destroyed = 0
    max_concurrent = 0
    max_concurrent_time = None
    max_available_time = None

    for r in kw_reader:
        if max_time and float(r[0]) > max_time:
            max_available_time = None
            break
        if r[1] == 'create':
            num_created += 1
        if r[1] == 'destroy':
            num_destroyed += 1
        concurrent = num_created-num_destroyed
        if concurrent > max_concurrent:
            max_concurrent = concurrent
            max_concurrent_time = r[0]
        max_available_time = r[0]

    print('concurrent', max_concurrent, max_concurrent_time, 'created', num_created, 'max_available', max_available_time)

    area = (max_x-min_x)*(max_y-min_y)
    print((max_x-min_x), (max_y-min_y), area, max_concurrent, max_concurrent/(area/1000000.0))


def create_contact_pairs(max_time, model_options, dist_limit=20.0, step_s=1.0):
    assert 'filepath' in model_options
    assert max_time > 0
    
    assert step_s == 1.0 # other is currently not supported...

    node_lifetimes = get_node_lifetimes(max_time, model_options)
    num_proxy_nodes = len(node_lifetimes)-1

    import dist_writer
    pos_iter = dist_writer.line_to_position_iterator(num_proxy_nodes, walkers_to_line_gen(num_proxy_nodes, model_options))

    # the dictionary that contains (start_time, end_times) tuples under each key (a,b) with a > b
    contact_pairs = {}

    # contains the start time of the current contact
    contact_pairs_start = {}

    for a in range(num_proxy_nodes+1):
        for b in  range(num_proxy_nodes+1):
            if a <= b:
                continue
            contact_pairs[(a,b)] = []
            contact_pairs_start[(a,b)] = None
    t = 0
    while t <= max_time:
        (ts, positions) = next(pos_iter)
        alive_nodes = [k for k in node_lifetimes if node_lifetimes[k][0] <= t <= node_lifetimes[k][1]]

        for a in alive_nodes:
            for b in alive_nodes:
                if a <= b:
                    continue

                pos_a = positions[a]
                pos_b = positions[b]
                diff_x = pos_a[0] - pos_b[0]
                diff_y = pos_a[1] - pos_b[1]
                dist = math.sqrt(diff_x * diff_x + diff_y * diff_y)

                if dist > dist_limit:
                    if contact_pairs_start[(a,b)] is not None: # connection breaks!
                        contact_pairs[(a,b)].append((contact_pairs_start[(a,b)], t))
                        contact_pairs_start[(a,b)] = None
                elif contact_pairs_start[(a,b)] is None:
                    contact_pairs_start[(a,b)] = t  # we start a new contact!
        t += 1

    # in the end, we need close all contacts based on the nodes lifetimes
    for a in range(num_proxy_nodes+1):
        for b in  range(num_proxy_nodes+1):
            if a <= b:
                continue

            if contact_pairs_start[(a,b)] is not None:
                contact_pairs[(a,b)].append((contact_pairs_start[(a,b)], min(node_lifetimes[a][1], node_lifetimes[b][1])))
                contact_pairs_start[(a,b)] = None

    return contact_pairs


def simulate_broadcast(max_time, model_options, dist_limit=20.0, setup_time=20.0, source_index=0):
    assert 'filepath' in model_options
    assert max_time > 0

    node_lifetimes = get_node_lifetimes(max_time, model_options)
    num_proxy_nodes = len(node_lifetimes)-1

    node_informed = {}
    for k in node_lifetimes:
        node_informed[k] = None
    node_informed[source_index] = 0 # source device is informed from the start

    conn_start = {}    # dict with key (a,b) and the second the connection did start (or None)

    import dist_writer
    pos_iter = dist_writer.line_to_position_iterator(num_proxy_nodes, walkers_to_line_gen(num_proxy_nodes, model_options))

    t = 0
    while t <= max_time:
        (ts, positions) = next(pos_iter)
        alive_nodes = [k for k in node_lifetimes if node_lifetimes[k][0] <= t <= node_lifetimes[k][1]]
        # iterate over all alive nodes until no new nodes were informed

        while True:
            newly_informed = False

            for a in alive_nodes:
                for b in alive_nodes:
                    if a <= b:   # otherwise already checked (or the same node) note that we
                        continue
                    pos_a = positions[a]
                    pos_b = positions[b]
                    diff_x = pos_a[0] - pos_b[0]
                    diff_y = pos_a[1] - pos_b[1]
                    dist = math.sqrt(diff_x * diff_x + diff_y * diff_y)

                    if dist > dist_limit:   # connection breaks!
                        conn_start[(a,b)] = None # we reset the connection
                    else:
                        if (a,b) not in conn_start or conn_start[(a,b)] is None : # connection could already have been started
                            conn_start[(a,b)] = t
                        assert conn_start[(a,b)] <= t

                        if t-conn_start[(a,b)] >= setup_time:
                            if node_informed[a] is not None and node_informed[b] is None:   # node_informed[a] <= t anyway
                                # a informs b -> newly informed so we might need to inform others as well!
                                node_informed[b] = t
                                newly_informed = True
                            elif node_informed[b] is not None and node_informed[a] is None:
                                # b informs a -> newly informed so we might need to inform others as well!
                                node_informed[a] = t
                                newly_informed = True
            if not newly_informed: # if we informed someone we need to go through all pairs again and check if new ones could get informed
                break
        t += 1
    return node_informed


def dist_time_iters(max_time, model_options):
    num_proxy_nodes = walkers_get_num_created_nodes_until(max_time, model_options)
    import dist_writer
    tp_iter = dist_writer.line_to_position_iterator(num_proxy_nodes, walkers_to_line_gen(num_proxy_nodes, model_options))
    return distance.time_dist_iters_from_pos_iter(tp_iter, num_proxy_nodes+1)


import numpy as np
def eval_lt_stats(max_time, model_options):
    lt = get_node_lifetimes(max_time, model_options)
    lts = []
    for k in lt:
        if lt[k][1] < max_time:
            lts.append(lt[k][1]-lt[k][0])
    return np.mean(lts), np.std(lts), np.percentile(np.array(lts), [2.5, 97.5])

if __name__ == "__main__":

    # print('001', eval_lt_stats(36000, {'filepath': 'data/kth_walkers/sparse_run1/ostermalm_001_1.tr.gz'}))
    # print('002', eval_lt_stats(36000, {'filepath': 'data/kth_walkers/sparse_run1/ostermalm_002_1.tr.gz'}))
    # print('003', eval_lt_stats(36000, {'filepath': 'data/kth_walkers/sparse_run1/ostermalm_003_1.tr.gz'}))
    # print('004', eval_lt_stats(36000, {'filepath': 'data/kth_walkers/sparse_run1/ostermalm_004_1.tr.gz'}))
    # print('005', eval_lt_stats(36000, {'filepath': 'data/kth_walkers/sparse_run1/ostermalm_005_1.tr.gz'}))
    # exit()
    #
    print('001')
    get_max_density({'filepath': 'data/kth_walkers/sparse_run1/ostermalm_001_1.tr.gz'}, max_time=3600)
    #print('002')
    #get_max_density({'filepath': 'data/kth_walkers/sparse_run1/ostermalm_002_1.tr.gz'})
    print('003')
    get_max_density({'filepath': 'data/kth_walkers/sparse_run1/ostermalm_003_1.tr.gz'}, max_time=3600)
    #print('004')
    #get_max_density({'filepath': 'data/kth_walkers/sparse_run1/ostermalm_004_1.tr.gz'})
    print('005')
    get_max_density({'filepath': 'data/kth_walkers/sparse_run1/ostermalm_005_1.tr.gz'}, max_time=3600)

    #
    # print('007')
    # get_max_density({'filepath': 'data/kth_walkers/medium_run1/ostermalm_007_1.tr.gz'})
    # print('009')
    # get_max_density({'filepath': 'data/kth_walkers/medium_run1/ostermalm_009_1.tr.gz'})
    # print('011')
    # get_max_density({'filepath': 'data/kth_walkers/medium_run1/ostermalm_011_1.tr.gz'})
    # print('015')
    # get_max_density({'filepath': 'data/kth_walkers/medium_run1/ostermalm_015_1.tr.gz'})
    # print('020')
    # get_max_density({'filepath': 'data/kth_walkers/medium_run1/ostermalm_020_1.tr.gz'})
    # print('030')
    # get_max_density({'filepath': 'data/kth_walkers/dense_run1/ostermalm_030_1.tr.gz'})
    # print('040')
    # get_max_density({'filepath': 'data/kth_walkers/dense_run1/ostermalm_040_1.tr.gz'})
    # print('050')
    # get_max_density({'filepath': 'data/kth_walkers/dense_run1/ostermalm_050_1.tr.gz'})
    # print('070')
    # get_max_density({'filepath': 'data/kth_walkers/dense_run1/ostermalm_070_1.tr.gz'})
    # print('090')
    # get_max_density({'filepath': 'data/kth_walkers/dense_run1/ostermalm_090_1.tr.gz'})

    #with gzip.open('data/kth_walkers/dense_run1/ostermalm_090_1.tr.gz','rt') as f:
    #with gzip.open('data/kth_walkers/medium_run1/ostermalm_007_1.tr.gz','rt') as f:


    max_time = 3600
    kw_reader = create_kth_walkers_reader({'filepath': 'data/kth_walkers/sparse_run1/ostermalm_001_1.tr.gz'}, max_time=max_time)


    num_created = 0
    num_destroyed = 0
    max_concurrent = 0
    max_concurrent_time = None


    min_x = None
    min_y = None
    max_x = None
    max_y = None

    for r in kw_reader:
        if max_time and float(r[0]) > max_time:
            break
        if r[1] == 'create':
            num_created += 1
        if r[1] == 'destroy':
            num_destroyed += 1
        concurrent = num_created-num_destroyed
        if concurrent > max_concurrent:
            max_concurrent = concurrent
            max_concurrent_time = r[0]

        if r[3] == 'destroy':
            num_destroyed += 1

    print('concurrent', max_concurrent, max_concurrent_time, 'created', num_created)

    #test_gen = walkers_to_line_gen(100, {'filepath': 'data/kth_walkers/sparse_run1/ostermalm_005_1.tr.gz'})

    #for line in test_gen:
    #    print(line)

    # 001: 57 12156.6 created 2092
    # 005: 233 3057.6 created 4227
    # 007: 301 4387.8 created 5706