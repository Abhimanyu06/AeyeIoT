#!/usr/bin/env python3
import time
import RPi.GPIO as GPIO
from dotenv import load_dotenv
import os
from delete_wifi import *
from datetime import datetime
import json
import logging
from logging.handlers import TimedRotatingFileHandler

load_dotenv()
LOG_PATH = os.getenv('LOG_PATH', "logs/")

log_handler = TimedRotatingFileHandler(LOG_PATH+'AeyeIoT.log', when='H', interval=1, backupCount=5)
logging.basicConfig(
    handlers=[log_handler],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

BUTTON_GPIO = 16

if __name__ == '__main__':
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    pressed = False

    while True:
        # button is pressed when pin is LOW
        if not GPIO.input(BUTTON_GPIO):
            if not pressed:
                logging.log(logging.INFO, json.dumps({'level': logging.INFO, 'message': "Wifi reset Button pressed!",  'timestamp': datetime.now().isoformat()}))
                pressed = True
                disconnect_and_forget()
        # button not pressed (or released)
        else:
            pressed = False