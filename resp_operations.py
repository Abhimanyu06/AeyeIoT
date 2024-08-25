#!/usr/bin/env python3
import time
import RPi.GPIO as GPIO
from delete_wifi import *

BUTTON_GPIO = 16

if __name__ == '__main__':
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    pressed = False

    while True:
        # button is pressed when pin is LOW
        if not GPIO.input(BUTTON_GPIO):
            if not pressed:
                print("Button pressed!")
                pressed = True
                disconnect_and_forget()
        # button not pressed (or released)
        else:
            pressed = False