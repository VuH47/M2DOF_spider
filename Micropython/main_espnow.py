"""
SpiderRobot - ESP-NOW main script
controls robot via ESP-NOW commands from master ESP32-S3
"""

from quad import Quad
from ultrasonic import Ultrasonic
from temperature import ESP32Temperature
from espnow_slave_compatible import ESPNowSlaveCompatible
import utime
from machine import Pin, I2C
from mpu6500 import MPU6500
from balance_controller import BalanceController

# ================================================
# CONFIG
# ================================================

MASTER_MAC = "e8:06:90:a1:f3:58" # you need to change to your own master devices 

# sensor pins
ULTRASONIC_TRIGGER_PIN = 22
ULTRASONIC_ECHO_PIN = 21
OBSTACLE_THRESHOLD_CM = 20

# timing
SENSOR_SEND_INTERVAL = 1000   # send sensor data every 1s
TEMP_UPDATE_INTERVAL = 5000   # update temp every 5s

# IMU / balance
I2C_BUS = 1
I2C_SCL_PIN = 25
I2C_SDA_PIN = 26
IMU_INT_PIN = 4

BALANCE_KP = 2.0
BALANCE_KI = 0.05
BALANCE_KD = 0.8

# SPM (Far From Home) params
SPM_SCAN_STEPS = 12
SPM_RSSI_SAMPLES = 5
SPM_TURN_MS = 1500
SPM_SETTLE_MS = 250
SPM_FORWARD_BURSTS = 4
SPM_FORWARD_MS = 900
PL_A = -59          # RSSI at 1m (dBm)
PL_N = 2.7          # path loss exponent

# ================================================
# INIT
# ================================================

print("SpiderRobot ESP-NOW")
print("=" * 40)

led = Pin(2, Pin.OUT)

# robot
print("Init robot...")
robot = Quad()
robot.init(12, 16, 25, 18, 13, 17, 26, 19)
robot.setTrims(0, 0, 0, 0, 0, 0, 0, 0)
print("OK")

# ultrasonic
print("Init ultrasonic...")
ultrasonic = Ultrasonic(trigger_pin=ULTRASONIC_TRIGGER_PIN, echo_pin=ULTRASONIC_ECHO_PIN)
robot.setUltrasonic(ultrasonic)
robot.setObstacleThreshold(OBSTACLE_THRESHOLD_CM)
print("OK")

# temperature
print("Init temp sensor...")
temp_sensor = ESP32Temperature(offset=17)
print("OK")

# IMU + balance
print("Init MPU6500...")
balance = None
try:
    i2c = I2C(I2C_BUS, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=400000)
    devices = i2c.scan()
    print(f"I2C devices: {[hex(d) for d in devices]}")

    if 0x68 in devices or 0x69 in devices:
        addr = 0x68 if 0x68 in devices else 0x69
        imu = MPU6500(i2c, address=addr, int_pin=IMU_INT_PIN)
        balance = BalanceController(imu, filter_alpha=0.98)
        balance.set_pid_gains(kp=BALANCE_KP, ki=BALANCE_KI, kd=BALANCE_KD)
        robot.setBalanceController(balance)

        print("Calibrating gyro - keep still!")
        balance.calibrate()
        print("Balance OK")
    else:
        print("MPU6500 not found - balance disabled")
except Exception as e:
    print(f"IMU init failed: {e}")
    print("Balance disabled")

# ESP-NOW
print("Init ESP-NOW...")
espnow = ESPNowSlaveCompatible(master_mac=MASTER_MAC, channel=1)
if not espnow.init():
    print("ERROR: ESP-NOW failed")
    raise Exception("ESP-NOW init failed")
print("OK - MAC:", espnow.get_mac())
print("Master:", MASTER_MAC)

# ================================================
# SPM: Far From Home
# ================================================

def estimate_distance_m(rssi):
    if rssi is None:
        return None
    return 10 ** ((PL_A - rssi) / (10 * PL_N))

def spm_read_rssi():
    mac, data = espnow.receive(timeout_ms=50)
    if mac is None or data is None:
        return None
    if isinstance(data, dict):
        if "rssi" in data:
            return data.get("rssi")
        if "last_rssi" in data:
            return data.get("last_rssi")
    return None

def spm_scan_headings():
    """rotate 360deg and sample RSSI to find strongest direction"""
    samples = []
    step_deg = 360 / SPM_SCAN_STEPS
    current_heading = 0.0
    for i in range(SPM_SCAN_STEPS):
        rssi_vals = []
        for _ in range(SPM_RSSI_SAMPLES):
            rssi = spm_read_rssi()
            if rssi is not None:
                rssi_vals.append(rssi)
            utime.sleep_ms(20)
        avg_rssi = sum(rssi_vals) / len(rssi_vals) if rssi_vals else None
        samples.append({
            "heading": current_heading,
            "rssi": avg_rssi,
            "dist_m": estimate_distance_m(avg_rssi)
        })
        robot.turn_R(steps=1, t=SPM_TURN_MS)
        utime.sleep_ms(SPM_SETTLE_MS)
        current_heading = (i + 1) * step_deg

    # pick best RSSI
    best = None
    best_score = -9999
    for s in samples:
        score = s["rssi"] if s["rssi"] is not None else -9999
        if score > best_score:
            best_score = score
            best = s
    return best, samples

def face_heading(target_heading_deg):
    if target_heading_deg is None:
        return
    step_deg = 360 / SPM_SCAN_STEPS
    error = target_heading_deg % 360
    if error > 180:
        steps_needed = int(round((360 - error) / step_deg))
        for _ in range(steps_needed):
            robot.turn_L(steps=1, t=SPM_TURN_MS)
            utime.sleep_ms(SPM_SETTLE_MS)
    else:
        steps_needed = int(round(error / step_deg))
        for _ in range(steps_needed):
            robot.turn_R(steps=1, t=SPM_TURN_MS)
            utime.sleep_ms(SPM_SETTLE_MS)
    robot.stand()

def crawl_toward_signal():
    for _ in range(SPM_FORWARD_BURSTS):
        if robot.isObstacleAhead():
            print("SPM: obstacle, stopping")
            return
        robot.forward(steps=1, t=SPM_FORWARD_MS)
        utime.sleep_ms(200)
        spm_read_rssi()
    robot.stand()

def run_spm_far_from_home():
    """scan -> face best RSSI -> crawl toward it"""
    print("SPM: starting")
    robot.stand()
    best, samples = spm_scan_headings()
    if not best:
        print("SPM: no RSSI data")
        return
    print("SPM: best heading", best)
    face_heading(best.get("heading"))
    crawl_toward_signal()
    print("SPM: done")

# ================================================
# COMMAND HANDLER
# ================================================

def convert_speed_to_time(speed_percent):
    """convert speed % (25-100) to servo time ms (1500-500)"""
    speed_percent = max(25, min(100, speed_percent))
    time_ms = int(2000 - (speed_percent * 15))
    return time_ms

_last_movement_time = 0
_movement_busy = False

def handle_espnow_command(command, params):
    global _last_movement_time, _movement_busy

    try:
        result = None
        requires_home = False

        is_movement_cmd = command in ["forward", "backward", "turn_left", "turn_right"]

        if is_movement_cmd:
            if _movement_busy:
                print(f"CMD: {command} - SKIPPED (busy)")
                return
            _movement_busy = True

        speed_percent = params.get("speed", 75)
        speed_time = convert_speed_to_time(speed_percent)

        # directional (returns to stand after)
        if command == "forward":
            steps = params.get("steps", 4)
            result = robot.forward(steps=steps, t=speed_time)
            robot.stand()
            print(f"CMD: forward @ {speed_percent}%")

        elif command == "backward":
            steps = params.get("steps", 4)
            result = robot.backward(steps=steps, t=speed_time)
            robot.stand()
            print(f"CMD: backward @ {speed_percent}%")

        elif command == "turn_left":
            steps = params.get("steps", 3)
            result = robot.turn_L(steps=steps, t=speed_time)
            robot.stand()
            print(f"CMD: turn_left @ {speed_percent}%")

        elif command == "turn_right":
            steps = params.get("steps", 3)
            result = robot.turn_R(steps=steps, t=speed_time)
            robot.stand()
            print(f"CMD: turn_right @ {speed_percent}%")

        if is_movement_cmd:
            _movement_busy = False

        elif command == "home":
            result = robot.home()
            print("CMD: home")

        elif command == "stand":
            result = robot.stand()
            print("CMD: stand")

        # motion commands (go back to stand when done)
        elif command == "hello":
            result = robot.hello()
            requires_home = True

        elif command == "moonwalk":
            steps = params.get("steps", 4)
            result = robot.moonwalk_L(steps=steps)
            requires_home = True

        elif command == "scan":
            result = robot.scan()
            requires_home = True

        elif command == "trot_walk":
            steps = params.get("steps", 4)
            t = params.get("t", 800)
            direction = params.get("direction", 1)
            result = robot.trot_walk(steps=steps, t=t, direction=direction)
            requires_home = True

        elif command == "spm_far_from_home":
            run_spm_far_from_home()
            result = {"status": "spm_completed"}

        # balance commands
        elif command == "balanced_stand":
            duration = params.get("duration", 5000)
            robot.balancedStand(duration_ms=duration)
            result = {"status": "balanced_stand_complete"}

        elif command == "enable_balance":
            robot.enableBalance()
            result = {"status": "balance_enabled"}

        elif command == "disable_balance":
            robot.disableBalance()
            result = {"status": "balance_disabled"}

        elif command == "get_balance":
            if balance:
                roll, pitch = balance.get_angles()
                result = {
                    "roll": round(roll, 2),
                    "pitch": round(pitch, 2),
                    "tilted": robot.isTilted(),
                    "enabled": robot.isBalanceEnabled()
                }
            else:
                result = {"error": "no balance controller"}

        # sensor queries
        elif command == "get_distance":
            result = {"distance_cm": ultrasonic.get_distance()}

        elif command == "get_temperature":
            result = {"temperature_c": temp_sensor.get_temperature_c()}

        elif command == "get_status":
            result = {
                "distance_cm": ultrasonic.get_distance(),
                "temperature_c": temp_sensor.get_temperature_c(),
                "servo_state": "active"
            }

        else:
            result = {"error": f"Unknown: {command}"}

        # return to stand for motion commands
        if requires_home:
            utime.sleep_ms(200)
            robot.stand()
            print(f"CMD: {command} -> stand")

        if espnow:
            espnow.send_response(result=result)

    except Exception as e:
        print(f"Error: {e}")
        _movement_busy = False
        try:
            robot.stand()
        except:
            pass
        if espnow:
            espnow.send_response(result=None, error=f"Error: {e}")

espnow.set_command_callback(handle_espnow_command)

# ================================================
# MAIN LOOP
# ================================================

print("=" * 40)
print("System Ready")
print("Starting up...")
robot.startup()
print("Waiting for commands...")
print("=" * 40)

last_sensor_send = 0
last_temp_update = 0
loop_count = 0
current_temperature = temp_sensor.get_temperature_c()

try:
    while True:
        loop_count += 1
        current_time = utime.ticks_ms()

        # update temp every 5s
        if utime.ticks_diff(current_time, last_temp_update) > TEMP_UPDATE_INTERVAL:
            last_temp_update = current_time
            current_temperature = temp_sensor.get_temperature_c()

        # send sensor data every 1s
        if utime.ticks_diff(current_time, last_sensor_send) > SENSOR_SEND_INTERVAL:
            last_sensor_send = current_time

            distance = ultrasonic.get_distance()

            if distance < 0:
                status = "NO_OBJECT"
                led.off()
            elif distance < OBSTACLE_THRESHOLD_CM:
                status = "OBSTACLE"
                led.on()
            else:
                status = "OK"
                led.off()

            espnow.send_sensor_data(
                distance=distance,
                temperature=current_temperature,
                status=status
            )

        # check for commands
        if espnow:
            espnow.receive(timeout_ms=10)

        utime.sleep_ms(100)

except KeyboardInterrupt:
    print("\nShutdown")
    robot.detachServos()
    led.off()
    if espnow:
        espnow.deinit()
    print("Bye!")

except Exception as e:
    print(f"ERROR: {e}")
    robot.detachServos()
    led.off()
    if espnow:
        espnow.deinit()
    raise
