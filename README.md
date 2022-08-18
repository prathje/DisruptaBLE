DisruptaBLE: Opportunistic BLE Networking
========================================

This repository contains the source code for the paper "DisruptaBLE: Opportunistic BLE Networking". DisruptaBLE is based on [µD3TN](https://d3tn.com/ud3tn.html) and adds [Zephyr RTOS](https://zephyrproject.org/) with BLE support as well as a BLE simulation environment using [BabbleSim](https://babblesim.github.io/).
Disclaimer: DisruptaBLE was partially derived from µD3TN. See `./LICENSE.txt` and `./LICENSE-3RD-PARTY.txt` for legal information.

Platforms
---------
With Zephyr RTOS support, DisruptaBLE supports numerous boards: [List of Supported Boards in Zephyr](https://docs.zephyrproject.org/boards/index.html)


Quick Start
-----------

Both platforms can be built, deployed, tested and used in parallel.
To get started with one or both platforms, just follow the subsequent
instructions.

This project uses git submodules to manage some code dependencies. Use the
`--recursive` option if you `git clone` the project or run
`git submodule init && git submodule update` at a later point in order to
satisfy them.

### Build and run with Zephyr RTOS

We provide a preliminary Docker Image to build and run µD3TN under Zephyr RTOS. Currently, only the nRF52 platform is tested. This also includes the BLE simulation of multiple devices using [BabbleSim](https://babblesim.github.io/).

First, start the corresponding container and mount the current working direction (the ud3tn project root) to /app:

```
docker run --rm -it -v ${PWD}/ud3tn-ble:/app -v ${PWD}/zephyr:/zephyr/zephyr prathje/babble-sim-docker:latest /bin/bash
   cd $ZEPHYR_BASE && west update && sudo apt-get install -y gdb valgrind libc6-dbg:i386
```

```
docker run --rm -it -v ${PWD}/ud3tn-ble:/app -v ${PWD}/zephyr:/zephyr/zephyr --net=host --cap-add=SYS_PTRACE --security-opt seccomp=unconfined --ulimit nofile=1000000:1000000 --pids-limit -1 prathje/babble-sim-docker:latest /bin/bash
```


Init everything:

```
cd $ZEPHYR_BASE && west update && sudo apt-get install -y gdb valgrind libc6-dbg:i386 mysql-client && cd /bsim && git clone https://github.com/prathje/ext_2G4_channel_positional.git ./components/ext_2G4_channel_positional && make all && sudo apt-get remove cmake && sudo -H pip3 install cmake && pip3 install python-dotenv pydal progressbar2 matplotlib pymysql scipy seaborn
```


Install new 2G4 positional channel:
```
cd /bsim
git clone https://github.com/prathje/ext_2G4_channel_positional.git ./components/ext_2G4_channel_positional
make all
```


Upgrade to newer cmake:
```
sudo apt-get remove cmake && sudo -H pip3 install cmake
```

Increase limits:
```
ulimit -n 1000000 && ulimit -s  256 && ulimit -i  120000 && echo 120000 > /proc/sys/kernel/threads-max && echo 600000 > /proc/sys/vm/max_map_count && echo 200000 > /proc/sys/kernel/pid_max 
```

Important: Add manual background noise in components/ext_2G4_modem_BLE_simple/src/modem_BLE_simple.c:
```
cd /bsim
nano components/ext_2G4_modem_BLE_simple/src/modem_BLE_simple.c
double TotalInterfmW  = pow(10.0, -96.42/10.0);
make all
```


Script to run the experiments as in the paper:
```
GROUP_NUM_EXECUTIONS=5 GROUP_PARALLEL_RUNS=5 python3 run_group.py "" envs/experiments/kth_walkers_broadcast/ &
GROUP_NUM_EXECUTIONS=5 GROUP_PARALLEL_RUNS=5 python3 run_group.py "" envs/experiments/kth_walkers_unicast/ &
wait
echo "All done"
```

when Ninja ends in a segmentation fault, restart the container...


```
west build -b nrf52840dk_nrf52840 --pristine auto  /app/zephyr/
west build -b native_posix --pristine auto  /app/zephyr/
west build -b nrf52_bsim --pristine auto  /app/zephyr/
/app/bsim/test.sh 1
/app/bsim/test_gdb.sh 1
./build/zephyr/zephyr.exe
```

Or execute the bsim test simulation:
```
/app/bsim/test.sh
```

To run with gdb support:
```
/app/bsim/test_gdb.sh
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
pip3 install python-dotenv pydal progressbar2 matplotlib pymysql scipy seaborn
cd /app/sim/
python3 run.py
python3 eval.py
```

Getting Started with the Implementation
---------------------------------------

The core part of µD3TN is located in `./components/ud3tn/`.
The starting point of the program can be found in
`./components/daemon/main.c`, calling init located in
`./components/ud3tn/init.c`.
This file is the best place to familiarize with the implementation.

Configurability
---------------

The following values can be configured at runtime via bundles to the "/config"
endpoint (see `doc/contacts_data_format.md`):
- reachable nodes (EID and CLA address)
- contacts (interval and data rate)
- reachable EIDs for each node and contact
- reliability and trustworthiness of the nodes

The following values can be configured at runtime via bundles to the
"/management" endpoint:
- system time

Via command line parameters (see `-h` or `--help` for details):
- own EID
- used CLAs and their parameters (e.g. IP and port of TCP socket)
- BP version for bundles injected by applications (6: RFC5050, 7: BPbis)
- Application Agent: IP and port
- maximum bundle size
- lifetime of bundles injected by applications
- activation of status reports

Via `config.h` at compile time:
- default values for command line parameters
- available storage space for bundles
- limits of the custody transfer feature
- settings of TCP connections created by various CLAs (e.g. timeouts, retry intervals)
- tuning of the routing algorithm regarding reliability and trustworthiness of nodes
- thread priorities, queue lengths, further performance settings (e.g. size of hash tables)

For configuring contacts at runtime, the `aap_config.py` script in `tools/aap`
may be used.

Testing
-------

Details about tools for testing and the overall testing approaches can be found
in `./doc/testing.md`.

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