# Balance demo script
# shows how to use MPU6500 IMU for active balancing

from machine import I2C, Pin
import utime

from quad import Quad
from mpu6500 import MPU6500
from balance_controller import BalanceController

# ================================================
# CONFIG
# ================================================

SERVO_PINS = {
    'FRH': 12, 'FLH': 16,
    'FRL': 25, 'FLL': 18,
    'BRH': 13, 'BLH': 17,
    'BRL': 26, 'BLL': 19
}

I2C_SCL = 22
I2C_SDA = 21
IMU_INT_PIN = 4   # set to None to disable interrupt

# PID tuning
BALANCE_KP = 2.0
BALANCE_KI = 0.05
BALANCE_KD = 0.8

# ================================================
# INIT FUNCTIONS
# ================================================

def init_robot():
    robot = Quad()
    robot.init(
        SERVO_PINS['FRH'], SERVO_PINS['FLH'],
        SERVO_PINS['FRL'], SERVO_PINS['FLL'],
        SERVO_PINS['BRH'], SERVO_PINS['BLH'],
        SERVO_PINS['BRL'], SERVO_PINS['BLL']
    )
    return robot

def init_imu():
    print("Init I2C...")
    i2c = I2C(0, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=400000)

    devices = i2c.scan()
    print(f"I2C found: {[hex(d) for d in devices]}")

    if 0x68 not in devices and 0x69 not in devices:
        print("MPU6500 not found! check wiring:")
        print(f"  VCC->3.3V  GND->GND  SCL->GPIO{I2C_SCL}  SDA->GPIO{I2C_SDA}")
        if IMU_INT_PIN:
            print(f"  INT->GPIO{IMU_INT_PIN} (optional)")
        return None

    addr = 0x68 if 0x68 in devices else 0x69
    print(f"MPU6500 at 0x{addr:02x}")

    if IMU_INT_PIN:
        print(f"Interrupt on GPIO{IMU_INT_PIN}")
        imu = MPU6500(i2c, address=addr, int_pin=IMU_INT_PIN)
    else:
        print("Polling mode")
        imu = MPU6500(i2c, address=addr)
    return imu

def init_balance(imu):
    balance = BalanceController(imu, filter_alpha=0.98)
    balance.set_pid_gains(kp=BALANCE_KP, ki=BALANCE_KI, kd=BALANCE_KD)
    return balance

# ================================================
# DEMOS
# ================================================

def demo_balanced_stand(robot):
    print("\n" + "=" * 40)
    print("DEMO: Balanced Stand")
    print("=" * 40)
    print("Put robot on uneven surface - it auto-adjusts!")
    robot.balancedStand(duration_ms=10000, update_rate_ms=20)

def demo_balanced_walk(robot):
    print("\n" + "=" * 40)
    print("DEMO: Balanced Walk")
    print("=" * 40)

    robot.enableBalance()
    for i in range(3):
        print(f"Step {i+1}/3")
        if not robot.forward(steps=2, t=800):
            print("Stopped (obstacle or fall)")
            break
        if robot.isFallen():
            print("Robot fell!")
            break
        utime.sleep_ms(200)

    robot.stand()
    robot.disableBalance()

def demo_tilt_monitoring(robot):
    print("\n" + "=" * 40)
    print("DEMO: Tilt Monitor")
    print("=" * 40)
    print("Tilt robot to see angles. Ctrl+C to stop.")

    robot.stand()
    robot.disableBalance()

    try:
        while True:
            roll, pitch = robot.getBalanceAngles()
            tilted = robot.isTilted(threshold=10)
            fallen = robot.isFallen(threshold=45)
            status = "FALLEN!" if fallen else ("TILTED" if tilted else "OK")
            print(f"Roll: {roll:+6.1f} | Pitch: {pitch:+6.1f} | {status}")
            utime.sleep_ms(100)
    except KeyboardInterrupt:
        print("\nStopped.")

def demo_pid_tuning(robot):
    print("\n" + "=" * 40)
    print("DEMO: PID Tuning")
    print("=" * 40)
    print(f"Kp={BALANCE_KP}  Ki={BALANCE_KI}  Kd={BALANCE_KD}")
    print("Tips:")
    print("  oscillating? increase Kd or decrease Kp")
    print("  too slow? increase Kp")
    print("  drifting? increase Ki (careful)")

    robot.enableBalance()
    robot.balancedStand(duration_ms=5000)
    robot.disableBalance()

# ================================================
# MAIN
# ================================================

def main():
    print("=" * 40)
    print("Balance Demo")
    print("=" * 40)

    print("Init robot...")
    robot = init_robot()

    print("Init IMU...")
    imu = init_imu()
    if imu is None:
        print("IMU failed, exiting.")
        return

    print("Init balance...")
    balance = init_balance(imu)
    robot.setBalanceController(balance)

    print("\nCalibrating... KEEP STILL!")
    utime.sleep_ms(1000)
    robot.calibrateBalance()

    print("Standing up...")
    robot.startup()

    print("\nSelect demo:")
    print("  1. Balanced Stand")
    print("  2. Balanced Walk")
    print("  3. Tilt Monitor")
    print("  4. Continuous Balance")

    # run balanced stand demo by default
    demo_balanced_stand(robot)

    robot.home()
    print("Done!")


def continuous_balance_mode():
    """keep robot balanced forever (Ctrl+C to stop)"""
    print("Continuous Balance Mode")

    robot = init_robot()
    imu = init_imu()
    if imu is None:
        return

    balance = init_balance(imu)
    robot.setBalanceController(balance)

    print("Calibrating... keep still!")
    utime.sleep_ms(1000)
    robot.calibrateBalance()

    robot.startup()
    robot.enableBalance()

    try:
        while True:
            corrections = balance.update()
            roll, pitch = balance.get_angles()

            stand_pose = robot._stand_pose
            for i in range(8):
                corrected = int(stand_pose[i] + corrections[i])
                robot._servo[i].SetPosition(corrected)

            if abs(roll) > 2 or abs(pitch) > 2:
                print(f"Roll: {roll:+5.1f} | Pitch: {pitch:+5.1f}")

            utime.sleep_ms(20)

    except KeyboardInterrupt:
        robot.disableBalance()
        robot.home()
        print("\nStopped.")


if __name__ == '__main__':
    main()
    # or: continuous_balance_mode()
