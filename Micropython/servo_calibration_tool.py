"""
Servo Calibration Tool for Quadruped Robot
helps find the true neutral (90deg) for each servo

usage:
  1. upload to ESP32
  2. run: import servo_calibration_tool
  3. follow prompts in REPL
  4. copy trim values to your main code

servo index map:
  0: FRH   1: FLH   2: FRL   3: FLL
  4: BRH   5: BLH   6: BRL   7: BLL
"""

from machine import Pin, PWM
import utime
import json

# ================================================
# CONFIG
# ================================================

SERVO_PINS = [12, 16, 25, 18, 13, 17, 26, 19]

SERVO_NAMES = [
    "FLH (Front Left Hip)",
    "FRH (Front Right Hip)",
    "BLL (Back Left Knee)",
    "BRL (Back Right Knee)",
    "BLH (Back Left Hip)",
    "BRH (Back Right Hip)",
    "FLL (Front Left Knee)",
    "FRL (Front Right Knee)"
]

PWM_FREQ = 50
CALIBRATION_FILE = "servo_trims.json"

# ================================================
# SERVO CLASS
# ================================================

class CalibrationServo:
    def __init__(self, pin, name="Servo"):
        self.pin_num = pin
        self.name = name
        self.pwm = PWM(Pin(pin), freq=PWM_FREQ)
        self.current_angle = 90
        self.trim = 0

    def set_angle(self, angle):
        angle = max(0, min(180, angle))
        self.current_angle = angle
        duty = int((angle / 180) * 102 + 26)
        self.pwm.duty(duty)

    def adjust(self, delta):
        new_angle = self.current_angle + delta
        self.set_angle(new_angle)
        return self.current_angle

    def get_trim(self):
        return self.current_angle - 90

    def release(self):
        self.pwm.duty(0)

    def deinit(self):
        self.pwm.deinit()

# ================================================
# CALIBRATION TOOL
# ================================================

class ServoCalibrationTool:
    def __init__(self, pins=SERVO_PINS, names=SERVO_NAMES):
        self.servos = []
        for i, pin in enumerate(pins):
            name = names[i] if i < len(names) else f"Servo {i}"
            self.servos.append(CalibrationServo(pin, name))
        self.trims = [0] * len(pins)

    def center_all(self):
        print("\n>>> All servos to 90...")
        for servo in self.servos:
            servo.set_angle(90)
        utime.sleep_ms(500)
        print(">>> Done.\n")

    def apply_trims(self, trims):
        print("\n>>> Applying trims...")
        for i, servo in enumerate(self.servos):
            trim = trims[i] if i < len(trims) else 0
            servo.trim = trim
            servo.set_angle(90 + trim)
        utime.sleep_ms(500)
        print(">>> Done.\n")

    def calibrate_single(self, servo_index):
        """interactive calibration for one servo"""
        servo = self.servos[servo_index]

        print(f"\n{'='*50}")
        print(f"CALIBRATING: [{servo_index}] {servo.name}")
        print(f"{'='*50}")
        print(f"Pin: GPIO {servo.pin_num}")
        print("Commands: +1 +5 +10 -1 -5 -10 | 90 | done | skip")

        servo.set_angle(90)

        while True:
            current = servo.current_angle
            trim = servo.get_trim()
            print(f"  {current}deg (trim: {trim:+d}) > ", end="")

            try:
                cmd = input().strip().lower()
            except:
                cmd = "done"

            if cmd == "done":
                self.trims[servo_index] = trim
                print(f">>> Saved: {trim:+d}")
                return trim
            elif cmd == "skip":
                self.trims[servo_index] = 0
                servo.set_angle(90)
                print(">>> Skipped")
                return 0
            elif cmd == "90":
                servo.set_angle(90)
            elif cmd.startswith("+") or cmd.startswith("-") or cmd.isdigit():
                try:
                    if cmd.startswith("+") or cmd.startswith("-"):
                        servo.adjust(int(cmd))
                    else:
                        servo.set_angle(int(cmd))
                except ValueError:
                    print("Invalid. use +N, -N, or angle")
            else:
                print("Try: +5, -5, 90, done, skip")

    def calibrate_all(self):
        """full calibration for all 8 servos"""
        print(f"\n{'='*50}")
        print(" SERVO CALIBRATION")
        print(f"{'='*50}")
        print("Goal: robot stands level with equal weight on all legs")
        print("Tips: hips first (0,1,4,5) then knees (2,3,6,7)")

        self.center_all()
        input("Press ENTER to begin...")

        for i in range(len(self.servos)):
            self.calibrate_single(i)

        self.print_summary()

        print("\nSave to file? (y/n): ", end="")
        try:
            if input().strip().lower() == "y":
                self.save_calibration()
        except:
            pass
        return self.trims

    def calibrate_pair(self, pair_name):
        pairs = {
            "front_hips": [0, 1],
            "back_hips": [4, 5],
            "front_knees": [2, 3],
            "back_knees": [6, 7],
            "right_side": [0, 2, 4, 6],
            "left_side": [1, 3, 5, 7],
            "hips": [0, 1, 4, 5],
            "knees": [2, 3, 6, 7],
        }
        if pair_name not in pairs:
            print(f"Unknown: {pair_name}. Options: {list(pairs.keys())}")
            return
        for i in pairs[pair_name]:
            self.calibrate_single(i)
        self.print_summary()

    def quick_adjust(self, servo_index, delta):
        if 0 <= servo_index < len(self.servos):
            new_angle = self.servos[servo_index].adjust(delta)
            trim = self.servos[servo_index].get_trim()
            print(f"[{servo_index}] {self.servos[servo_index].name}: {new_angle}deg (trim: {trim:+d})")
            self.trims[servo_index] = trim
        else:
            print(f"Invalid: {servo_index}")

    def set_servo(self, servo_index, angle):
        if 0 <= servo_index < len(self.servos):
            self.servos[servo_index].set_angle(angle)
            trim = self.servos[servo_index].get_trim()
            print(f"[{servo_index}] {self.servos[servo_index].name}: {angle}deg (trim: {trim:+d})")
            self.trims[servo_index] = trim
        else:
            print(f"Invalid: {servo_index}")

    def print_summary(self):
        print(f"\n{'='*50}")
        print(" CALIBRATION SUMMARY")
        print(f"{'='*50}\n")
        print("Servo                          | Trim")
        print("-" * 42)
        for i, servo in enumerate(self.servos):
            print(f"[{i}] {servo.name:26} | {self.trims[i]:+4d}")
        print()
        print(">>> Copy to your main code:")
        print(f"robot.setTrims({self.trims[0]}, {self.trims[1]}, {self.trims[2]}, {self.trims[3]}, "
              f"{self.trims[4]}, {self.trims[5]}, {self.trims[6]}, {self.trims[7]})")
        print()

    def save_calibration(self, filename=CALIBRATION_FILE):
        data = {
            "trims": self.trims,
            "names": [s.name for s in self.servos],
            "pins": [s.pin_num for s in self.servos]
        }
        with open(filename, "w") as f:
            json.dump(data, f)
        print(f">>> Saved to {filename}")

    def load_calibration(self, filename=CALIBRATION_FILE):
        try:
            with open(filename, "r") as f:
                data = json.load(f)
            self.trims = data.get("trims", [0] * len(self.servos))
            print(f">>> Loaded: {self.trims}")
            return True
        except:
            print(f">>> No file: {filename}")
            return False

    def test_calibration(self):
        print("\n>>> Testing trims...")
        self.apply_trims(self.trims)
        print(">>> Should be balanced. If not, calibrate_single(N)")

    def release_all(self):
        print(">>> Releasing servos...")
        for servo in self.servos:
            servo.release()
        print(">>> Servos limp.")

    def deinit(self):
        for servo in self.servos:
            servo.deinit()

# ================================================
# QUICK REPL FUNCTIONS
# ================================================

_tool = None

def start():
    global _tool
    _tool = ServoCalibrationTool()
    return _tool

def calibrate():
    global _tool
    if _tool is None:
        _tool = ServoCalibrationTool()
    return _tool.calibrate_all()

def center():
    global _tool
    if _tool is None:
        _tool = ServoCalibrationTool()
    _tool.center_all()

def adjust(servo, delta):
    global _tool
    if _tool is None:
        _tool = ServoCalibrationTool()
    _tool.quick_adjust(servo, delta)

def set_angle(servo, angle):
    global _tool
    if _tool is None:
        _tool = ServoCalibrationTool()
    _tool.set_servo(servo, angle)

def summary():
    global _tool
    if _tool is None:
        print("Run start() first.")
    else:
        _tool.print_summary()

def save():
    global _tool
    if _tool:
        _tool.save_calibration()

def load():
    global _tool
    if _tool is None:
        _tool = ServoCalibrationTool()
    _tool.load_calibration()
    _tool.test_calibration()

def test():
    global _tool
    if _tool:
        _tool.test_calibration()

def release():
    global _tool
    if _tool:
        _tool.release_all()

def help():
    print("""
CALIBRATION TOOL COMMANDS
=========================

Horn Mounting:
  mount_mode()         interactive guide
  mount_servo(n)       center servo N
  mount_next()         next servo

Stand Pose:
  find_stand_pose()    interactive pose finder
  stand_pose()         apply saved pose
  flat()               all servos to 90

Calibration:
  start()              init tool
  calibrate()          full interactive
  center()             all to 90
  adjust(n, delta)     quick adjust
  set_angle(n, angle)  set angle
  summary()            show trims
  save() / load()      file ops
  test()               apply trims
  release()            go limp
""")

# ================================================
# HORN MOUNTING MODE
# ================================================

_mount_index = 0

def mount_servo(servo_index):
    """center servo for horn mounting (other servos go limp)"""
    global _tool, _mount_index
    if _tool is None:
        _tool = ServoCalibrationTool()
    if servo_index < 0 or servo_index >= len(_tool.servos):
        print(f"Invalid: {servo_index}")
        return
    _mount_index = servo_index
    servo = _tool.servos[servo_index]

    for i, s in enumerate(_tool.servos):
        if i == servo_index:
            s.set_angle(90)
        else:
            s.release()

    print(f"\n{'='*40}")
    print(f" MOUNTING [{servo_index}]: {servo.name}")
    print(f"{'='*40}")
    print(f" GPIO {servo.pin_num} - holding at 90")
    print(" 1. position leg at neutral")
    print(" 2. press horn on")
    print(" 3. screw in")
    print(" 4. run mount_next()")

def mount_next():
    global _mount_index
    _mount_index = (_mount_index + 1) % 8
    mount_servo(_mount_index)

def mount_mode():
    """guided horn mounting for all 8 servos"""
    global _tool, _mount_index
    if _tool is None:
        _tool = ServoCalibrationTool()

    print(f"\n{'='*50}")
    print(" HORN MOUNTING MODE")
    print(f"{'='*50}")
    print(" Each servo centers at 90, attach horn at neutral")
    print(" Order: hips (0,1,4,5) then knees (2,3,6,7)")

    mount_order = [0, 1, 4, 5, 2, 3, 6, 7]

    input("Press ENTER to begin...")

    for i, servo_idx in enumerate(mount_order):
        servo = _tool.servos[servo_idx]
        print(f"\n[{i+1}/8] [{servo_idx}] {servo.name}")
        print("-" * 40)

        for j, s in enumerate(_tool.servos):
            if j == servo_idx:
                s.set_angle(90)
            else:
                s.release()

        print(f">>> Servo {servo_idx} at 90. Attach horn!")
        try:
            input(">>> ENTER when done...")
        except:
            pass

    print(f"\n{'='*50}")
    print(" MOUNTING COMPLETE!")
    print(f"{'='*50}")
    print(" Next: center() then calibrate()")
    _tool.center_all()

# ================================================
# STAND POSE FINDER
# ================================================

STAND_POSE = [140, 40, 155, 25, 40, 140, 25, 140]

def find_stand_pose():
    """interactive tool to find standing angles"""
    global _tool, STAND_POSE
    if _tool is None:
        _tool = ServoCalibrationTool()

    print(f"\n{'='*50}")
    print(" STAND POSE FINDER")
    print(f"{'='*50}")
    print(" Adjust servos until robot stands balanced")
    print(" Commands: +N/-N  s0-s7  all  test  done")

    current_pose = STAND_POSE.copy()
    current_servo = 0

    for i, angle in enumerate(current_pose):
        _tool.servos[i].set_angle(angle)

    while True:
        servo = _tool.servos[current_servo]
        angle = current_pose[current_servo]
        print(f"[{current_servo}] {servo.name}: {angle} > ", end="")

        try:
            cmd = input().strip().lower()
        except:
            cmd = "done"

        if cmd == "done":
            STAND_POSE = current_pose.copy()
            print(f"\n>>> STAND_POSE = {current_pose}")
            print(">>> Add to quad.py:")
            print(f"STAND_ANGLES = {current_pose}")
            try:
                data = {"stand_pose": current_pose}
                with open("stand_pose.json", "w") as f:
                    json.dump(data, f)
                print(">>> Saved to stand_pose.json")
            except:
                pass
            return current_pose

        elif cmd == "all":
            print("\nCurrent pose:")
            for i, ang in enumerate(current_pose):
                print(f"  [{i}] {_tool.servos[i].name}: {ang}")

        elif cmd == "test":
            print(">>> Applying...")
            for i, angle in enumerate(current_pose):
                _tool.servos[i].set_angle(angle)

        elif cmd.startswith("s") and len(cmd) == 2 and cmd[1].isdigit():
            new_servo = int(cmd[1])
            if 0 <= new_servo < 8:
                current_servo = new_servo
            else:
                print("Use s0-s7")

        elif cmd.startswith("+") or cmd.startswith("-"):
            try:
                delta = int(cmd)
                new_angle = max(0, min(180, current_pose[current_servo] + delta))
                current_pose[current_servo] = new_angle
                _tool.servos[current_servo].set_angle(new_angle)
            except ValueError:
                print("Invalid. Use +N or -N")

        elif cmd.isdigit():
            new_angle = max(0, min(180, int(cmd)))
            current_pose[current_servo] = new_angle
            _tool.servos[current_servo].set_angle(new_angle)

        else:
            print("Commands: +N -N s0-s7 all test done")

def stand_pose():
    global _tool, STAND_POSE
    if _tool is None:
        _tool = ServoCalibrationTool()
    try:
        with open("stand_pose.json", "r") as f:
            data = json.load(f)
        STAND_POSE = data.get("stand_pose", STAND_POSE)
        print(f">>> Loaded: {STAND_POSE}")
    except:
        print(f">>> Default: {STAND_POSE}")
    for i, angle in enumerate(STAND_POSE):
        _tool.servos[i].set_angle(angle)
    print(">>> Stand pose applied.")

def flat():
    global _tool
    if _tool is None:
        _tool = ServoCalibrationTool()
    _tool.center_all()
    print(">>> Flat (all 90)")

# ================================================
# AUTO-RUN
# ================================================

if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(" SERVO CALIBRATION TOOL")
    print(f"{'='*50}")
    print("Quick start:")
    print("  from servo_calibration_tool import *")
    print("  calibrate()   # full interactive")
    print("  adjust(0, +5) # quick adjust")
    print("  summary()     # show trims")
    help()
