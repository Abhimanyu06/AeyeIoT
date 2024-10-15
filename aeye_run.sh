#!/bin/bash
sleep 15
/home/rp/AeyeIoT/wifi-connect-headless-rpi/scripts/../scripts/run.sh
nohup python3 /home/rp/AeyeIoT/resp_operations.py > /home/rp/AeyeIoT/logs/resp_operations.log &
nohup python3 /home/rp/AeyeIoT/cv.py > /home/rp/AeyeIoT/logs/cv.log &