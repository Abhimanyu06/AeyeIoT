#!/bin/bash
sleep 15
mkdir /home/rp/AeyeIoT/logs/
nohup python3 /home/rp/AeyeIoT/git_repo_version.py > /home/rp/AeyeIoT/logs/git_repo.log &
chmod 777 /home/rp/AeyeIoT/* &
chmod 777 /home/rp/AeyeIoT/logs/* &
/home/rp/AeyeIoT/wifi-connect-headless-rpi/scripts/run.sh &
nohup python3 /home/rp/AeyeIoT/resp_operations.py > /home/rp/AeyeIoT/logs/resp_operations.log &
nohup python3 /home/rp/AeyeIoT/cv.py > /home/rp/AeyeIoT/logs/cv.log &