# Stop current bsims
${BSIM_COMPONENTS_PATH}/common/stop_bsim.sh || 1


## Clear old executables
#rm /app/p2p/build_source/zephyr/zephyr.exe
#rm /app/p2p/build_proxy/zephyr/zephyr.exe
#
## and their copies
#rm ${BSIM_OUT_PATH}/bin/bs_nrf52_bsim_p2p_source
#rm ${BSIM_OUT_PATH}/bin/bs_nrf52_bsim_p2p_proxy
#
## Compile source
#west build -b nrf52_bsim /app/p2p --build-dir /app/p2p/build_source -- -DOVERLAY_CONFIG=source.conf
#cp /app/p2p/build_source/zephyr/zephyr.exe ${BSIM_OUT_PATH}/bin/bs_nrf52_bsim_p2p_source
#
## Compile proxy
#west build -b nrf52_bsim /app/p2p --build-dir /app/p2p/build_proxy -- -DOVERLAY_CONFIG=proxy.conf
#cp /app/p2p/build_proxy/zephyr/zephyr.exe ${BSIM_OUT_PATH}/bin/bs_nrf52_bsim_p2p_proxy



cd ${BSIM_OUT_PATH}/bin


SIM_NUM_DEVICES=$1
SIM_NUM_PROXY_DEVICES=$(($SIM_NUM_DEVICES-1))

DIST_FILE_PATH=$2

# See https://babblesim.github.io/2G4_select_ch_mo.html
# -dist=/app/distances.matrix

# We run the simulation in the end so we can easily cancel it :)

./bs_nrf52_bsim_p2p_source -s=p2p_sim -d=0 &

for (( i=1; i <= $SIM_NUM_PROXY_DEVICES; ++i ))
do
    ./bs_nrf52_bsim_p2p_proxy -s=p2p_sim -d=$i &
done


WIFI_INTERFERENCE_ATT=100
WIFI_INTERFERENCE_UTILISATION=100


#./bs_device_time_monitor -s=p2p_sim -d=$(($SIM_NUM_DEVICES)) -interval=1e6 & # TODO! FIX ME!
#./bs_device_2G4_WLAN_actmod -s=p2p_sim -d=$(($SIM_NUM_DEVICES+1)) -ConfigSet=$(($WIFI_INTERFERENCE_UTILISATION)) -channel=2 &
#./bs_device_2G4_WLAN_actmod -s=p2p_sim -d=$(($SIM_NUM_DEVICES+2)) -ConfigSet=$(($WIFI_INTERFERENCE_UTILISATION)) -channel=4 &
#./bs_device_2G4_WLAN_actmod -s=p2p_sim -d=$(($SIM_NUM_DEVICES+3)) -ConfigSet=$(($WIFI_INTERFERENCE_UTILISATION)) -channel=6 &
#./bs_device_2G4_WLAN_actmod -s=p2p_sim -d=$(($SIM_NUM_DEVICES+4)) -ConfigSet=$(($WIFI_INTERFERENCE_UTILISATION)) -channel=8 &
#./bs_device_2G4_WLAN_actmod -s=p2p_sim -d=$(($SIM_NUM_DEVICES+5)) -ConfigSet=$(($WIFI_INTERFERENCE_UTILISATION)) -channel=10 &
#./bs_device_2G4_WLAN_actmod -s=p2p_sim -d=$(($SIM_NUM_DEVICES+6)) -ConfigSet=$(($WIFI_INTERFERENCE_UTILISATION)) -channel=12 &


# 806400000e0
#
./bs_2G4_phy_v1 -s=p2p_sim -D=$(($SIM_NUM_DEVICES+0))  -sim_length=3600e6 -defmodem=BLE_simple -channel=Indoorv1 -argschannel -preset=Huge3 -speed=1.1 -at=$(($WIFI_INTERFERENCE_ATT)) -dist=$DIST_FILE_PATH