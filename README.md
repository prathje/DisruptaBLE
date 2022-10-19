DisruptaBLE: Opportunistic BLE Networking
========================================

This repository contains the source code for the paper "DisruptaBLE: Opportunistic BLE Networking". DisruptaBLE is based on [µD3TN](https://d3tn.com/ud3tn.html) and adds [Zephyr RTOS](https://zephyrproject.org/) with BLE support as well as a BLE simulation environment using [BabbleSim](https://babblesim.github.io/).
Disclaimer: DisruptaBLE was partially derived from µD3TN. See `./LICENSE.txt` and `./LICENSE-3RD-PARTY.txt` for legal information.
With Zephyr RTOS support, DisruptaBLE supports (in theory) numerous boards: [List of Supported Boards in Zephyr](https://docs.zephyrproject.org/boards/index.html)

To cite this, please cite the publication:

```
@INPROCEEDINGS{9843509,  author={Rathje, Patrick and Landsiedel, Olaf},  booktitle={2022 IEEE 47th Conference on Local Computer Networks (LCN)},   title={DisruptaBLE: Opportunistic BLE Networking},   year={2022},  volume={},  number={},  pages={165-172},  doi={10.1109/LCN53696.2022.9843509}}
```


Quick Start
-----------

For a quick start, simply run the provided docker image and mount your current directory in it.
We provide a preliminary Docker Image to build and run DisruptaBLE under Zephyr RTOS. Currently, only the nRF52 platform is tested.
This also includes the BLE simulation of multiple devices using [BabbleSim](https://babblesim.github.io/).
First, start the corresponding container and mount the current working direction (the git project root) to /app:

```
docker run --rm -it -v ${PWD}:/app prathje/disruptable:latest@sha256:ba202790c45f44792a9aed3de31ce898b184ba34c505f3ff7af3510260afebc2 /bin/bash
```

You can then execute the example with 25 devices in a random walk environment as follows:
```
git submodule init && git submodule update
cd sim
python3 run.py envs/test.env
```

This example spawns 24 proxy nodes and a single central node. Simulation settings are merged using the config file in `sim/.env` as well as the ones specified in `envs/test.env`. 
The events are written into a logfile in `logs/sqlite.db`

Further Steps
-----------

Running large simulations requires additional parameters (at least for the execution via docker):
```
--net=host --cap-add=SYS_PTRACE --security-opt seccomp=unconfined --ulimit nofile=1000000:1000000 --pids-limit -1
```

Script to run the experiments as in the paper the KTH walkers dataset is required, please write pra@informatik.uni-kiel.de to get access.
With the files in place, the experiments can get executed via:
```
GROUP_NUM_EXECUTIONS=5 GROUP_PARALLEL_RUNS=5 python3 run_group.py "" envs/experiments/kth_walkers_broadcast/ &
GROUP_NUM_EXECUTIONS=5 GROUP_PARALLEL_RUNS=5 python3 run_group.py "" envs/experiments/kth_walkers_unicast/ &
wait
echo "All done"
```


To build inside but flash outside the container:
```bash
west build -b nrf52840dk_nrf52840 /app/zephyr/ --pristine auto --build-dir /app/build/zephyr/build_source -- -DOVERLAY_CONFIG=source.conf
west build -b nrf52840dk_nrf52840 /app/zephyr/ --pristine auto --build-dir /app/build/zephyr/build_proxy -- -DOVERLAY_CONFIG=proxy.conf
```

To flash it:
```bash
nrfjprog -f nrf52 --program build/zephyr/build_source/zephyr/zephyr.hex --sectorerase --reset
nrfjprog -f nrf52 --program build/zephyr/build_proxy/zephyr/zephyr.hex --sectorerase --reset
```


Build, flash and debug proxy using west directly:
```bash
west build -b nrf52840dk_nrf52840 zephyr/ --pristine auto --build-dir build_proxy -- -DOVERLAY_CONFIG=proxy.conf
west flash --build-dir build_proxy
west debug --build-dir build_proxy
```

Running and analyzing simulations:
```
python3 eval.py
```

Getting Started with the Implementation
---------------------------------------

The core part of µD3TN is located in `./components/ud3tn/`.
The starting point of the program can be found in
`./components/daemon/main.c`, calling init located in
`./components/ud3tn/init.c`.
This file is the best place to familiarize with the implementation.
`./components/cla/zephyr` contains the BLE specific adapters and neighbor detection.
`./components/platform/zephyr` contains platform specific code for Zephyr adapters.
`./components/routing/epidemic` contains code for broadcast and spray-and-wait routing.
License
-------

The code in `./components`, `./include`, `./pyd3tn`, `./python-ud3tn-utils`,
`./test`, and `./tools` has been developed specifically for µD3TN and is
released under a BSD 3-clause license. The license can be found in
`./LICENSE.txt`, `./pyd3tn/LICENSE`, and `./python-ud3tn-utils/LICENSE`.

External code
-------------

As an early starting point for the STM32F4 project structure,
we have used the project https://github.com/elliottt/stm32f4/
as a general basis.

All further code taken from third parties is documented in
`./LICENSE-3RD-PARTY.txt`, as well as in the source files, along with the
respective original URLs and associated licenses. Generally, third-party code
is found in `./external` and uses Git submodules referencing the original
repositories where applicable.
