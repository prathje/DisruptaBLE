import json
import os
import sys

from pprint import pprint

from pydal import DAL, Field
import tables
import numpy as np
import math

from dist_eval import extract_contact_pairs, dist_time_iters_from_run

import matplotlib.pyplot as plt
from export_utility import load_env_config

from scipy.optimize import curve_fit
import matplotlib.ticker as ticker
from matplotlib.ticker import PercentFormatter
from matplotlib.ticker import (MultipleLocator, AutoMinorLocator)
import matplotlib as mpl
from dist_writer import density_to_side_length
from matplotlib.widgets import Slider, Button

if __name__ == "__main__":
    config = load_env_config()

    logdir = config['SIM_LOG_DIR']
    os.makedirs(logdir, exist_ok=True)

    db = DAL(config['SIM_DB_URI'], folder=logdir)

    tables.init_tables(db)
    tables.init_eval_tables(db)

    db.commit()  # we need to commit

    run_id = int(sys.argv[1])
    assert run_id > 0

    run = db.run[run_id]
    assert run
    run_config = json.loads(run.configuration_json)
    model_options = json.loads(run_config['SIM_MODEL_OPTIONS'])

    fig, ax = plt.subplots()

    side_length = density_to_side_length(model_options['density'], run.num_proxy_devices)
    plt.axis([0, side_length, 0, side_length])

    plt.subplots_adjust(left=0.25, bottom=0.3)

    # this is the central node
    plt.scatter([side_length*0.5], [side_length*0.5], alpha=1.0)

    node_circles = []
    for i in range(run.num_proxy_devices):
        circle = plt.Circle((0.0, 0.0), 0.5, color = 'black', fill = True, linestyle='--', linewidth=2.0)
        node_circles.append(ax.add_artist(circle))

#    conn_lines = []
#    for i in range(run.num_proxy_devices):
#        conn_lines.append(
#            plt.scatter(0, 0)
#        )


    devices = []
    for i in range(run.num_proxy_devices):
        devices.append(db((db.device.run == run) & (db.device.number == (i+1))).select()[0])


    broadcast_bundle = db((db.bundle.run == run) & (db.bundle.destination_eid == 'dtn://fake')).select()[0]


    axamp = plt.axes([0.25, 0.1, 0.65, 0.03])
    time_slider = Slider(
        ax=axamp,
        label="Time [s]",
        valmin=0,
        valmax=int(run.simulation_time / 1000000),
        valinit=0,
        valstep=1,
        orientation="horizontal"
    )

    time_slider.val = 0.0
    def render_time():
        us = time_slider.val*1000000
        for i in range(run.num_proxy_devices):
            pos = db((db.position.device == devices[i]) & (db.position.us == us)).select()[0]
            received = db(((db.stored_bundle.device == devices[i]) & (db.stored_bundle.created_us <= us)) & (db.stored_bundle.bundle == broadcast_bundle)).count() > 0
            node_circles[i].set(center=(pos.pos_x, pos.pos_y), color= ('red' if received else 'black'))

        fig.canvas.draw_idle()


    def next(event):
        time_slider.val = min(run.simulation_time / 1000000, time_slider.val+1.0)
        render_time()

    def prev(event):
        time_slider.val = max(0.0, time_slider.val-1.0)
        render_time()

    axprev = plt.axes([0.7, 0.05, 0.1, 0.075])
    axnext = plt.axes([0.81, 0.05, 0.1, 0.075])
    bnext = Button(axnext, 'Next')
    bnext.on_clicked(next)
    bprev = Button(axprev, 'Previous')
    bprev.on_clicked(prev)


    def slider_update(val=0.0):
        # change position and current
        render_time()



    time_slider.on_changed(slider_update)
    render_time()
    plt.show()