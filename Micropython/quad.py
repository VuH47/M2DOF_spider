# quadruped robot class - based on OttoDIY (2020)
# controls 8 servos for walking, dancing, etc

from micropython import const
import oscillator, utime, math

# direction constants
FORWARD = const(1)
BACKWARD = const(-1)
LEFT = const(1)
RIGHT = const(-1)
SMALL = const(5)
MEDIUM = const(15)
BIG = const(30)

def DEG2RAD(g):
    return (g * math.pi) / 180


class Quad:
    def __init__(self):
        self._servo_totals = 8
        self._servo = []
        for i in range(self._servo_totals):
            self._servo.append(oscillator.Oscillator())
        self._servo_pins = [-1] * self._servo_totals
        self._servo_trim = [0] * self._servo_totals
        self._servo_position = [90] * self._servo_totals
        self._final_time = 0
        self._partial_time = 0
        self._increment = [0] * self._servo_totals
        self._isOttoResting = True
        self._reverse = [False] * 8
        self._ultrasonic = None
        self._obstacle_threshold = 20  # cm

        # balance stuff
        self._balance_controller = None
        self._balance_enabled = False

        # stand pose angles
        # [FLH, FRH, BLL, BRL, BLH, BRH, FLL, FRL]
        self._stand_pose = [140, 40, 155, 25, 40, 140, 25, 140]

        # offsets from 90 for each servo (for oscillation center)
        self._stand_offsets = [angle - 90 for angle in self._stand_pose]

    def deinit(self):
        self.detachServos()

    def init(self, FRH, FLH, FRL, FLL, BRH, BLH, BRL, BLL):
        self._servo_pins[0] = FRH
        self._servo_pins[1] = FLH
        self._servo_pins[2] = FRL
        self._servo_pins[3] = FLL
        self._servo_pins[4] = BRH
        self._servo_pins[5] = BLH
        self._servo_pins[6] = BRL
        self._servo_pins[7] = BLL

        self.attachServos()
        self.setRestState(False)

        for i in range(self._servo_totals):
            self._servo_position[i] = 90

    def attachServos(self):
        for i in range(self._servo_totals):
            self._servo[i].attach(self._servo_pins[i])

    def detachServos(self):
        for i in range(self._servo_totals):
            self._servo[i].detach()

    def setTrims(self, FRH, FLH, FRL, FLL, BRH, BLH, BRL, BLL):
        self._servo[0].SetTrim(0 if FRH is None else FRH)
        self._servo[1].SetTrim(0 if FLH is None else FLH)
        self._servo[2].SetTrim(0 if FRL is None else FRL)
        self._servo[3].SetTrim(0 if FLL is None else FLL)
        self._servo[4].SetTrim(0 if BRH is None else BRH)
        self._servo[5].SetTrim(0 if BLH is None else BLH)
        self._servo[6].SetTrim(0 if BRL is None else BRL)
        self._servo[7].SetTrim(0 if BLL is None else BLL)

    # move all servos to target positions over a time period
    def _moveServos(self, period, servo_target):
        self.attachServos()
        if self.getRestState():
            self.setRestState(False)
        if period > 10:
            for i in range(self._servo_totals):
                self._increment[i] = ((servo_target[i]) - self._servo_position[i]) / (period / 10.0)
            self._final_time = utime.ticks_ms() + period
            iteration = 1
            while utime.ticks_ms() < self._final_time:
                self._partial_time = utime.ticks_ms() + 10

                corrections = self.getBalanceCorrections()

                for i in range(self._servo_totals):
                    target_pos = int(self._servo_position[i] + (iteration * self._increment[i]))
                    target_pos += int(corrections[i])
                    self._servo[i].SetPosition(target_pos)
                while utime.ticks_ms() < self._partial_time:
                    pass
                iteration += 1
        else:
            corrections = self.getBalanceCorrections()
            for i in range(self._servo_totals):
                self._servo[i].SetPosition(int(servo_target[i] + corrections[i]))
        for i in range(self._servo_totals):
            self._servo_position[i] = servo_target[i]

    def _moveSingle(self, position, servo_number):
        if position > 180 or position < 0:
            position = 90
        self.attachServos()
        if self.getRestState():
            self.setRestState(False)
        self._servo[servo_number].SetPosition(position)
        self._servo_position[servo_number] = position

    def oscillateServos(self, amplitude, offset, period, phase, cycle=1.0):
        for i in range(self._servo_totals):
            self._servo[i].SetO(offset[i])
            self._servo[i].SetA(amplitude[i])
            self._servo[i].SetT(period[i])
            self._servo[i].SetPh(phase[i])

        ref = float(utime.ticks_ms())
        x = ref
        while x <= period[0] * cycle + ref:
            for i in range(self._servo_totals):
                self._servo[i].refresh()
            x = float(utime.ticks_ms())

    def _execute(self, amplitude, offset, period, phase, steps=1.0):
        """run oscillating movement - offsets added to stand pose so
        oscillations happen around standing position not 90deg"""
        phase_rad = [DEG2RAD(i) for i in phase]

        # combine movement offsets with stand offsets
        combined_offset = [offset[i] + self._stand_offsets[i] for i in range(self._servo_totals)]

        self.attachServos()
        if self.getRestState():
            self.setRestState(False)

        # do full cycles
        cycles = int(steps)
        if cycles >= 1:
            i = 0
            while i < cycles:
                self.oscillateServos(amplitude, combined_offset, period, phase_rad)
                i += 1
        # do remaining partial cycle
        self.oscillateServos(amplitude, combined_offset, period, phase_rad, float(steps - cycles))

    def getRestState(self):
        return self._isOttoResting

    def setRestState(self, state):
        self._isOttoResting = state

    def setUltrasonic(self, ultrasonic_sensor):
        self._ultrasonic = ultrasonic_sensor

    def setObstacleThreshold(self, threshold_cm):
        self._obstacle_threshold = threshold_cm

    def getDistance(self):
        if self._ultrasonic:
            return self._ultrasonic.get_distance()
        return -1

    def isObstacleAhead(self):
        if self._ultrasonic:
            distance = self._ultrasonic.get_distance()
            return 0 < distance < self._obstacle_threshold
        return False

    # --- balance controller stuff ---

    def setBalanceController(self, balance_controller):
        self._balance_controller = balance_controller

    def enableBalance(self):
        self._balance_enabled = True
        if self._balance_controller:
            self._balance_controller.enable()

    def disableBalance(self):
        self._balance_enabled = False
        if self._balance_controller:
            self._balance_controller.disable()

    def isBalanceEnabled(self):
        return self._balance_enabled and self._balance_controller is not None

    def calibrateBalance(self):
        """calibrate IMU - robot must be still and level!"""
        if self._balance_controller:
            self._balance_controller.calibrate()
        else:
            print("No balance controller set!")

    def getBalanceAngles(self):
        """returns (roll, pitch) in degrees"""
        if self._balance_controller:
            return self._balance_controller.get_angles()
        return (0.0, 0.0)

    def isTilted(self, threshold=15.0):
        if self._balance_controller:
            return self._balance_controller.is_tilted(threshold)
        return False

    def isFallen(self, threshold=45.0):
        if self._balance_controller:
            return self._balance_controller.is_fallen(threshold)
        return False

    def getBalanceCorrections(self):
        """get servo corrections from balance controller"""
        if self._balance_controller and self._balance_enabled:
            return self._balance_controller.update()
        return [0.0] * 8

    def setBalancePID(self, kp=None, ki=None, kd=None):
        if self._balance_controller:
            self._balance_controller.set_pid_gains(kp, ki, kd)

    # --- poses ---

    def home(self):
        """all servos to 90 degrees (mechanical neutral)"""
        self.attachServos()
        homes = [90] * self._servo_totals
        self._moveServos(500, homes)
        self.setRestState(True)

    def stand(self, t=500):
        """move to standing position
        servo order: [FLH, FRH, BLL, BRL, BLH, BRH, FLL, FRL]"""
        self.attachServos()
        self._moveServos(t, self._stand_pose)
        self.setRestState(True)

    def balancedStand(self, duration_ms=5000, update_rate_ms=20):
        """stand with active balance correction using IMU"""
        if not self._balance_controller:
            print("No balance controller! Using regular stand.")
            self.stand()
            return

        self.attachServos()
        if self.getRestState():
            self.setRestState(False)

        self._moveServos(500, self._stand_pose)

        was_enabled = self._balance_enabled
        self.enableBalance()

        print("Balanced stand active...")
        start_time = utime.ticks_ms()

        while utime.ticks_diff(utime.ticks_ms(), start_time) < duration_ms:
            corrections = self._balance_controller.update()

            for i in range(self._servo_totals):
                corrected_pos = int(self._stand_pose[i] + corrections[i])
                self._servo[i].SetPosition(corrected_pos)

            # print angles every ~500ms if tilted
            if utime.ticks_diff(utime.ticks_ms(), start_time) % 500 < update_rate_ms:
                roll, pitch = self.getBalanceAngles()
                if abs(roll) > 2 or abs(pitch) > 2:
                    print(f"  Roll: {roll:+.1f}, Pitch: {pitch:+.1f}")

            utime.sleep_ms(update_rate_ms)

        if not was_enabled:
            self.disableBalance()

        self.setRestState(True)
        print("Balanced stand done.")

    def startup(self, t=500):
        """smooth startup: home -> hips -> knees -> stand
        prevents jerky movements on power-on"""
        self.attachServos()

        # step 1: go to 90 (home)
        print("Startup: home position...")
        homes = [90] * self._servo_totals
        self._moveServos(t, homes)
        utime.sleep_ms(200)

        # step 2: move hips to stand (knees stay at 90)
        print("Startup: hips...")
        hips_ready = [
            self._stand_pose[0],  # FLH
            self._stand_pose[1],  # FRH
            90,                    # BLL knee
            90,                    # BRL knee
            self._stand_pose[4],  # BLH
            self._stand_pose[5],  # BRH
            90,                    # FLL knee
            90                     # FRL knee
        ]
        self._moveServos(t, hips_ready)
        utime.sleep_ms(200)

        # step 3: move knees to stand (robot rises up)
        print("Startup: knees...")
        self._moveServos(t, self._stand_pose)

        print("Startup: done! robot standing")
        self.setRestState(True)

    # --- movement gaits ---

    def walk(self, t=360):
        """walk gait using stand pose as base"""
        if self.isObstacleAhead():
            print("Obstacle! stopping walk.")
            return False

        sp = self._stand_pose
        a = 16
        ao = 50
        b = 5
        c = -30
        co = 10

        step1 = [sp[0] + 2.0 * a - ao, sp[1] - 4.0 * a + ao,
                 sp[2] + c + 5 * b, sp[3] - c - 4 * b,
                 sp[4] + 3.0 * a - co, sp[5] - 1.0 * a + co,
                 sp[6] - c - 4 * b - 10, sp[7] + c + 6 * b]
        step2 = [sp[0] + 2.3 * a - ao, sp[1] - 2.0 * a + ao,
                 sp[2] + c + 5 * b, sp[3] - c - 0 * b,
                 sp[4] + 3.3 * a - co, sp[5] - 1.3 * a + co,
                 sp[6] - c - 4 * b - 10, sp[7] + c + 6 * b]
        step3 = [sp[0] + 3.0 * a - ao, sp[1] - 1.0 * a + ao,
                 sp[2] + c + 4 * b, sp[3] - c - 6 * b,
                 sp[4] + 4.0 * a - co, sp[5] - 2.0 * a + co,
                 sp[6] - c - 4 * b - 10, sp[7] + c + 5 * b]
        step4 = [sp[0] + 3.3 * a - ao, sp[1] - 1.3 * a + ao,
                 sp[2] + c + 4 * b, sp[3] - c - 6 * b,
                 sp[4] + 2.0 * a - co, sp[5] - 2.3 * a + co,
                 sp[6] - c - 0 * b - 10, sp[7] + c + 5 * b]
        step5 = [sp[0] + 4.0 * a - ao, sp[1] - 2.0 * a + ao,
                 sp[2] + c + 4 * b, sp[3] - c - 5 * b,
                 sp[4] + 1.0 * a - co, sp[5] - 3.0 * a + co,
                 sp[6] - c - 6 * b - 10, sp[7] + c + 4 * b]
        step6 = [sp[0] + 2.0 * a - ao, sp[1] - 2.3 * a + ao,
                 sp[2] + c + 0 * b, sp[3] - c - 5 * b,
                 sp[4] + 1.3 * a - co, sp[5] - 3.3 * a + co,
                 sp[6] - c - 6 * b - 10, sp[7] + c + 4 * b]
        step7 = [sp[0] + 1.0 * a - ao, sp[1] - 3.0 * a + ao,
                 sp[2] + c + 6 * b, sp[3] - c - 4 * b,
                 sp[4] + 2.0 * a - co, sp[5] - 4.0 * a + co,
                 sp[6] - c - 5 * b - 10, sp[7] + c + 4 * b]
        step8 = [sp[0] + 1.3 * a - ao, sp[1] - 3.3 * a + ao,
                 sp[2] + c + 6 * b, sp[3] - c - 4 * b,
                 sp[4] + 2.3 * a - co, sp[5] - 2.0 * a + co,
                 sp[6] - c - 5 * b - 10, sp[7] + c + 0 * b]

        self._moveServos(t, step1)
        self._moveServos(t / 3, step2)
        self._moveServos(t, step3)
        self._moveServos(t / 3, step4)
        self._moveServos(t, step5)
        self._moveServos(t / 3, step6)
        self._moveServos(t, step7)
        self._moveServos(t / 3, step8)
        return True

    def walk1(self, steps=3, t=1000, dir=FORWARD):
        if dir == FORWARD and self.isObstacleAhead():
            print("Obstacle! stopping walk1.")
            return False

        self.attachServos()
        if self.getRestState():
            self.setRestState(False)

        amplitude = [
            15, 15, 20, 20,
            15, 15, 20, 20,
        ]
        period = [t, t, t / 2, t / 2,
                  t, t, t / 2, t / 2]
        offset = [0, 0, 0, 0, 0, 0, 0, 0]
        phase = [
            90, 90, 270, 90,
            270, 270, 90, 270
        ]

        if dir == BACKWARD:
            phase[0] = phase[1] = 270
            phase[4] = phase[5] = 90

        for i in range(self._servo_totals):
            self._servo[i].SetO(offset[i])
            self._servo[i].SetA(amplitude[i])
            self._servo[i].SetT(period[i])
            self._servo[i].SetPh(phase[i])

        _final_time = float(utime.ticks_ms()) + period[0] * steps
        _init_time = float(utime.ticks_ms())

        while float(utime.ticks_ms()) < _final_time:
            side = int((float(utime.ticks_ms()) - _init_time) / (period[0] / 2)) % 2
            self._servo[0].refresh()
            self._servo[1].refresh()
            self._servo[4].refresh()
            self._servo[5].refresh()
            if side == 0:
                self._servo[3].refresh()
                self._servo[6].refresh()
            else:
                self._servo[2].refresh()
                self._servo[7].refresh()

            utime.sleep(0.001)
        return True

    def forward(self, steps=3, t=800):
        if self.isObstacleAhead():
            print("Obstacle! stopping.")
            return False

        x_amp = 15
        z_amp = 15
        ap = 10
        hi = 15
        front_x = 6
        bll_amp = 20    # BLL needs more amplitude
        bll_offset = -10
        period = [t] * self._servo_totals
        amplitude = [x_amp, x_amp, bll_amp, z_amp, x_amp, x_amp, z_amp, z_amp]
        offset = [0 + ap - front_x,
                  0 - ap + front_x,
                  bll_offset,
                  0 + hi,
                  0 - ap - front_x,
                  0 + ap + front_x,
                  0 + hi,
                  0 - hi
                  ]
        phase = [180, 180, 90, 90,
                 0, 0, 90, 90]
        self._execute(amplitude, offset, period, phase, steps)
        return True

    def backward(self, steps=3, t=800):
        x_amp = 15
        z_amp = 15
        ap = 10
        hi = 15
        front_x = 6
        bll_amp = 20
        bll_offset = -10
        period = [t] * self._servo_totals
        amplitude = [x_amp, x_amp, bll_amp, z_amp, x_amp, x_amp, z_amp, z_amp]
        offset = [0 + ap - front_x,
                  0 - ap + front_x,
                  bll_offset,
                  0 + hi,
                  0 - ap - front_x,
                  0 + ap + front_x,
                  0 + hi,
                  0 - hi
                  ]
        phase = [0, 0, 90, 90,
                 180, 180, 90, 90]
        self._execute(amplitude, offset, period, phase, steps)
        return True

    def turn_L(self, steps=2, t=1000):
        x_amp = 15
        z_amp = 15
        ap = 5
        hi = 23
        period = [t] * self._servo_totals
        amplitude = [x_amp, x_amp, z_amp, z_amp, x_amp, x_amp, z_amp, z_amp]
        offset = [ap, -ap, -hi, +hi, -ap, ap, hi, -hi]
        phase = [0, 180, 90, 90, 180, 0, 90, 90]
        self._execute(amplitude, offset, period, phase, steps)

    def turn_R(self, steps=2, t=1000):
        x_amp = 15
        z_amp = 15
        ap = 5
        hi = 23
        period = [t] * self._servo_totals
        amplitude = [x_amp, x_amp, z_amp, z_amp, x_amp, x_amp, z_amp, z_amp]
        offset = [ap, -ap, -hi, +hi, -ap, ap, hi, -hi]
        phase = [180, 0, 90, 90, 0, 180, 90, 90]
        self._execute(amplitude, offset, period, phase, steps)

    def omni_walk(self, steps=2, t=1000, side=True, turn_factor=2):
        x_amp = 15
        z_amp = 15
        ap = 0
        hi = 23
        front_x = 6 * (1 - pow(turn_factor, 2))
        period = [t] * self._servo_totals
        amplitude = [x_amp, x_amp, z_amp, z_amp, x_amp, x_amp, z_amp, z_amp]
        offset = [
            0 + ap - front_x,
            0 - ap + front_x,
            0 - hi,
            0 + hi,
            0 - ap - front_x,
            0 + ap + front_x,
            0 + hi,
            0 - hi
        ]

        phase = [0] * self._servo_totals
        if side:
            phase1 = [0, 0, 90, 90, 180, 180, 90, 90]
            phase2R = [0, 180, 90, 90, 180, 0, 90, 90]
            for i in range(self._servo_totals):
                phase[i] = phase1[i] * (1 - turn_factor) + phase2R[i] * turn_factor
        else:
            phase1 = [0, 0, 90, 90, 180, 180, 90, 90]
            phase2L = [180, 0, 90, 90, 0, 180, 90, 90]
            for i in range(self._servo_totals):
                phase[i] = phase1[i] * (1 - turn_factor) + phase2L[i] * turn_factor + self._servo[
                    i]._phase
        self._execute(amplitude, offset, period, phase, steps)

    # --- fun moves ---

    def dance(self, steps=3, t=2000):
        x_amp = 0
        z_amp = 30
        ap = 0
        hi = 20
        period = [t] * self._servo_totals
        amplitude = [x_amp, x_amp, z_amp, z_amp, x_amp, x_amp, z_amp, z_amp]
        offset = [ap, -ap, -hi, +hi, -ap, ap, hi, -hi]
        phase = [0, 0, 0, 270, 0, 0, 90, 180]
        self._execute(amplitude, offset, period, phase, steps)

    def front_back(self, steps=2, t=1000):
        x_amp = 30
        z_amp = 20
        ap = 15
        hi = 30
        period = [t] * self._servo_totals
        amplitude = [x_amp, x_amp, z_amp, z_amp, x_amp, x_amp, z_amp, z_amp]
        offset = [ap, -ap, -hi, hi, -ap, ap, hi, -hi]
        phase = [0, 180, 270, 90, 0, 180, 90, 270]
        self._execute(amplitude, offset, period, phase, steps)

    def moonwalk_L(self, steps=4, t=2000):
        z_amp = 25
        o = 5
        period = [t] * self._servo_totals
        amplitude = [0, 0, z_amp, z_amp, 0, 0, z_amp, z_amp]
        offset = [0, 0, -z_amp - o, z_amp + o, 0, 0, z_amp + o, -z_amp - o]
        phase = [0, 0, 0, 80, 0, 0, 160, 290]
        self._execute(amplitude, offset, period, phase, steps)

    def up_down(self, steps=2, t=2000):
        x_amp = 0
        z_amp = 35
        ap = 10
        hi = 15
        front_x = 0
        period = [t] * self._servo_totals
        amplitude = [x_amp, x_amp, z_amp, z_amp, x_amp, x_amp, z_amp, z_amp]
        offset = [
            ap - front_x,
            -ap + front_x,
            -hi,
            hi,
            -ap - front_x,
            ap + front_x,
            hi,
            -hi
        ]
        phase = [0, 0, 90, 270, 180, 180, 270, 90]
        self._execute(amplitude, offset, period, phase, steps)

    def push_up(self, steps=2, t=2000):
        z_amp = 40
        x_amp = 45
        hi = 0
        b = 35
        period = [t] * self._servo_totals
        amplitude = [0, 0, z_amp, z_amp, 0, 0, 0, 0]
        offset = [0, 0, -hi, hi, x_amp, -x_amp, b, -b]
        phase = [0, 0, 90, -90, 0, 0, 0, 0]
        self._execute(amplitude, offset, period, phase, steps)

    def hello(self):
        """wave hello gesture"""
        self.attachServos()
        if self.getRestState():
            self.setRestState(False)

        sp = self._stand_pose
        a = 50
        b = 30
        c = 20
        d = 70
        state1 = [sp[0] - a, sp[1], sp[2] + c, sp[3] - c,
                   sp[4] + c, sp[5] - c, sp[6] - d, sp[7] + d]
        state2 = [sp[0] - a, sp[1] + b, sp[2] + c, sp[3] + d,
                   sp[4] + c, sp[5] - c, sp[6] - d, sp[7] + d]
        state3 = [sp[0] - a, sp[1] - b, sp[2] + c, sp[3] + d,
                   sp[4] + c, sp[5] - c, sp[6] - d, sp[7] + d]

        self._moveServos(300, state1)

        for i in range(3):
            self._moveServos(200, state2)
            self._moveServos(200, state3)

        utime.sleep_ms(300)
        self._moveServos(300, self._stand_pose)

    def wave_hand(self, steps=3, t=2000):
        period = [t] * self._servo_totals
        amplitude = [20, 0, 0, 30, 0, 0, 0, 0]
        offset = [-50, 0, 20, 60, 0, 0, 0, 0]
        phase = [0] * self._servo_totals
        self._execute(amplitude, offset, period, phase, steps)

    def hide(self, steps=1.0, t=2000):
        a = 60
        b = 70
        period = [t] * self._servo_totals
        amplitude = [0, 0, 0, 0, 0, 0, 0, 0]
        offset = [-a, a, b, -b, a, -a, -b, b]
        phase = [0, 0, 0, 0, 0, 0, 0, 0]
        self._execute(amplitude, offset, period, phase, steps)

    def scared(self):
        """scared reaction lol"""
        sp = self._stand_pose
        ap = 10
        hi = 40

        sentado = [sp[0] - 15, sp[1] + 15, sp[2] - hi, sp[3] + hi,
                   sp[4] - 20, sp[5] + 20, sp[6] + hi, sp[7] - hi]
        salto = [sp[0] - ap, sp[1] + ap, 160, 20,
                 sp[4] + ap * 3, sp[5] - ap * 3, 20, 160]

        self._moveServos(600, sentado)
        self._moveServos(1000, salto)
        utime.sleep_ms(1000)
        self._moveServos(500, self._stand_pose)

    def scan(self, rotations=1):
        """360 scan - rotates slowly for ultrasonic readings"""
        turns_per_rotation = 4
        total_turns = turns_per_rotation * rotations
        scan_speed = 1500  # ms per turn (slow for accuracy)

        for _ in range(total_turns):
            self.turn_R(steps=1, t=scan_speed)

        self.stand()

    def trot_walk(self, steps=4, t=800, direction=FORWARD):
        """trot gait - diagonal pairs move together
        FL+BR vs FR+BL with 180deg phase separation"""

        if direction == FORWARD and self.isObstacleAhead():
            print("Obstacle! stopping trot.")
            return False

        hip_amp = 18    # lateral movement
        leg_amp = 20    # vertical lift
        body_tilt = 12  # weight transfer

        period = [t] * self._servo_totals

        # order: FRH, FLH, FRL, FLL, BRH, BLH, BRL, BLL
        amplitude = [
            hip_amp,   # FRH
            hip_amp,   # FLH
            leg_amp,   # FRL
            leg_amp,   # FLL
            hip_amp,   # BRH
            hip_amp,   # BLH
            leg_amp,   # BRL
            leg_amp    # BLL
        ]

        offset = [
            0,            # FRH
            0,            # FLH
            -body_tilt,   # FRL
            body_tilt,    # FLL
            0,            # BRH
            0,            # BLH
            body_tilt,    # BRL
            -body_tilt    # BLL
        ]

        # diagonal pairs: pair1 (FL+BR) vs pair2 (FR+BL), 180deg apart
        if direction == FORWARD:
            phase = [
                0,    # FRH  (pair 2)
                180,  # FLH  (pair 1)
                90,   # FRL  (pair 2, leg lift offset)
                270,  # FLL  (pair 1, leg lift offset)
                180,  # BRH  (pair 1)
                0,    # BLH  (pair 2)
                270,  # BRL  (pair 1, leg lift offset)
                90    # BLL  (pair 2, leg lift offset)
            ]
        else:
            phase = [
                180,  # FRH
                0,    # FLH
                270,  # FRL
                90,   # FLL
                0,    # BRH
                180,  # BLH
                90,   # BRL
                270   # BLL
            ]

        self._execute(amplitude, offset, period, phase, steps)
        return True


if __name__ == '__main__':
    quad = Quad()
    quad.init(12, 16, 25, 18, 13, 17, 26, 19)
    quad.home()

    while True:
        quad.forward()
        utime.sleep(0.5)
