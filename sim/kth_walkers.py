import gzip
import csv
import math

def walkers_to_line_gen(num_proxy_nodes, model_options):
    assert 'filepath' in model_options
    with gzip.open(model_options['filepath'],'rt') as f:
        # we first disable all nodes (including node 0)
        for i in range(num_proxy_nodes+1):
            yield "0 disable {}".format(i)

        # we then set node 0 position and enable it
        yield "0 set 0 783.2 1639.4 0"
        # we then enable node 0
        yield "0 enable 0"

        # we then go read through walkers file and translate the commands, ignoring non-existant devices
        reader = csv.reader(f, delimiter=' ')
        for r in reader:
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
    assert 'filepath' in model_options
    num_created = 0
    with gzip.open(model_options['filepath'],'rt') as f:
        reader = csv.reader(f, delimiter=' ')
        for r in reader:
            if max_time and float(r[0]) > max_time:
                break
            if r[1] == 'create':
                num_created += 1
    return num_created

if __name__ == "__main__":
    #with gzip.open('data/kth_walkers/dense_run1/ostermalm_090_1.tr.gz','rt') as f:
    #with gzip.open('data/kth_walkers/medium_run1/ostermalm_007_1.tr.gz','rt') as f:
    with gzip.open('data/kth_walkers/sparse_run1/ostermalm_001_1.tr.gz','rt') as f:
        reader = csv.reader(f, delimiter=' ')

        num_created = 0
        num_destroyed = 0
        max_concurrent = 0
        max_concurrent_time = None

        max_time = 3600

        for r in reader:
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

        print('concurrent', max_concurrent, max_concurrent_time, 'created', num_created)

        #test_gen = walkers_to_line_gen(100, {'filepath': 'data/kth_walkers/sparse_run1/ostermalm_005_1.tr.gz'})

        #for line in test_gen:
        #    print(line)
    


    # 001: 57 12156.6 created 2092
    # 005: 233 3057.6 created 4227
    # 007: 301 4387.8 created 5706