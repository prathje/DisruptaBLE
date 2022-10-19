FROM --platform=linux/amd64 prathje/babble-sim-docker:latest@sha256:961261f4c8bd2e894eb786089affb23e596fd03ed78e2d8b097d42ce74a4aca4

# TODO we should rebuild the babble-sim container
# install some dependencies
RUN sudo apt update && sudo apt-get install -y gdb valgrind libc6-dbg:i386

# Upgrade to newer cmake:
RUN sudo apt update && sudo apt-get remove cmake && sudo -H pip3 install cmake
RUN pip3 install python-dotenv pydal progressbar2 matplotlib pymysql scipy seaborn
RUN cd /bsim && git clone https://github.com/prathje/ext_2G4_channel_positional.git ./components/ext_2G4_channel_positional && make all

# Increase limits:
#RUN ulimit -n 1000000 && ulimit -s  256 && ulimit -i  120000 && echo 120000 > /proc/sys/kernel/threads-max && echo 600000 > /proc/sys/vm/max_map_count && echo 200000 > /proc/sys/kernel/pid_max

# IMPORTANT: Add manual background noise in components/ext_2G4_modem_BLE_simple/src/modem_BLE_simple.c:
RUN sed -i 's/double TotalInterfmW  = 0;/double TotalInterfmW  = pow(10.0, -96.42\/10.0);/g' /bsim/components/ext_2G4_modem_BLE_simple/src/modem_BLE_simple.c && cd /bsim && make all

#GROUP_NUM_EXECUTIONS=5 GROUP_PARALLEL_RUNS=5 python3 run_group.py "" envs/experiments/kth_walkers_broadcast/ &