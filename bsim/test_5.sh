# Stop current bsims
${BSIM_COMPONENTS_PATH}/common/stop_bsim.sh || 1


# Clear old executables
rm /app/build/zephyr/build_source/zephyr/zephyr.exe
rm /app/build/zephyr/build_proxy/zephyr/zephyr.exe

# and their copies
rm ${BSIM_OUT_PATH}/bin/bs_nrf52_bsim_dtn_source
rm ${BSIM_OUT_PATH}/bin/bs_nrf52_bsim_dtn_proxy

# Compile source
west build -b nrf52_bsim /app/platforms/zephyr/ --pristine auto --build-dir /app/build/zephyr/build_source -- -DOVERLAY_CONFIG=/app/platforms/zephyr/source.conf
cp /app/build/zephyr/build_source/zephyr/zephyr.exe ${BSIM_OUT_PATH}/bin/bs_nrf52_bsim_dtn_source

# Compile proxy
west build -b nrf52_bsim /app/platforms/zephyr/ --pristine auto --build-dir /app/build/zephyr/build_proxy -- -DOVERLAY_CONFIG=/app/platforms/zephyr/proxy.conf
cp /app/build/zephyr/build_proxy/zephyr/zephyr.exe ${BSIM_OUT_PATH}/bin/bs_nrf52_bsim_dtn_proxy


cd ${BSIM_OUT_PATH}/bin


# See https://babblesim.github.io/2G4_select_ch_mo.html
# -dist=/app/distances.matrix

# We run the simulation in the end so we can easily cancel it :)

./bs_nrf52_bsim_dtn_source -s=dtn_sim -d=0 &
./bs_nrf52_bsim_dtn_proxy -s=dtn_sim -d=1 &
./bs_nrf52_bsim_dtn_proxy -s=dtn_sim -d=2 &
./bs_nrf52_bsim_dtn_proxy -s=dtn_sim -d=3 &
./bs_nrf52_bsim_dtn_proxy -s=dtn_sim -d=4 &

./bs_2G4_phy_v1 -s=dtn_sim -D=5 -sim_length=10806400000e0 -defmodem=BLE_simple -channel=Indoorv1 -argschannel -preset=Huge3 -speed=1.1 -at=50