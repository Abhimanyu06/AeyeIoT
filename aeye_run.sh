#!/bin/bash
sleep 15
/home/rp/Aeye_iot/wifi-connect-headless-rpi/scripts/../scripts/run.sh
nohup python3 /home/rp/Aeye_iot/resp_operations.py > /home/rp/Aeye_iot/logs/resp_operations.log &
nohup python3 /home/rp/Aeye_iot/cv.py > /home/rp/Aeye_iot/logs/cv.log &