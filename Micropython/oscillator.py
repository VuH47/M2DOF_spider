# Servo oscillator driver for MicroPython
# based on OttoDIY project (2020)
# makes servos move in sine wave patterns

import math
import time
import machine


class Servo:
    def __init__(self, freq=50, max_ang=180):
        self.freq = freq
        self.max_ang = max_ang
        self.pin = None
        self.pwm = None
        self._attached = False

    def attach(self, pin):
        self.pin = machine.Pin(pin)
        self.pwm = machine.PWM(self.pin, freq=self.freq)
        self._attached = True

    def detach(self):
        self.pwm.deinit()
        self._attached = False

    def attached(self):
        return self._attached

    # move servo to angle (0-180 degrees)
    def write(self, degrees):
        degrees = degrees % 360
        if degrees < 0:
            degrees += 360
        if degrees > 180:
            degrees = 180
        duty = int(degrees * 102 / 180 + 26)
        self.pwm.duty(duty)

    def __deinit__(self):
        self.pwm.deinit()


class Oscillator:
    def __init__(self, trim=0):
        # oscillator params
        self._A = 0       # amplitude (degrees)
        self._O = 0       # offset (degrees)
        self._T = 0       # period (ms)
        self._phase0 = 0.0  # phase (radians)

        # internal stuff
        self._servo = Servo()
        self._pos = 0
        self._trim = trim    # calibration offset
        self._phase = 0.0
        self._inc = 0.0
        self._N = 0.0        # num samples
        self._TS = 0         # sampling period ms
        self._previousMillis = 0
        self._currentMillis = 0
        self._stop = True     # if true servo is stopped
        self._rev = False     # reverse mode

    def attach(self, pin, rev=False):
        if not self._servo.attached():
            self._servo.attach(pin)
            self._servo.write(90 + self._trim)

            # default timing
            self._TS = 30
            self._T = 2000
            self._N = self._T / self._TS
            self._inc = 2 * math.pi / self._N
            self._previousMillis = 0

            # default wave params
            self._A = 45
            self._phase = 0
            self._phase0 = 0
            self._O = 0
            self._stop = False
            self._rev = rev

    def detach(self):
        if self._servo.attached():
            self._servo.detach()

    def SetA(self, A):
        self._A = A

    def SetO(self, O):
        self._O = O

    def SetPh(self, Ph):
        self._phase0 = Ph

    def SetT(self, T):
        self._T = T
        self._N = self._T / self._TS
        self._inc = 2 * math.pi / self._N

    def SetPosition(self, position):
        self._servo.write(position + self._trim)

    def SetTrim(self, trim):
        self._trim = trim

    def getTrim(self):
        return self._trim

    def Stop(self):
        self._stop = True

    def Play(self):
        self._stop = False

    def Reset(self):
        self._phase = 0

    # check if its time for the next sample
    def __next_sample(self):
        self._currentMillis = time.ticks_ms()
        if self._currentMillis - self._previousMillis > self._TS:
            self._previousMillis = self._currentMillis;
            return True
        return False

    # call this in a loop to keep the oscillation going
    def refresh(self):
        if self.__next_sample():
            if not self._stop:
                self._pos = round(self._A * math.sin(
                    self._phase + self._phase0) + self._O)
                if self._rev:
                    self._pos = -self._pos
                self._servo.write(self._pos + 90 + self._trim)

            # always increment phase even when stopped
            # so coordination between servos stays in sync
            self._phase = self._phase + self._inc


if __name__ == '__main__':
    # quick test
    os = Oscillator()
    os.attach(pin=15)

    # sine wave formula: y = A*sin(2*pi*x/T + Ph) + O
    os.SetA(A=20)       # amplitude in degrees
    os.SetO(O=10)       # offset 
    os.SetT(T=1000)     # period in ms
    os.SetPh(Ph=0)      # phase

    while True:
        os.Stop()
