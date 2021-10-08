import json
import os

from pprint import pprint

from pydal import DAL, Field
import tables
import numpy as np
import math

from dist_eval import extract_contact_pairs, dist_time_iters_from_run

import matplotlib.pyplot as plt
from export_utility import slugify, cached, init_cache, load_env_config

from scipy.optimize import curve_fit


METHOD_PREFIX = 'export_'

CONFIDENCE_FILL_COLOR = '0.8'
COLOR_MAP = 'tab10'

NODE_DISTANCES = {'0-1': 1000000, '0-2': 1000000, '0-3': 1000000, '0-4': 1000000, '0-5': 1000000, '0-6': 1000000, '0-7': 1000000, '0-8': 1000000, '0-9': 1000000, '0-10': 1000000, '0-11': 1000000, '0-12': 1000000, '0-13': 1000000, '0-14': 1000000, '0-15': 1000000, '0-16': 1000000, '0-17': 1000000, '0-18': 1000000, '0-19': 1000000, '0-20': 1000000, '0-21': 1000000, '1-0': 1000000, '1-2': 3.456703910614525, '1-3': 7.182262569832403, '1-4': 8.756983240223464, '1-5': 9.99592336986849, '1-6': 12.67458100558659, '1-7': 14.5827188921466, '1-8': 16.38973014454004, '1-9': 19.25956340155856, '1-10': 23.618426986987057, '1-11': 1000000, '1-12': 10.956123613253236, '1-13': 16.06376138335258, '1-14': 20.00102499495382, '1-15': 14.643533714122508, '1-16': 7.259078212290502, '1-17': 19.11281115990325, '1-18': 22.483824607018203, '1-19': 20.029326606019676, '1-20': 12.003398037000936, '1-21': 21.10717485593909, '2-0': 1000000, '2-1': 3.456703910614525, '2-3': 3.725558659217878, '2-4': 5.300279329608939, '2-5': 11.548815065110565, '2-6': 9.217877094972065, '2-7': 11.703843161893602, '2-8': 13.890554657092665, '2-9': 17.18298684424475, '2-10': 21.958013293794885, '2-11': 1000000, '2-12': 8.213520326631636, '2-13': 16.78322092748957, '2-14': 20.583320329052885, '2-15': 16.630299144936114, '2-16': 10.715782122905027, '2-17': 20.674460584197654, '2-18': 21.10717485593909, '2-19': 19.98287321104847, '2-20': 13.324346506546563, '2-21': 20.23365749662015, '3-0': 1000000, '3-1': 7.182262569832403, '3-2': 3.725558659217878, '3-4': 1.574720670391061, '3-5': 14.006851853298748, '3-6': 5.492318435754187, '3-7': 9.065111605486074, '3-8': 11.753459590409685, '3-9': 15.506493496313173, '3-10': 20.672461185649556, '3-11': 1000000, '3-12': 6.128293616090922, '3-13': 18.273055858336907, '3-14': 21.815158524965582, '3-15': 19.24295161169144, '3-16': 14.441340782122905, '3-17': 22.828877710640477, '3-18': 20.188953013823387, '3-19': 20.59295738851494, '3-20': 15.503386057847282, '3-21': 19.93083529255105, '4-0': 1000000, '4-1': 8.756983240223464, '4-2': 5.300279329608939, '4-3': 1.574720670391061, '4-5': 15.20163728901716, '4-6': 3.9175977653631264, '4-7': 8.207207739016427, '4-8': 11.105216017477835, '4-9': 15.021096864165932, '4-10': 20.310900076649492, '4-11': 1000000, '4-12': 5.767303508177958, '4-13': 19.087346860392042, '4-14': 22.501630635053893, '4-15': 20.451236823116485, '4-16': 16.016061452513966, '4-17': 23.85622682640059, '4-18': 19.997816427428308, '4-19': 21.044706424498962, '4-20': 16.590746115989838, '4-21': 20.011089918554763, '5-0': 1000000, '5-1': 9.99592336986849, '5-2': 11.548815065110565, '5-3': 14.006851853298748, '5-4': 15.20163728901716, '5-6': 18.4235061916238, '5-7': 15.950513056858117, '5-8': 15.810784615771896, '5-9': 16.559083709354567, '5-10': 18.92012652422499, '5-11': 1000000, '5-12': 13.000065690858015, '5-13': 6.6292578810434435, '5-14': 10.526398092314913, '5-15': 5.250048593808522, '5-16': 10.36562729551123, '5-17': 9.172673371836899, '5-18': 17.075241639283604, '5-19': 11.61377113331385, '5-20': 2.093761015156856, '5-21': 14.492980887787395, '6-0': 1000000, '6-1': 12.67458100558659, '6-2': 9.217877094972065, '6-3': 5.492318435754187, '6-4': 3.9175977653631264, '6-5': 18.4235061916238, '6-7': 7.211843496651391, '6-8': 10.39125837151921, '6-9': 14.501233697567853, '6-10': 19.92950299612266, '6-11': 1000000, '6-12': 6.640434486390038, '6-13': 21.48320509358523, '6-14': 24.566739143820538, '6-15': 23.64507629420866, '6-16': 19.933659217877093, '6-17': 26.645001477883763, '6-18': 20.057919238521023, '6-19': 22.609542490960596, '6-20': 19.585419597527018, '6-21': 20.734877213860837, '7-0': 1000000, '7-1': 14.5827188921466, '7-2': 11.703843161893602, '7-3': 9.065111605486074, '7-4': 8.207207739016427, '7-5': 15.950513056858117, '7-6': 7.211843496651391, '7-8': 3.1794148748678186, '7-9': 7.289390200916461, '7-10': 12.71765949947127, '7-11': 1000000, '7-12': 3.6518984038161557, '7-13': 16.82634403068106, '7-14': 19.185370614938716, '7-15': 20.680057535494523, '7-16': 21.198147476481275, '7-17': 22.515475778433444, '7-18': 12.917968015561176, '7-19': 16.60557692832689, '7-20': 16.38237448216814, '7-21': 13.945927955712198, '8-0': 1000000, '8-1': 16.38973014454004, '8-2': 13.890554657092665, '8-3': 11.753459590409685, '8-4': 11.105216017477835, '8-5': 15.810784615771896, '8-6': 10.39125837151921, '8-7': 3.1794148748678186, '8-9': 4.109975326048643, '8-10': 9.538244624603452, '8-11': 1000000, '8-12': 5.728355820804471, '8-13': 15.4114737000369, '8-14': 17.242902685071293, '8-15': 20.068953934437964, '8-16': 22.479524469128, '8-17': 21.22465498696441, '8-18': 9.803731178757726, '8-19': 14.317277412164199, '8-20': 15.83130971307509, '8-21': 11.123315779038181, '9-0': 1000000, '9-1': 19.25956340155856, '9-2': 17.18298684424475, '9-3': 15.506493496313173, '9-4': 15.021096864165932, '9-5': 16.559083709354567, '9-6': 14.501233697567853, '9-7': 7.289390200916461, '9-8': 4.109975326048643, '9-10': 5.4282692985548096, '9-11': 1000000, '9-12': 9.378260101317938, '9-13': 14.439891026689196, '9-14': 15.355965943752768, '9-15': 20.013293250601517, '9-16': 24.650284959122356, '9-17': 20.185624804820563, '9-18': 5.882273547209652, '9-19': 11.977997727321677, '9-20': 16.05123353940481, '9-21': 7.887721532803746, '10-0': 1000000, '10-1': 23.618426986987057, '10-2': 21.958013293794885, '10-3': 20.672461185649556, '10-4': 20.310900076649492, '10-5': 18.92012652422499, '10-6': 19.92950299612266, '10-7': 12.71765949947127, '10-8': 9.538244624603452, '10-9': 5.4282692985548096, '10-11': 1000000, '10-12': 14.579139314169467, '10-13': 14.899015855739497, '10-14': 14.364525139664803, '10-15': 21.19814747648127, '10-16': 28.187512474266306, '10-17': 20.060112562829577, '10-18': 2.2660614525139664, '10-19': 10.677374301675975, '10-20': 17.851583550531593, '10-21': 5.72276536312849, '11-0': 1000000, '11-1': 1000000, '11-2': 1000000, '11-3': 1000000, '11-4': 1000000, '11-5': 1000000, '11-6': 1000000, '11-7': 1000000, '11-8': 1000000, '11-9': 1000000, '11-10': 1000000, '11-12': 1000000, '11-13': 1000000, '11-14': 1000000, '11-15': 1000000, '11-16': 1000000, '11-17': 1000000, '11-18': 1000000, '11-19': 1000000, '11-20': 1000000, '11-21': 1000000, '12-0': 1000000, '12-1': 10.956123613253236, '12-2': 8.213520326631636, '12-3': 6.128293616090922, '12-4': 5.767303508177958, '12-5': 13.000065690858015, '12-6': 6.640434486390038, '12-7': 3.6518984038161557, '12-8': 5.728355820804471, '12-9': 9.378260101317938, '12-10': 14.579139314169467, '12-11': 1000000, '12-13': 15.042825115237225, '12-14': 17.96923275665521, '12-15': 18.000268782448337, '12-16': 17.556488115736435, '12-17': 20.443002642539987, '12-18': 14.231736983878987, '12-19': 15.975016438580028, '12-20': 13.75263163837714, '12-21': 14.389452019340096, '13-0': 1000000, '13-1': 16.06376138335258, '13-2': 16.78322092748957, '13-3': 18.273055858336907, '13-4': 19.087346860392042, '13-5': 6.6292578810434435, '13-6': 21.48320509358523, '13-7': 16.82634403068106, '13-8': 15.4114737000369, '13-9': 14.439891026689196, '13-10': 14.899015855739497, '13-11': 1000000, '13-12': 15.042825115237225, '13-14': 3.954881917518506, '13-15': 6.451593067534036, '13-16': 16.917558127167457, '13-17': 5.8245844650768435, '13-18': 12.728468665586693, '13-19': 5.4070483892412655, '13-20': 4.606089749364724, '13-21': 9.50374152725524, '14-0': 1000000, '14-1': 20.00102499495382, '14-2': 20.583320329052885, '14-3': 21.815158524965582, '14-4': 22.501630635053893, '14-5': 10.526398092314913, '14-6': 24.566739143820538, '14-7': 19.185370614938716, '14-8': 17.242902685071293, '14-9': 15.355965943752768, '14-10': 14.364525139664803, '14-11': 1000000, '14-12': 17.96923275665521, '14-13': 3.954881917518506, '14-15': 9.11185716532576, '14-16': 20.693002296756447, '14-17': 6.0060470028165795, '14-18': 12.098463687150836, '14-19': 3.6871508379888267, '14-20': 8.456530279424248, '14-21': 8.641759776536311, '15-0': 1000000, '15-1': 14.643533714122508, '15-2': 16.630299144936114, '15-3': 19.24295161169144, '15-4': 20.451236823116485, '15-5': 5.250048593808522, '15-6': 23.64507629420866, '15-7': 20.680057535494523, '15-8': 20.068953934437964, '15-9': 20.013293250601517, '15-10': 21.19814747648127, '15-11': 1000000, '15-12': 18.000268782448337, '15-13': 6.451593067534036, '15-14': 9.11185716532576, '15-16': 12.717659499471273, '15-17': 4.9629890729643975, '15-18': 19.082837771643323, '15-19': 11.73411679974617, '15-20': 4.297744911890573, '15-21': 15.936128474981762, '16-0': 1000000, '16-1': 7.259078212290502, '16-2': 10.715782122905027, '16-3': 14.441340782122905, '16-4': 16.016061452513966, '16-5': 10.36562729551123, '16-6': 19.933659217877093, '16-7': 21.198147476481275, '16-8': 22.479524469128, '16-9': 24.650284959122356, '16-10': 28.187512474266306, '16-11': 1000000, '16-12': 17.556488115736435, '16-13': 16.917558127167457, '16-14': 20.693002296756447, '16-15': 12.717659499471273, '16-17': 17.68064857243567, '16-18': 26.633233008238527, '16-19': 21.974164378250073, '16-20': 12.312973225336044, '16-21': 24.477226023865402, '17-0': 1000000, '17-1': 19.11281115990325, '17-2': 20.674460584197654, '17-3': 22.828877710640477, '17-4': 23.85622682640059, '17-5': 9.172673371836899, '17-6': 26.645001477883763, '17-7': 22.515475778433444, '17-8': 21.22465498696441, '17-9': 20.185624804820563, '17-10': 20.060112562829577, '17-11': 1000000, '17-12': 20.443002642539987, '17-13': 5.8245844650768435, '17-14': 6.0060470028165795, '17-15': 4.9629890729643975, '17-16': 17.68064857243567, '17-18': 17.81014758550868, '17-19': 9.525552827465127, '17-20': 7.366336389107649, '17-21': 14.387732634778425, '18-0': 1000000, '18-1': 22.483824607018203, '18-2': 21.10717485593909, '18-3': 20.188953013823387, '18-4': 19.997816427428308, '18-5': 17.075241639283604, '18-6': 20.057919238521023, '18-7': 12.917968015561176, '18-8': 9.803731178757726, '18-9': 5.882273547209652, '18-10': 2.2660614525139664, '18-11': 1000000, '18-12': 14.231736983878987, '18-13': 12.728468665586693, '18-14': 12.098463687150836, '18-15': 19.082837771643323, '18-16': 26.633233008238527, '18-17': 17.81014758550868, '18-19': 8.411312849162009, '18-20': 15.883064081242408, '18-21': 3.4567039106145234, '19-0': 1000000, '19-1': 20.029326606019676, '19-2': 19.98287321104847, '19-3': 20.59295738851494, '19-4': 21.044706424498962, '19-5': 11.61377113331385, '19-6': 22.609542490960596, '19-7': 16.60557692832689, '19-8': 14.317277412164199, '19-9': 11.977997727321677, '19-10': 10.677374301675975, '19-11': 1000000, '19-12': 15.975016438580028, '19-13': 5.4070483892412655, '19-14': 3.6871508379888267, '19-15': 11.73411679974617, '19-16': 21.974164378250073, '19-17': 9.525552827465127, '19-18': 8.411312849162009, '19-20': 9.776887413994404, '19-21': 4.954608938547485, '20-0': 1000000, '20-1': 12.003398037000936, '20-2': 13.324346506546563, '20-3': 15.503386057847282, '20-4': 16.590746115989838, '20-5': 2.093761015156856, '20-6': 19.585419597527018, '20-7': 16.38237448216814, '20-8': 15.83130971307509, '20-9': 16.05123353940481, '20-10': 17.851583550531593, '20-11': 1000000, '20-12': 13.75263163837714, '20-13': 4.606089749364724, '20-14': 8.456530279424248, '20-15': 4.297744911890573, '20-16': 12.312973225336044, '20-17': 7.366336389107649, '20-18': 15.883064081242408, '20-19': 9.776887413994404, '20-21': 13.067300508624527, '21-0': 1000000, '21-1': 21.10717485593909, '21-2': 20.23365749662015, '21-3': 19.93083529255105, '21-4': 20.011089918554763, '21-5': 14.492980887787395, '21-6': 20.734877213860837, '21-7': 13.945927955712198, '21-8': 11.123315779038181, '21-9': 7.887721532803746, '21-10': 5.72276536312849, '21-11': 1000000, '21-12': 14.389452019340096, '21-13': 9.50374152725524, '21-14': 8.641759776536311, '21-15': 15.936128474981762, '21-16': 24.477226023865402, '21-17': 14.387732634778425, '21-18': 3.4567039106145234, '21-19': 4.954608938547485, '21-20': 13.067300508624527}

def get_dist(a,b):
    ks = ["{}-{}".format(a,b), "{}-{}".format(b,a)]
    for k in ks:
        if k in NODE_DISTANCES:
            return NODE_DISTANCES[k]

    assert(False)


device_dist_cache = {}

def get_dist_by_device_id(db, id_a, id_b):
    a = db.device[id_a]
    b = db.device[id_b]

    assert a and b

    return get_dist(a.number, b.number)



def load_plot_defaults():
    # Configure as needed
    plt.rc('lines', linewidth=2.0)
    plt.rc('legend', framealpha=1.0, fancybox=True)
    plt.rc('errorbar', capsize=3)
    plt.rc('pdf', fonttype=42)
    plt.rc('ps', fonttype=42)
    plt.rc('font', size=8, family="serif", serif=['Times New Roman'] + plt.rcParams['font.serif'])


def rssi_from_d(d, n, rssi_0):
    ad = -10*n*np.log10(d)+rssi_0
    return ad

def export_testbed_calibration_setup_times_at_distances(db, base_path):
    distance_groups = [5, 10, 15, 20]
    #distance_groups = [5, 10, 15, 20]
    range = 0.5 # the +- range for each distance

    types = ['testbed', 'calibration']
    runs = db((db.run.status == 'processed') & (db.run.group.belongs(types))).select()

    overall_data = {}
    overall_distances = {}

    for g in types:
        overall_data[g] = []
        overall_distances[g] = []

    for r in runs:
        name = slugify(("export_testbed_calibration_setup_times_with_dist_2", str(r.name), str(r.id)))
        print("Handling {}".format(name))

        def proc():
            distances = []
            data = []
            for ci in db((db.conn_info.run == r)).iterselect():
                if None in [ci.client_channel_up_us, ci.client_channel_down_us]:
                    continue    # we skip connections that have not been closed till the end
                data.append(
                    (ci.client_connection_success_us - ci.client_conn_init_us, ci.client_channel_up_us - ci.client_connection_success_us)
                )
                distances.append(get_dist_by_device_id(db, ci.client, ci.peripheral))
            return data, distances
        run_data, run_distances = cached(name, proc)
        overall_data[r.group] += run_data
        overall_distances[r.group] += run_distances

    setup_means = {}
    setup_stds = {}

    for g in types:
        setup_means[g] = [0.0 for dg in distance_groups]
        setup_stds[g] =  [0.0 for dg in distance_groups]

        for (i, dg) in enumerate(distance_groups):
            xs = []
            for (d, (con_set, chan_set)) in zip(overall_distances[g], overall_data[g]):
                if dg-range <= d < dg+range:
                    xs.append(con_set+chan_set)

            xs = np.array(xs) / 1000000.0
            setup_means[g][i] = np.mean(xs)
            setup_stds[g][i] = np.std(xs)


    width = 0.6       # the width of the bars: can also be len(x) sequence

    fig, ax = plt.subplots()

    x = np.arange(len(distance_groups))
    width = 0.4  # the width of the bars

    fig, ax = plt.subplots()
    rects1 = ax.bar(x - width/2, setup_means['testbed'],  width, yerr= setup_stds['testbed'], label='Testbed', capsize=0)
    rects2 = ax.bar(x + width/2, setup_means['calibration'], width,yerr= setup_stds['calibration'], label='Simulation', capsize=0)

    ax.set_xticks(x)
    ax.set_xticklabels(distance_groups)

    ax.set_ylabel('Link Setup Time [s]')
    ax.set_xlabel('Distance [m]')
    #ax.set_title('')
    ax.legend() # (loc='upper center', bbox_to_anchor=(0.5, -0.5), ncol=2)

    # Adapt the figure size as needed
    fig.set_size_inches(1.75, 2.0)
    plt.tight_layout()
    plt.savefig(export_dir + slugify(("testbed_calibration_setup_times")) + ".pdf", format="pdf")
    plt.close()


def export_testbed_calibration_bundle_transmission_time(db, base_path):
    distance_groups = [5, 10, 15, 20]
    range = 0.5 # the +- range for each distance
    types = ['testbed', 'calibration']
    runs = db((db.run.status == 'processed') & (db.run.group.belongs(types))).select()

    overall_data = {}
    overall_distances = {}

    for g in types:
        overall_data[g] = []
        overall_distances[g] = []

    for r in runs:
        name = slugify(("export_testbed_calibration_bundle_transmission_time_with_dist_2", str(r.name), str(r.id)))
        print("Handling {}".format(name))

        def proc():
            distances = []
            times = []
            for t in db((db.bundle_transmission.run == r) & (db.bundle_transmission.end_us != None )).iterselect():

                ci = db.conn_info[t.conn_info]
                sb = db.stored_bundle[t.source_stored_bundle]
                b = db.bundle[sb.bundle]

                if not b.is_sv:
                    times.append(t.end_us - t.start_us)
                    distances.append(get_dist_by_device_id(db, ci.client, ci.peripheral))
            return times, distances
        run_data, run_distances = cached(name, proc)
        overall_data[r.group] += run_data
        overall_distances[r.group] += run_distances

    bt_means = {}
    bt_std = {}

    print(overall_data)

    for g in types:
        bt_means[g] = [0.0 for dg in distance_groups]
        bt_std[g] =  [0.0 for dg in distance_groups]

        for (i, dg) in enumerate(distance_groups):
            xs = []
            for (d, x) in zip(overall_distances[g], overall_data[g]):
                if dg-range <= d < dg+range:
                    xs.append(x)
            print(xs)
            times = np.array(xs) / 1000000.0
            bt_means[g][i] = np.mean(times)
            bt_std[g][i] = np.std(times)


    fig, ax = plt.subplots()

    x = np.arange(len(distance_groups))
    width = 0.4  # the width of the bars

    fig, ax = plt.subplots()
    rects1 = ax.bar(x - width/2, bt_means['testbed'],  width, yerr= bt_std['testbed'], label='Testbed', capsize=0)
    rects2 = ax.bar(x + width/2, bt_means['calibration'], width,yerr= bt_std['calibration'], label='Simulation', capsize=0)

    ax.set_xticks(x)
    ax.set_xticklabels(distance_groups)

    ax.set_ylabel('Link Setup Time [s]')
    ax.set_xlabel('Distance [m]')

    ax.set_ylabel('Bundle Tx Time [s]')
    #ax.set_title('')
    #ax.legend()

    # Adapt the figure size as needed
    fig.set_size_inches(1.75, 3.0)
    plt.tight_layout()
    plt.savefig(export_dir + slugify(("testbed_calibration_bundle_transmission_time")) + ".pdf", format="pdf")
    plt.close()

def export_testbed_calibration_bundle_transmission_success(db, base_path):
    distance_groups = [5, 10, 15, 20]
    #distance_groups = [5, 10, 15, 20]
    range = 0.5 # the +- range for each distance

    types = ['testbed', 'calibration']
    runs = db((db.run.status == 'processed') & (db.run.group.belongs(types))).select()

    overall_data = {}
    overall_distances = {}

    for g in types:
        overall_data[g] = []
        overall_distances[g] = []

    for r in runs:
        name = slugify(("export_testbed_calibration_bundle_transmission_success_with_dist_2", str(r.name), str(r.id)))
        print("Handling {}".format(name))

        def proc():
            distances = []
            successes = []

            for t in db((db.bundle_transmission.run == r)).iterselect():
                ci = db.conn_info[t.conn_info]
                sb = db.stored_bundle[t.source_stored_bundle]
                b = db.bundle[sb.bundle]
                if not b.is_sv:
                    distances.append(get_dist_by_device_id(db, ci.client, ci.peripheral))
                    successes.append(t.end_us is not None)
            return successes, distances
        run_data, run_distances = cached(name, proc)
        overall_data[r.group] += run_data
        overall_distances[r.group] += run_distances

    bt_success_mean = {}
    for g in types:
        bt_success_mean[g] =  [0.0 for dg in distance_groups]

        for (i, dg) in enumerate(distance_groups):
            xs = []
            for (d, x) in zip(overall_distances[g], overall_data[g]):
                if dg-range <= d < dg+range:
                    xs.append(1.0 if x else 0.0)
            xs = np.array(xs)
            bt_success_mean[g][i] = np.mean(xs)*100.0

    fig, ax = plt.subplots()

    x = np.arange(len(distance_groups))
    width = 0.4  # the width of the bars

    fig, ax = plt.subplots()
    rects1 = ax.bar(x - width/2, bt_success_mean['testbed'],  width, label='Testbed', capsize=0)
    rects2 = ax.bar(x + width/2, bt_success_mean['calibration'], width,label='Simulation', capsize=0)

    ax.set_xticks(x)
    ax.set_xticklabels(distance_groups)

    ax.set_ylabel('Bundle Tx Success [%]')
    ax.set_xlabel('Distance [m]')
    ax.legend() # (loc='upper center', bbox_to_anchor=(0.5, -0.5), ncol=2)
    #ax.set_title('')
    #ax.legend()
    plt.axis([None, None, 0, 100])

    # Adapt the figure size as needed
    fig.set_size_inches(1.75, 1.5)
    plt.tight_layout()
    plt.savefig(export_dir + slugify(("testbed_calibration_bundle_transmission_success")) + ".pdf", format="pdf")
    plt.close()

def export_testbed_calibration_bundle_rssi_bars(db, base_path):
    distance_groups = [5, 10, 15, 20]
    #distance_groups = [5, 10, 15, 20]
    range = 0.5 # the +- range for each distance

    types = ['testbed', 'calibration']
    runs = db((db.run.status == 'processed') & (db.run.group.belongs(types))).select()

    overall_data = {}
    overall_distances = {}

    for g in types:
        overall_data[g] = []
        overall_distances[g] = []

    for r in runs:
        name = slugify(("export_testbed_calibration_bundle_rssi_bars_with_dist_2", str(r.name), str(r.id)))
        print("Handling {}".format(name))

        def proc():
            distances = []
            rssi_values = []
            for adv_received in db((db.advertisements.run == r)).iterselect():
                rssi_values.append(adv_received.rssi)
                distances.append(get_dist_by_device_id(db, adv_received.sender, adv_received.receiver))
            return rssi_values, distances

        run_data, run_distances = cached(name, proc)
        overall_data[r.group] += run_data
        overall_distances[r.group] += run_distances

    rssi_means = {}
    rssi_std = {}

    for g in types:
        rssi_means[g] = [0.0 for dg in distance_groups]
        rssi_std[g] =  [0.0 for dg in distance_groups]


        for (i, dg) in enumerate(distance_groups):
            xs = []
            for (d, x) in zip(overall_distances[g], overall_data[g]):
                if dg-range <= d < dg+range:
                    xs.append(x)
            xs = np.array(xs)
            rssi_means[g][i] = np.mean(xs)
            rssi_std[g][i] = np.std(xs)

    fig, ax = plt.subplots()

    x = np.arange(len(distance_groups))
    width = 0.4  # the width of the bars

    fig, ax = plt.subplots()
    rects1 = ax.bar(x - width/2, rssi_means['testbed'],  width, yerr= rssi_std['testbed'], label='Testbed', capsize=0)
    rects2 = ax.bar(x + width/2, rssi_means['calibration'], width,yerr= rssi_std['calibration'], label='Simulation', capsize=0)

    ax.set_xticks(x)
    ax.set_xticklabels(distance_groups)
    ax.set_ylabel('Mean RSSI [dBm]')
    ax.legend()
    #ax.set_title('')

    plt.axis([None, None, -100, 0])

    # Adapt the figure size as needed
    fig.set_size_inches(1.8, 1.5)
    plt.tight_layout()
    plt.savefig(export_dir + slugify(("testbed_calibration_bundle_rssi_bars")) + ".pdf", format="pdf")
    plt.close()

def export_testbed_calibration_bundle_rssi_per_distance(db, base_path):

    groups = ['testbed', 'calibration']
    labels = ['Testbed', 'Simulation']
    markers = ['o', 'o']

    runs = db((db.run.status == 'processed') & (db.run.group.belongs(groups))).select()

    overall_data = {}
    for g in groups:
        overall_data[g] = []

    for r in runs:
        name = slugify(("export_testbed_calibration_bundle_rssi_per_distance", str(r.name), str(r.id)))
        print("Handling {}".format(name))

        def proc():
            devs_cache = {}
            for d in db((db.device.run == r)).iterselect():
                devs_cache[d.id] = d.number
            data = []
            for adv_received in db((db.advertisements.run == r)).iterselect():
                dist = get_dist(devs_cache[adv_received.sender], devs_cache[adv_received.receiver])
                data.append((dist, adv_received.rssi))
            return data

        run_data = cached(name, proc)
        overall_data[r.group] += run_data

    plt.clf()

    #plt.plot([2],[-50], 'o', label='ADS', alpha=1.0, markersize=5)

    for (i, g) in enumerate(groups):
        distances = [x[0] for x in overall_data[g]]
        rssi_vals = [x[1] for x in overall_data[g]]


        #plt.plot(distances,rssi_vals, markers[i], label=labels[i], alpha=0.2, markersize=2)

        mean_dist = []
        mean_rssi_vals = []
        for d in sorted(set(distances)):
            mean_dist.append(d)

            rs = []
            for (d2, r2) in zip(distances, rssi_vals):
                if d2 == d:
                    rs.append(r2)

            mean_rssi_vals.append(np.mean(np.array(rs)))

        plt.plot(mean_dist,mean_rssi_vals, 'o', label=labels[i], alpha=1.0, markersize=2)

        finiteYmask = np.isfinite(mean_rssi_vals)
        ((n, rssi_0), _) = curve_fit(rssi_from_d, np.array(mean_dist)[finiteYmask], np.array(mean_rssi_vals)[finiteYmask], bounds=([0,-100], [10,0]))

        plt.plot(mean_dist, rssi_from_d(np.array(mean_dist), n, rssi_0), linestyle='--', label="{} Base n={}, rssi_0={}".format(labels[i], round(n, 2), round(rssi_0,2)), color='C{}'.format(i+1))
        print("{}: Base n={}, rssi_0={}".format(g, round(n, 2), round(rssi_0,2)))


    plt.legend()
    #fig, ax = plt.subplots()
    #fig.set_size_inches(1.9, 1.9)
    plt.tight_layout()

    plt.xlabel("Distance [m]")
    plt.ylabel("RSSI [dBm]")
    plt.axis([0, 30, -100, 0])
    plt.grid(True)
    plt.tight_layout()
    #plt.savefig(export_dir + slugify('testbed_calibration_bundle_rssi_per_distance') + ".pdf", format="pdf")
    plt.savefig(export_dir + slugify('testbed_calibration_bundle_rssi_per_distance') + ".png", format="png", dpi=1200)
    plt.close()


def export_app_connection_distance_histogramm(db, export_dir):
    runs = db((db.run.status == 'processed') & ((db.run.group == 'broadcast') | (db.run.group == 'unicast')) ).select()

    overall_data = []

    for r in runs:
        name = slugify(("export_app_connection_distance_histogramm", str(r.name), str(r.id)))
        print("Handling {}".format(name))

        config = json.loads(r.configuration_json)

        density = get_density(r)

        if density != 'sparse':
            continue    # for now, we only evaluate the largest area

        def proc():
            data = []

            for ci in db((db.conn_info.run == r)).iterselect():
                if None in [ci.client_channel_up_us, ci.peripheral_channel_up_us]:
                    continue # this was not a successful connection

                exact_start_us = min(ci.client_channel_up_us, ci.peripheral_channel_up_us)

                start_s = math.floor(exact_start_us/1000000)
                #exact_end_us = max(ci.client_disconnect_us or 0, ci.peripheral_disconnect_us or 0) or r.simulation_time
                #end_s = math.ceil(exact_end_us/1000000)

                for s in range(start_s, start_s+1):
                    dist = (db.executesql(
                        '''
                            SELECT dp.us, dp.d + (dp.d_next-dp.d) * (({us}-dp.us)/(dp.us_next-dp.us)) as d
                            FROM distance_pair dp WHERE dp.device_a = {device_a} AND dp.device_b = {device_b} AND dp.us = FLOOR({us}/1000000)*1000000
                        '''.format(device_a=ci.client, device_b=ci.peripheral, us=start_s*1000000)
                    ))
                    data.append(dist[0][1])
            return data

        run_data = cached(name, proc)
        overall_data += run_data

    plt.clf()
    #plt.legend()

    fig, ax = plt.subplots()

    mean = np.mean(np.array(overall_data))

    n, bins, patches = ax.hist(overall_data, 50, density=False)

    plt.axvline(mean, color='k', linestyle='dashed', linewidth=1)
    plt.text(mean+12, .925, "mean: {:.2f}m".format(mean), transform=ax.get_xaxis_transform())

    fig.set_size_inches(3.0, 2.5)
    plt.tight_layout()

    plt.xlabel("Distance [m]")
    plt.ylabel("# Connections")
    #plt.axis([0, 30, -100, 0])
    #plt.grid(True)
    plt.tight_layout()
    plt.savefig(export_dir + slugify('export_app_connection_distance_histogramm') + ".pdf", format="pdf")
    plt.close()

def export_testbed_rssi_per_distance(db, export_dir):

    runs = db((db.run.status == 'processed') & (db.run.group == 'testbed')).select()

    overall_data = []

    def handle_adv_data(name, data):
        max_dist = 25

        xs = range(1, max_dist+1)

        per_dist = [[] for x in xs]

        for d in data:
            dist = round(d[1])
            if 1 <= dist <= max_dist:
                per_dist[dist-1].append(d[0])

        per_dist_mean = [np.nanmean(vals) for vals in per_dist]
        per_dist_lq = [np.nanpercentile(vals, 2.5) for vals in per_dist]
        per_dist_uq = [np.nanpercentile(vals, 97.5) for vals in per_dist]

        finiteYmask = np.isfinite(per_dist_mean)
        ((n, rssi_0), _) = curve_fit(rssi_from_d, np.array(xs)[finiteYmask], np.array(per_dist_mean)[finiteYmask], bounds=([0,-100], [10,0]))

        plt.clf()
        plt.plot(xs, per_dist_mean, linestyle='-', label="Mean", color='C1')
        plt.plot(xs, rssi_from_d(np.array(xs), n, rssi_0), linestyle='--', label="Base n={}, rssi_0={}".format(round(n, 2), round(rssi_0,2)), color='C2')
        plt.fill_between(xs, per_dist_lq, per_dist_uq, color=CONFIDENCE_FILL_COLOR, label='95% Confidence Interval')
        plt.legend()
        plt.xlabel("Distance [m]")
        plt.ylabel("RSSI [dBm]")
        plt.axis([0, max_dist, -100, -40])
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(export_dir + slugify(name) + ".pdf", format="pdf")
        plt.close()


    for r in runs:
        name = slugify(("testbed rssi per distance", str(r.name), str(r.id)))
        print("Handling {}".format(name))

        def proc():
            devs_cache = {}
            for d in db((db.device.run == r)).iterselect():
                devs_cache[d.id] = d.number
            data = []
            for adv_received in db((db.advertisements.run == r)).iterselect():
                dist = get_dist(devs_cache[adv_received.sender], devs_cache[adv_received.receiver])
                data.append((adv_received.rssi, dist))
            return data

        data = proc() # cached(name, proc)
        handle_adv_data(name, data)

        overall_data += data

        handle_adv_data(slugify("RSSI per Distance (overall) {}".format(r.id)), overall_data)

def export_pre_calibration_connection_times(db, base_path):
    runs = db((db.run.status == 'processed') & (db.run.group == 'pre-calibration')).select()

    def handle_conn_times(name, data):
        keys = ['connection_success_after_us', 'channel_up_after_us', 'first_bundle_received_after_us', 'first_bundle_payload_length']
        bar_keys = keys[0:3]
        per_key = {}

        for k in keys:
            per_key[k] = []

        for d in data:
            for k in keys:
                per_key[k].append(d[k])


        means = []
        stds = []

        for k in bar_keys:
            np_data = np.array(per_key[k])/1000.0
            means.append(np.mean(np_data))
            stds.append(np.std(np_data))

        size_np_data = np.array(per_key['first_bundle_payload_length'])
        size_mean = np.mean(size_np_data)
        size_std = np.std(size_np_data)

        plt.clf()

        fig, ax = plt.subplots()

        ax.bar(["Conn. Setup", "Channel Setup", "First Bundle"], means[0:3], yerr=stds[0:3], align='center',
               ecolor='black', capsize=5, color=['C1', 'C2', 'C3'])

        ax.yaxis.grid(True)
        plt.ylabel("Time [ms]")
        plt.axis([None, None, 0, 300])

        # Adapt the figure size as needed
        fig.set_size_inches(5.0, 8.0)
        plt.tight_layout()
        plt.savefig(export_dir + slugify((name, 5.0, 8.0)) + ".pdf", format="pdf")
        plt.close()

        with open(export_dir + slugify((name, "first_bundle_payload_length")) + ".txt", "w") as f:
            f.write("avg size: {} std: {}".format(size_mean, size_std))


    overall_data = []

    for r in runs:
        name = slugify(("single_run_pre_calibratiin_connection_times_v2", str(r.name), str(r.id)))
        print("Handling {}".format(name))

        def proc():
            data = []
            for ci in db((db.conn_info.run == r)).iterselect():
                if None in [ci.client_channel_up_us, ci.client_channel_down_us]:
                    continue    # we skip connections that have not been closed till the end

                sb_res = db((db.stored_bundle.device == ci.client)
                            & (db.stored_bundle.created_us >= ci.client_channel_up_us)
                            & (db.stored_bundle.created_us <= ci.client_channel_down_us)
                            ).select(orderby=db.stored_bundle.created_us)

                if len(sb_res) == 0:
                    continue    # we skip connections without any bundle transmissions

                first_sb = None
                first_b = None

                for sb in sb_res:
                    b = db.bundle[sb.bundle]
                    if b and b.source != ci.client:
                        first_sb = sb
                        first_b = b
                        break

                if not first_sb:
                    continue

                assert(first_b)
                assert(first_b.is_sv == True or first_b.is_sv == 'T')   # the first bundle received should in all cases be a sv
                assert(first_b.source != ci.client)   # the first bundle received should in all cases be a sv

                first_bundle_received_us = first_sb.created_us
                assert(ci.client_channel_up_us <= first_bundle_received_us <= ci.client_channel_down_us)

                e = {
                    'connection_success_after_us': ci.client_connection_success_us - ci.client_conn_init_us,
                    'channel_up_after_us': ci.client_channel_up_us - ci.client_connection_success_us,
                    'first_bundle_received_after_us': first_bundle_received_us - ci.client_channel_up_us,
                    'first_bundle_payload_length': first_b.payload_length
                }

                data.append(e)

            return data

        run_data = cached(name, proc)
        overall_data += run_data

        handle_conn_times(name, run_data)

    # we now export the whole thing
    handle_conn_times("testbed_connection_times", overall_data)


def export_pair_packets(db, base_path):

    res = db.executesql('''
        SELECT
        r.id, COUNT(DISTINCT b.id)
        FROM run r 
        LEFT JOIN bundle_transmission bt ON bt.run = r.id
        LEFT JOIN stored_bundle sb ON sb.id = bt.source_stored_bundle
        LEFT JOIN bundle b ON sb.bundle = b.id AND b.destination_eid = "dtn://fake"
        GROUP BY r.id
        ORDER BY r.name ASC
    ''')

    data = {}

    for r in res:
        run = db.run[r[0]]
        config = json.loads(run.configuration_json)
        model_options = json.loads(config['SIM_MODEL_OPTIONS'])

        k = round(model_options['distance'])
        if k not in data:
            data[k] = []
        data[k].append(r[1])

    sorted_keys = sorted(data.keys())

    avg = []

    for k in sorted_keys:
        assert len(data[k])
        avg.append(sum(data[k]) / len(data[k]))


    pprint(sorted_keys)
    pprint(avg)

    # TODO: Calculate error bars and export as graph!

    pass

def export_pair_timings(db, base_path):

    # ONLY times for the source node!
    # AVG: advertising (the time without an active connection)
    # AVG: conn_init -> channel_up_us
    # AVG: channel_up_us -> channel_down_us (of which bundle and sv transmissions? -> just use the direction source -> proxy
    # AVG: channel_disconnect -> conn_init


    # AVG idle/advertisement time


    res = db.executesql('''
        SELECT
        r.id, ci.id, ci.client_conn_init_us,
        MIN(ci.client_channel_up_us, ci.peripheral_channel_up_us),
        MIN(ci.client_connection_success_us, ci.peripheral_connection_success_us),
        MIN(COALESCE(ci.client_channel_down_us, r.simulation_time), COALESCE(ci.peripheral_channel_down_us, r.simulation_time)),
        MIN(COALESCE(ci.client_disconnect_us, r.simulation_time), COALESCE(ci.peripheral_disconnect_us, r.simulation_time)),
        MAX(ci.client_channel_up_us, ci.peripheral_channel_up_us),
        MAX(ci.client_connection_success_us, ci.peripheral_connection_success_us),
        MAX(COALESCE(ci.client_channel_down_us, r.simulation_time), COALESCE(ci.peripheral_channel_down_us, r.simulation_time)),
        MAX(COALESCE(ci.client_disconnect_us, r.simulation_time), COALESCE(ci.peripheral_disconnect_us, r.simulation_time))
        FROM run r
        JOIN conn_info ci ON ci.run = r.id
        WHERE (ci.client_channel_up_us + ci.peripheral_channel_up_us + ci.client_connection_success_us + ci.peripheral_connection_success_us) IS NOT NULL 
    ''')

    pprint(res)
    # TODO: Calculate error bars and export as graph!

    pass

def export_rssi_per_distance(db, export_dir):

    runs = db((db.run.status == 'processed') & (db.run.group == RUN_GROUP)).select()

    overall_limit = 5000
    overall_data = []


    def handle_adv_data(name, data):
        max_dist = 500

        xs = range(1, max_dist+1)

        per_dist = [[] for x in xs]

        for d in data:
            dist = round(d[1])
            if 1 <= dist <= max_dist:
                per_dist[dist-1].append(d[0])

        per_dist_mean = [np.nanmean(vals) for vals in per_dist]
        per_dist_lq = [np.nanpercentile(vals, 2.5) for vals in per_dist]
        per_dist_uq = [np.nanpercentile(vals, 97.5) for vals in per_dist]


        def rssi_from_d(d, n, rssi_0):
            ad = -10*n*np.log10(d)+rssi_0
            return ad
        finiteYmask = np.isfinite(per_dist_mean)
        ((n, rssi_0), _) = curve_fit(rssi_from_d, np.array(xs)[finiteYmask], np.array(per_dist_mean)[finiteYmask], bounds=([0,-100], [10,0]))

        plt.clf()
        plt.plot(xs, per_dist_mean, linestyle='-', label="Mean", color='C1')
        plt.plot(xs, rssi_from_d(np.array(xs), n, rssi_0), linestyle='--', label="Base n={}, rssi_0={}".format(round(n, 2), round(rssi_0,2)), color='C2')
        plt.fill_between(xs, per_dist_lq, per_dist_uq, color=CONFIDENCE_FILL_COLOR, label='95% Confidence Interval')
        plt.legend()
        plt.xlabel("Distance [m]")
        plt.ylabel("RSSI [dBm]")
        plt.axis([0, max_dist, -100, -40])
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(export_dir + slugify(name) + ".pdf", format="pdf")
        plt.close()


    for r in runs:
        name = slugify(("rssi per distance", str(r.name), str(r.id), str(overall_limit)))
        print("Handling {}".format(name))

        def proc():
            limit = 1000   # batch processing slows down everything right now
            offset = 0

            data = []

            while True:
                rows = db.executesql('''
                    SELECT adv.rssi as rssi, dp.d + (dp.d_next-dp.d)* ((adv.received_us-dp.us)/(dp.us_next-dp.us)) as d
                    FROM (SELECT * FROM advertisements WHERE run = {} LIMIT {} OFFSET {}) as adv
                    JOIN distance_pair dp ON dp.run = adv.run AND dp.device_a = adv.sender AND dp.device_b = adv.receiver AND dp.us = FLOOR(adv.received_us/1000000)*1000000
                '''.format(r.id, limit, offset))

                # rows = db.executesql('''
                #     SELECT adv.rssi as rssi, adv.received_us, pr.pa_x, pr.pa_y, pr.pb_x, pr.pb_y, pr.pc_x, pr.pc_y, pr.pd_x, pr.pd_y
                #     FROM advertisements adv
                #     JOIN pos_pair pr ON pr.run = adv.run AND pr.device_a = adv.sender AND pr.device_b = adv.receiver AND pr.us = FLOOR(adv.received_us/1000000)*1000000
                #     WHERE adv.run = {} LIMIT {} OFFSET {}
                # '''.format(r.id, limit, offset))

                for row in rows:
                    if len(data) < overall_limit:
                        data.append(row)

                if len(data) == overall_limit:
                    break

                offset += limit

                if len(rows) < limit:
                    break

            return data

        data = cached(name, proc)
        handle_adv_data(name, data)

        overall_data += data

        handle_adv_data(slugify("RSSI per Distance (overall) {}".format(r.id)), overall_data)

def export_mean_path_loss(db, export_dir):
    # We only do this for testbed runs
    runs = db((db.run.status == 'processed') & (db.run.group == 'testbed')).select()

    def handle_loss_histogramm(name, data):
        step = 1.0
        xs = range(-100, 0, 1)
        per_db = [0 for x in xs]
        for d in data:
            l = round(d)
            if 0 <= l < len(per_db):
                per_db[l] += 1
        plt.clf()
        plt.hist(per_db, len(per_db))
        plt.xlabel("RSSI [dB]")
        plt.ylabel("Amount")
        plt.tight_layout()
        plt.savefig(export_dir + slugify((name, 'histogramm')) + ".pdf", format="pdf")
        plt.close()

    overall_limit = 1000

    for r in runs:
        print("Handling {}".format(r.name))
        devices = db((db.device.run == r)).select()

        for a in devices:
            for b in devices:
                if a == b:
                    continue

                name = slugify(("rssi loss", str(r.name), str(r.id), str(overall_limit), a.number, b.number))

                def proc():
                    rows = db((db.advertisements.sender == a) & (db.advertisements.receiver == b)).select(limitby=(0, overall_limit))
                    return [x.rssi for x in rows]

                data = cached(name, proc)
                handle_loss_histogramm(name, data)

                per_dist_mean = np.nanmean(data)
                per_dist_lq = np.nanpercentile(data, 2.5)
                per_dist_uq = np.nanpercentile(data, 97.5)

                print(name)
                print("per_dist_mean: {}".format(per_dist_mean))
                print("per_dist_lq: {}".format(per_dist_lq))
                print("per_dist_uq: {}".format(per_dist_uq))


def export_advertisement_reception_rate(db, export_dir):
    runs = db((db.run.status == 'processed') & (db.run.group == RUN_GROUP)).select()

    overall_limit = 1000
    overall_data = []

    def handle_adv_data(name, data):
        max_dist = 501
        step = 10

        xs = range(1, max_dist+1, step)

        per_dist = [[] for x in xs]

        for d in data:
            dist = round(d[-2])
            if 1 <= dist <= max_dist:
                index = math.ceil(((dist-1)/step))
                per_dist[index].append(d[-1])

        per_dist_mean = [np.nanmean(vals)*100 for vals in per_dist]
        per_dist_lq = [np.nanpercentile(vals, 2.5)*100 for vals in per_dist]
        per_dist_uq = [np.nanpercentile(vals, 97.5)*100 for vals in per_dist]

        plt.clf()
        plt.plot(xs, per_dist_mean, linestyle='-', label="Mean", color='C1')
        plt.fill_between(xs, per_dist_lq, per_dist_uq, color=CONFIDENCE_FILL_COLOR, label='95% Confidence Interval')
        plt.legend()
        plt.xlabel("Distance [m]")
        plt.ylabel("Adv Reception Rate [%]")
        plt.axis([0, max_dist, 0, 100])
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(export_dir + slugify(name) + ".pdf", format="pdf")
        plt.close()


    for r in runs:
        name = slugify(("adv reception rate per distance", str(r.name), str(r.id), str(overall_limit)))
        print("Handling {}".format(name))

        def proc():
            limit = 20   # batch processing slows down everything right now
            offset = 0

            data = []

            while True:
                rows = db.executesql('''
                    SELECT adv.run, adv.sender, adv.received_us, dp.device_b, dp.d + (dp.d_next-dp.d)* ((adv.received_us-dp.us)/(dp.us_next-dp.us)) as d,
                    CASE WHEN EXISTS (SELECT * FROM advertisements as ra WHERE ra.run = adv.run AND ra.received_us = adv.received_us AND ra.receiver = dp.device_b)
                            THEN 1 
                            ELSE 0
                        END as received
                    FROM (SELECT DISTINCT run, sender, received_us, connectable FROM advertisements WHERE run = {} LIMIT {} OFFSET {}) as adv
                    JOIN distance_pair dp ON dp.run = adv.run AND dp.device_a = adv.sender AND dp.device_b != adv.sender AND dp.us = FLOOR(adv.received_us/1000000)*1000000  
                '''.format(r.id, limit, offset))


                # rows = db.executesql('''
                #     SELECT adv.rssi as rssi, adv.received_us, pr.pa_x, pr.pa_y, pr.pb_x, pr.pb_y, pr.pc_x, pr.pc_y, pr.pd_x, pr.pd_y
                #     FROM advertisements adv
                #     JOIN pos_pair pr ON pr.run = adv.run AND pr.device_a = adv.sender AND pr.device_b = adv.receiver AND pr.us = FLOOR(adv.received_us/1000000)*1000000
                #     WHERE adv.run = {} LIMIT {} OFFSET {}
                # '''.format(r.id, limit, offset))

                for row in rows:
                    data.append(row)

                offset += limit

                if len(rows) < limit or offset >= overall_limit:
                    break

            return data

        data = cached(name, proc)
        handle_adv_data(name, data)

        overall_data += data

        handle_adv_data(slugify("Adv reception rate per Distance (overall) {}".format(r.id)), overall_data)

def export_bundle_transmission_success_per_distance(db, base_path):
    '''
SELECT ROUND(d/5)*5 as de, AVG(end_us IS NOT NULL) FROM (



FROM bundle_transmission bt
JOIN stored_bundle ssb ON ssb.id = bt.source_stored_bundle
JOIN conn_info ci ON ci.id = bt.conn_info
JOIN bundle b ON b.id = ssb.bundle AND b.destination_eid = 'dtn://fake' AND b.is_sv = 'F'
JOIN run r ON r.id = bt.run

WHERE r.status = 'finished' LIMIT 10000)
 '''
    pass

def export_bundle_transmission_time_per_distance(db, base_path):

    runs = db((db.run.status == 'processed') & (db.run.group == RUN_GROUP) & (db.run.group != 'testbed') & (db.run.group != 'virtual_testbed')).select()

    MIN_SAMPLES = 10

    def handle_transmission_success(name, data):
        max_dist = 501
        step = 10

        xs = range(1, max_dist+1, step)

        per_dist = [[] for x in xs]

        for d in data:
            dist = round(d[-1])
            if 1 <= dist <= max_dist:
                index = math.ceil(((dist-1)/step))
                per_dist[index].append(1 if  d[1] is not None else 0)

        if MIN_SAMPLES > 0:
            for i in range(len(per_dist)):
                if len(per_dist[i]) < MIN_SAMPLES:
                    per_dist[i] = []


        per_success_mean = [np.nanmean(vals)*100 for vals in per_dist]

        plt.clf()
        plt.plot(xs, per_success_mean, linestyle='-', label="Mean", color='C1')
        #plt.fill_between(xs, per_success_lq, per_success_uq, color=CONFIDENCE_FILL_COLOR, label='95% Confidence Interval')
        plt.legend()
        plt.xlabel("Distance [m]")
        plt.ylabel("Bundle Tx Success Rate [%]")
        plt.axis([0, max_dist, 0, 100])
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(export_dir + slugify((name, "Bundle Transmission Success Rate")) + ".pdf", format="pdf")
        plt.close()

    def handle_transmission_times(name, data):
        max_dist = 501
        step = 10

        xs = range(1, max_dist+1, step)

        per_dist = [[] for x in xs]

        for d in data:
            dist = round(d[-1])
            if 1 <= dist <= max_dist and d[1] is not None:
                index = math.ceil(((dist-1)/step))
                per_dist[index].append((d[1]-d[0])/1000000)

        if MIN_SAMPLES > 0:
            for i in range(len(per_dist)):
                if len(per_dist[i]) < MIN_SAMPLES:
                    per_dist[i] = []

        per_dist_mean = [np.nanmean(vals) for vals in per_dist]
        per_dist_lq = [np.nanpercentile(vals, 2.5) for vals in per_dist]
        per_dist_uq = [np.nanpercentile(vals, 97.5) for vals in per_dist]

        plt.clf()
        plt.plot(xs, per_dist_mean, linestyle='-', label="Mean", color='C1')
        plt.fill_between(xs, per_dist_lq, per_dist_uq, color=CONFIDENCE_FILL_COLOR, label='95% Confidence Interval')
        plt.legend()
        plt.xlabel("Distance [m]")
        plt.ylabel("Bundle Transmission Time [s]")
        plt.axis([0, max_dist, 0, 60])
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(export_dir + slugify((name, "Bundle Transmission By Distance")) + ".pdf", format="pdf")
        plt.close()

    overall_data = []

    for r in runs:

        run_config = json.loads(r.configuration_json)
        name = slugify(("transmission time per distance", str(r.name), str(r.id)))



        def proc():
            bundle_transmission_times = []
            bundle_transmission_success = [] # TODO?

            data = []

            for ci in db((db.conn_info.run == r)).iterselect():

                if None in [ci.client_channel_up_us, ci.peripheral_channel_up_us, ci.client_channel_down_us, ci.peripheral_channel_down_us]:
                    continue

                exact_start_us = min(ci.client_channel_up_us, ci.peripheral_channel_up_us)
                exact_end_us = max(ci.client_channel_down_us, ci.peripheral_channel_down_us)

                start_s = math.floor(exact_start_us/1000000)
                end_s = math.ceil(exact_end_us/1000000)

                distances = []
                for s in range(start_s, end_s+1):
                    dist = (db.executesql(
                        '''
                            SELECT dp.us, dp.d + (dp.d_next-dp.d) * (({us}-dp.us)/(dp.us_next-dp.us)) as d
                            FROM distance_pair dp WHERE dp.device_a = {device_a} AND dp.device_b = {device_b} AND dp.us = FLOOR({us}/1000000)*1000000
                        '''.format(device_a=ci.client, device_b=ci.peripheral, us=s*1000000)
                    ))
                    distances.append(dist[0][1])

                bt_rows = (db.executesql(
                    '''
                        SELECT bt.start_us, bt.end_us
                        FROM bundle_transmission bt
                        JOIN stored_bundle sb ON sb.id = bt.source_stored_bundle
                        JOIN bundle b ON b.id = sb.bundle AND b.is_sv = 'F'
                        WHERE bt.conn_info = {ci_id}
                        GROUP BY bt.id
                    '''.format(ci_id=ci.id)
                ))
                for bt in bt_rows:
                    transmission_start_s = math.floor(bt[0]/1000000)

                    if bt[1] is None:
                        transmission_end_s = transmission_start_s
                    else:
                        transmission_end_s = math.floor(bt[1]/1000000)

                    transmission_distances = []
                    for s in range(transmission_start_s, transmission_end_s+1):
                        transmission_distances.append(distances[transmission_start_s-start_s])
                    data.append((bt[0], bt[1], sum(transmission_distances) / len(transmission_distances)))

            return data

        data = cached(name, proc)
        handle_transmission_times(name, data)
        handle_transmission_success(name, data)

        overall_data += data

    handle_transmission_times(slugify("Bundle Transmission times (overall)"), overall_data)
    handle_transmission_success(slugify("Bundle Transmission times (overall) {}"), overall_data)



            # t_rows = (db.executesql(
                #     '''
                #         SELECT bt.start_us, bt.end_us, MAX(dp.d), MIN(dp.d), AVG(dp.d)
                #         FROM bundle_transmission bt
                #         JOIN stored_bundle sb ON sb.id = bt.source_stored_bundle
                #         JOIN bundle b ON b.id = sb.bundle AND b.is_sv = 'F'
                #         JOIN distance_pair dp ON dp.device_a = {device_a} AND dp.device_b = {device_b} AND dp.us BETWEEN FLOOR(bt.start_us/1000000)*1000000 AND FLOOR(bt.end_us/1000000)*1000000
                #         WHERE bt.conn_info = {ci_id} AND bt.end_us IS NOT NULL
                #         GROUP BY bt.id
                #     '''.format(ci_id=ci.id, device_a=ci.client, device_b=ci.peripheral)
                # ))



                # t_rows = (db.executesql(
                #         '''
                #             SELECT bt.start_us, bt.end_us, dp.d + (dp.d_next-dp.d) * ((bt.start_us-dp.us)/(dp.us_next-dp.us)) as d
                #             FROM bundle_transmission bt ON bt.conn_info = ci.id
                #             JOIN stored_bundle sb ON sb.id = bt.source_stored_bundle
                #             JOIN bundle b ON b.id = sb.bundle AND b.is_sv = 'F'
                #             JOIN distance_pair dp ON dp.device_a = ci.client AND dp.device_b = ci.peripheral AND dp.us = FLOOR(bt.start_us/1000000)*1000000
                #             WHERE ci.id = {}
                #         '''.format(ci.id, ci.client, ci.peripheral)
                # ))

    '''
SELECT ROUND(d/5)*5 as de, AVG(end_us-start_us)/1000000 FROM (

SELECT bt.*, dp.d + (dp.d_next-dp.d)* ((bt.start_us-dp.us)/(dp.us_next-dp.us)) as d

FROM bundle_transmission bt
JOIN stored_bundle ssb ON ssb.id = bt.source_stored_bundle
JOIN conn_info ci ON ci.id = bt.conn_info
JOIN bundle b ON b.id = ssb.bundle AND b.b.destination_eid = 'dtn://fake' AND b.is_sv = 'F'
JOIN run r ON r.id = bt.run
JOIN distance_pair dp ON dp.device_a = ci.client AND dp.device_b = ci.peripheral AND dp.us = FLOOR(bt.start_us/1000000)*1000000
WHERE r.status = 'finished') as a
GROUP BY de
 '''
    pass

def export_bundle_transmission_time_per_neighbors(db, base_path):
    '''
SELECT ROUND(d/5)*5 as de, AVG(end_us-start_us)/1000000 FROM (

SELECT bt.*, dp.d + (dp.d_next-dp.d)* ((bt.start_us-dp.us)/(dp.us_next-dp.us)) as d

FROM bundle_transmission bt
JOIN stored_bundle ssb ON ssb.id = bt.source_stored_bundle
JOIN conn_info ci ON ci.id = bt.conn_info
JOIN bundle b ON b.id = ssb.bundle AND b.b.destination_eid = 'dtn://fake' AND b.is_sv = 'F'
JOIN run r ON r.id = bt.run
JOIN distance_pair dp ON dp.device_a = ci.client AND dp.device_b = ci.peripheral AND dp.us = FLOOR(bt.start_us/1000000)*1000000
WHERE r.status = 'finished') as a
GROUP BY de
 '''
    pass

def export_bundle_propagation_epidemic(db, base_path):

    length_s = 250 #3000 TODO: use 3000 again!
    step = 1.0

    runs = db((db.run.status == 'processed') & (db.run.group == 'broadcast')).select()
    max_step = math.ceil(length_s/step)

    per_density_reception_steps = {
        'sparse': [],
        'populated': [],
        'dense': [],
        'very_dense': []
    }

    for r in runs:

        run_config = json.loads(r.configuration_json)
        name = slugify(("epidemic propagation", str(r.name), str(r.id), str(length_s), str(step)))


        model_options = json.loads(run_config['SIM_MODEL_OPTIONS'])

        print("Handling run {}".format(name))

        density = get_density(r)

        def proc():
            run_reception_steps = []

            bundles = db((db.bundle.run == r) & (db.bundle.destination_eid == 'dtn://fake') & (db.bundle.creation_timestamp_ms <= ((r.simulation_time/1000)-(length_s*1000)))).iterselect()
            for b in bundles:
                receptions_steps = [0]*(max_step+1)

                res = db.executesql(
                    '''
                        SELECT us, receiver_eid = destination_eid FROM bundle_reception
                        WHERE bundle = {}
                        ORDER BY us ASC
                    '''.format(b.id)
                )

                for row in res:
                    ms = (row[0]/1000)-b.creation_timestamp_ms
                    ts = round((ms/1000) / step)
                    for x in range(ts, max_step+1):
                        receptions_steps[x] += 1
                run_reception_steps.append(receptions_steps)
            return run_reception_steps

        run_reception_steps = cached(name, proc)
        per_density_reception_steps[density] += run_reception_steps

    positions = range(0, max_step + 1)
    plt.clf()

    mean = {}
    cis = {}


    fig, ax = plt.subplots()
    fig.set_size_inches(3.0, 3.0)

    for k in per_density_reception_steps:
        if len(per_density_reception_steps[k]) > 0:
            per_density_reception_steps[k] = np.array(per_density_reception_steps[k], dtype=np.float64)
            per_density_reception_steps[k] = np.swapaxes(per_density_reception_steps[k], 0, 1)  # we swap the axes to get all t=0 values at the first position together
            per_density_reception_steps[k] = (per_density_reception_steps[k] / 24.0) * 100.0
            mean[k] = np.mean(per_density_reception_steps[k], axis=1)
            cis[k] = np.percentile(per_density_reception_steps[k], [2.5, 97.5], axis=1)


    if 'sparse' in mean:
        plt.plot(positions, mean['sparse'], linestyle='-', label="Sparse", alpha=0.75, color='C1')
        plt.fill_between(positions, cis['sparse'][0], cis['sparse'][1], color='C1', label='95% CI Sparse', alpha=0.25, linewidth=0.0)

    if 'populated' in mean:
        plt.plot(positions, mean['populated'], linestyle='-', label="Populated", alpha=0.75, color='C2')
        plt.fill_between(positions, cis['populated'][0], cis['populated'][1], color='C2', label='95% CI Populated', alpha=0.25, linewidth=0.0)

    if 'dense' in mean:
        plt.plot(positions, mean['dense'], linestyle='-', label="Dense", alpha=0.75, color='C4')
        plt.fill_between(positions, cis['dense'][0], cis['dense'][1], color='C4', label='95% CI Dense', alpha=0.25, linewidth=0.0)

    if 'very_dense' in mean:
        plt.plot(positions, mean['very_dense'], linestyle='-', label="Very Dense", alpha=0.75, color='C5')
        plt.fill_between(positions, cis['very_dense'][0], cis['very_dense'][1], color='C5', label='95% CI Very Dense', alpha=0.25, linewidth=0.0)

    plt.legend()
    plt.xlabel("Time [s]")
    plt.ylabel('Bundle Reception Rate [%]')
    plt.axis([0, 300, None, None])
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(base_path + "epidemic_propagation" + ".pdf", format="pdf")
    plt.close()

def export_fake_bundle_propagation_direct(db, base_path):

    length_s = 250 # 3000 TODO use real value again!
    step = 1.0

    runs = db((db.run.status == 'processed') & (db.run.group == 'unicast')).select()

    max_step = math.ceil(length_s/step)

    per_density_reception_steps = {
        'sparse': [],
        'populated': [],
        'dense': [],
        'very_dense': []
    }

    for r in runs:
        run_config = json.loads(r.configuration_json)
        name = slugify(("direct propagation 2", str(r.name), str(r.id), str(length_s), str(step)))

        density = get_density(r)

        def proc():
            run_reception_steps = []
            # & (db.bundle.creation_timestamp_ms <= ((r.simulation_time/1000)-(length_s*1000)))
            bundles = db((db.bundle.run == r) & (db.bundle.destination_eid == 'dtn://source') & (db.bundle.creation_timestamp_ms <= ((r.simulation_time/1000)-(length_s*1000)))).iterselect()
            for b in bundles:
                if b.creation_timestamp_ms > ((r.simulation_time/1000)-(length_s*1000)):
                    continue    # this bundle is too late

                receptions_steps = [0]*(max_step+1)

                res = db.executesql(
                    '''
                        SELECT us FROM bundle_reception
                        WHERE bundle = {} AND receiver_eid = destination_eid
                        ORDER BY us ASC
                    '''.format(b.id)
                )

                for row in res:
                    ms = (row[0]/1000)-b.creation_timestamp_ms
                    ts = round((ms/1000) / step)

                    for x in range(ts, max_step+1):
                        receptions_steps[x] += 1

                run_reception_steps.append(receptions_steps)
            return run_reception_steps

        run_reception_steps = cached(name, proc)
        per_density_reception_steps[density] += run_reception_steps

    positions = range(0, max_step + 1)
    plt.clf()

    fig, ax = plt.subplots()
    fig.set_size_inches(3.0, 3.0)

    mean = {}
    cis = {}


    for k in per_density_reception_steps:
        if len(per_density_reception_steps[k]) > 0:
            per_density_reception_steps[k] = np.array(per_density_reception_steps[k], dtype=np.float64)
            per_density_reception_steps[k] = np.swapaxes(per_density_reception_steps[k], 0, 1)  # we swap the axes to get all t=0 values at the first position together
            per_density_reception_steps[k] = per_density_reception_steps[k]*100
            mean[k] = np.mean(per_density_reception_steps[k], axis=1)
            cis[k] = np.percentile(per_density_reception_steps[k], [2.5, 97.5], axis=1)

    if 'sparse' in mean:
        plt.plot(positions, mean['sparse'], linestyle='-', label="Sparse", alpha=0.75, color='C1')
        plt.fill_between(positions, cis['sparse'][0], cis['sparse'][1], color='C1', label='95% CI Sparse', alpha=0.25, linewidth=0.0)

    if 'populated' in mean:
        plt.plot(positions, mean['populated'], linestyle='-', label="Populated", alpha=0.75, color='C2')
        plt.fill_between(positions, cis['populated'][0], cis['populated'][1], color='C2', label='95% CI Populated', alpha=0.25, linewidth=0.0)

    if 'dense' in mean:
        plt.plot(positions, mean['dense'], linestyle='-', label="Dense", alpha=0.75, color='C4')
        plt.fill_between(positions, cis['dense'][0], cis['dense'][1], color='C4', label='95% CI Dense', alpha=0.25, linewidth=0.0)

    if 'very_dense' in mean:
        plt.plot(positions, mean['very_dense'], linestyle='-', label="Very Dense", alpha=0.75, color='C5')
        plt.fill_between(positions, cis['very_dense'][0], cis['very_dense'][1], color='C5', label='95% CI Very Dense', alpha=0.25, linewidth=0.0)

    plt.legend()
    plt.xlabel("Time [s]")
    plt.ylabel('Bundle Reception Rate [%]')
    plt.axis([0, 300, None, None])
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(base_path + "spray_and_wait_propagation" + ".pdf", format="pdf")
    plt.close()


def export_ict(db, base_path):
    runs = db((db.run.status == 'processed') & ((db.run.group == 'broadcast') | (db.run.group == 'unicast'))).select()
    max_dist = 50

    per_density = {
        'sparse': [],
        'populated': [],
        'dense': [],
        'very_dense': []
    }

    max_s = 360

    for r in runs:
        name = slugify(("ict", str(max_dist), str(r.name), str(r.id)))

        run_config = json.loads(r.configuration_json)

        print("Handling {}".format(name))

        density = get_density(r)

        def proc():
            # build ict map
            contact_pairs = extract_contact_pairs(dist_time_iters_from_run(run_config), r.simulation_time, max_dist)
            s = []
            for (a,b) in contact_pairs:
                for (start, end) in contact_pairs[(a,b)]:
                    s.append(((end-start)/1000000))
            return s
        xs = cached(name, proc)
        per_density[density] += xs

    xs = {}
    for k in per_density:
        pa = []
        if len(per_density[k]) > 0:
            for t in range(0, max_s, 1):
                p = len([x for x in per_density[k] if x > t]) / len(per_density[k])
                pa.append(p)
            xs[k] = pa

    positions = [t/60.0 for t in range(0, max_s)]
    plt.clf()

    fig, ax = plt.subplots()
    fig.set_size_inches(3.0, 3.0)

    if 'sparse' in xs:
        plt.plot(positions, xs['sparse'], linestyle='-', label="Sparse", color='C1')
    if 'populated' in xs:
        plt.plot(positions, xs['populated'], linestyle='--', label="Populated", color='C2')
    if 'dense' in xs:
        plt.plot(positions, xs['dense'], linestyle=':', label="Dense", color='C3')
    if 'very_dense' in xs:
        plt.plot(positions, xs['very_dense'], linestyle=':', label="Very Dense", color='C4')

    plt.legend()
    plt.xlabel("Time [minute]")
    plt.ylabel('P(X>x)')
    plt.axis([None, None, None, None])
    plt.tight_layout()
    plt.savefig(base_path + "export_ict" + ".pdf", format="pdf")
    plt.close()


def export_connection_times(db, base_path):
    runs = db((db.run.status == 'processed') & (db.run.group == RUN_GROUP)).select()


    overall_times = []
    for r in runs:
        name = slugify(("connection_times", str(r.name), str(r.id)))
        run_config = json.loads(r.configuration_json)

        conn_infos = db((db.conn_info.run == r)).iterselect()
        setup_times = []
        for conn_info in conn_infos:
            if None in [conn_info.client_conn_init_us, conn_info.client_channel_up_us, conn_info.peripheral_channel_up_us]:
                continue

            setup_time = (max(conn_info.client_channel_up_us, conn_info.peripheral_channel_up_us) - conn_info.client_conn_init_us)/1000000
            setup_times.append(setup_time)

        overall_times += setup_times

        setup_times = np.array(setup_times)

        mean = np.mean(setup_times)
        (lq, uq) = np.percentile(setup_times, [2.5, 97.5])

        print(name)
        print("Mean: {}, LQ: {}, UQ: {}".format(mean, lq, uq))

    overall_times = np.array(overall_times)
    mean = np.mean(overall_times)
    (lq, uq) = np.percentile(overall_times, [2.5, 97.5])
    print("export_connection_times overall")
    print("Mean: {}, LQ: {}, UQ: {}".format(mean, lq, uq))

def get_density(run):
    run_config = json.loads(run.configuration_json)
    model_options = json.loads(run_config['SIM_MODEL_OPTIONS'])
    density = model_options['density']

    if density <= 10.0:
        return 'sparse'
    elif density <= 100.0:
        return 'populated'
    elif density <= 1000.0:
        return 'dense'
    elif density <= 10000.0:
        return 'very_dense'
    
    assert False, "density {} not known".format(density)


def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return text


if __name__ == "__main__":
    config = load_env_config()

    load_plot_defaults()

    logdir = config['SIM_LOG_DIR']
    export_dir = config['SIM_EXPORT_DIR']
    export_cache_dir = config['SIM_EXPORT_CACHE_DIR']
    os.makedirs(logdir, exist_ok=True)

    assert 'SIM_EXPORT_DIR' in config and config['SIM_EXPORT_DIR']

    if 'SIM_EXPORT_CACHE_DIR' in config and config['SIM_EXPORT_CACHE_DIR']:
        init_cache(config['SIM_EXPORT_CACHE_DIR'])


    db = DAL(config['SIM_DB_URI'], folder=logdir)

    tables.init_tables(db)
    tables.init_eval_tables(db)

    db.commit() # we need to commit

    exports = [
        export_testbed_calibration_bundle_transmission_time,
        export_testbed_calibration_bundle_rssi_bars,
        export_testbed_calibration_bundle_transmission_success,
        export_testbed_calibration_setup_times_at_distances,
        #export_testbed_calibration_bundle_rssi_per_distance,
        #export_fake_bundle_propagation_direct,
        #export_bundle_propagation_epidemic,
        #export_ict,
        #export_app_connection_distance_histogramm,
        #export_testbed_rssi_per_distance,
        #export_pre_calibration_connection_times,
        #export_testbed_connection_times,
        #export_mean_path_loss,
        #export_connection_times,
        #export_stored_bundles,
        #export_bundle_transmission_time_per_distance,
        #export_bundle_transmission_time_per_neighbors,
        #export_rssi_per_distance,
        #export_advertisement_reception_rate,
        #export_fake_bundle_propagation_epidemic,
        #export_fake_bundle_propagation_direct,
        #export_ict,
    ]

    for step in exports:
        name = remove_prefix(step.__name__, METHOD_PREFIX)
        print("Handling {}".format(name))
        export_dir = config['SIM_EXPORT_DIR'] + '/tmp/' #os.path.join(config['SIM_EXPORT_DIR'], name) + '/'
        os.makedirs(export_dir, exist_ok=True)
        step(db, export_dir)