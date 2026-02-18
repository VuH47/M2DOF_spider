"""
Servo Calibration - quick test script
"""

from machine import Pin, PWM
import time

# servo pins: [15, 4, 16, 17, 5, 18, 19, 21]
SERVO_PIN = 4

# setup PWM
pwm = PWM(Pin(SERVO_PIN), freq=50)


# convert angle to PWM duty cycle
def set_angle(angle):
    # clamp to 0-180
    if angle < 0:
        angle = 0
    elif angle > 180:
        angle = 180

    # pulse width 0.5ms to 2.5ms maps to duty 25 to 125
    duty = int((angle / 180) * (125 - 25) + 25)
    pwm.duty(duty)


if __name__ == '__main__':

    # test: go to 0, 180, then 90
    set_angle(0)
    time.sleep(1)

    set_angle(180)
    time.sleep(1)

    set_angle(90)
    time.sleep(1)
