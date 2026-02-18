# MPU6500 IMU driver for MicroPython
# reads accelerometer, gyroscope, and temp data
# used for active balancing on the quadruped robot

from micropython import const
import struct
import utime

# register addresses
_WHO_AM_I = const(0x75)
_PWR_MGMT_1 = const(0x6B)
_PWR_MGMT_2 = const(0x6C)
_CONFIG = const(0x1A)
_GYRO_CONFIG = const(0x1B)
_ACCEL_CONFIG = const(0x1C)
_ACCEL_CONFIG2 = const(0x1D)
_SMPLRT_DIV = const(0x19)
_INT_PIN_CFG = const(0x37)
_INT_ENABLE = const(0x38)

# data registers
_ACCEL_XOUT_H = const(0x3B)
_GYRO_XOUT_H = const(0x43)
_TEMP_OUT_H = const(0x41)

# gyro full scale ranges
_GYRO_FS_250 = const(0x00)    # +/- 250 deg/s
_GYRO_FS_500 = const(0x08)    # +/- 500 deg/s
_GYRO_FS_1000 = const(0x10)   # +/- 1000 deg/s
_GYRO_FS_2000 = const(0x18)   # +/- 2000 deg/s

# accel full scale ranges
_ACCEL_FS_2G = const(0x00)    # +/- 2g
_ACCEL_FS_4G = const(0x08)    # +/- 4g
_ACCEL_FS_8G = const(0x10)    # +/- 8g
_ACCEL_FS_16G = const(0x18)   # +/- 16g

# conversion factors (raw -> physical units)
_GYRO_SCALE = {
    _GYRO_FS_250: 131.0,
    _GYRO_FS_500: 65.5,
    _GYRO_FS_1000: 32.8,
    _GYRO_FS_2000: 16.4
}

_ACCEL_SCALE = {
    _ACCEL_FS_2G: 16384.0,
    _ACCEL_FS_4G: 8192.0,
    _ACCEL_FS_8G: 4096.0,
    _ACCEL_FS_16G: 2048.0
}


class MPU6500:
    """MPU6500 6-axis IMU - accel + gyro + temp
    supports optional interrupt pin for faster response"""

    def __init__(self, i2c, address=0x68, gyro_fs=_GYRO_FS_500, accel_fs=_ACCEL_FS_4G, int_pin=None):
        self.i2c = i2c
        self.address = address
        self._gyro_fs = gyro_fs
        self._accel_fs = accel_fs
        self._gyro_scale = _GYRO_SCALE[gyro_fs]
        self._accel_scale = _ACCEL_SCALE[accel_fs]

        self._gyro_bias = [0.0, 0.0, 0.0]  # calibrated at startup

        # interrupt stuff
        self._int_pin = None
        self._int_pin_num = None
        self._data_ready = False
        self._callback = None
        self._machine = None

        self._init_sensor()

        if int_pin is not None:
            self._setup_interrupt(int_pin)

    def _write_reg(self, reg, value, retries=3):
        for attempt in range(retries):
            try:
                self.i2c.writeto_mem(self.address, reg, bytes([value]))
                return
            except OSError as e:
                if attempt < retries - 1:
                    utime.sleep_ms(5)
                else:
                    raise e

    def _read_reg(self, reg, nbytes=1, retries=3):
        for attempt in range(retries):
            try:
                return self.i2c.readfrom_mem(self.address, reg, nbytes)
            except OSError as e:
                if attempt < retries - 1:
                    utime.sleep_ms(5)
                else:
                    raise e

    def _init_sensor(self):
        """configure the MPU6500"""
        who = self._read_reg(_WHO_AM_I)[0]
        if who not in (0x70, 0x71, 0x73):
            raise RuntimeError(f"MPU6500 not found! WHO_AM_I=0x{who:02x}")

        # wake up
        self._write_reg(_PWR_MGMT_1, 0x00)
        utime.sleep_ms(10)

        # reset
        self._write_reg(_PWR_MGMT_1, 0x80)
        utime.sleep_ms(100)

        # clock source = PLL with gyro ref
        self._write_reg(_PWR_MGMT_1, 0x01)
        utime.sleep_ms(10)

        # set ranges
        self._write_reg(_GYRO_CONFIG, self._gyro_fs)
        self._write_reg(_ACCEL_CONFIG, self._accel_fs)

        # sample rate = 1kHz / (1+9) = 100Hz
        self._write_reg(_SMPLRT_DIV, 9)

        # DLPF at 41Hz bandwidth
        self._write_reg(_CONFIG, 0x03)
        self._write_reg(_ACCEL_CONFIG2, 0x03)

        utime.sleep_ms(50)
        print(f"MPU6500 init ok (0x{who:02x})")

    def _setup_interrupt(self, pin_num):
        """setup data-ready interrupt on a GPIO pin"""
        import machine
        self._machine = machine
        self._int_pin_num = pin_num

        # INT pin config: clear on any read, latch
        self._write_reg(_INT_PIN_CFG, 0x30)
        utime.sleep_ms(10)

        # enable data ready interrupt
        self._write_reg(_INT_ENABLE, 0x01)
        utime.sleep_ms(10)

        # clear pending interrupt
        self._read_reg(0x3A)
        utime.sleep_ms(10)

        # attach GPIO interrupt
        self._int_pin = machine.Pin(pin_num, machine.Pin.IN)
        self._int_pin.irq(trigger=machine.Pin.IRQ_RISING, handler=self._int_handler)

        utime.sleep_ms(50)
        print(f"MPU6500 interrupt on GPIO {pin_num}")

    def disable_interrupt(self):
        if self._int_pin:
            self._int_pin.irq(handler=None)
            self._data_ready = False

    def enable_interrupt(self):
        if self._int_pin:
            try:
                self._read_reg(0x3A)
            except:
                pass
            self._int_pin.irq(trigger=self._machine.Pin.IRQ_RISING, handler=self._int_handler)

    def _int_handler(self, pin):
        self._data_ready = True
        if self._callback:
            self._callback()

    def set_data_ready_callback(self, callback):
        """set callback for when new data is ready (runs in ISR context, keep it short!)"""
        self._callback = callback

    def is_data_ready(self):
        if self._int_pin:
            ready = self._data_ready
            self._data_ready = False
            return ready
        else:
            status = self._read_reg(0x3A)[0]
            return (status & 0x01) != 0

    def wait_for_data(self, timeout_ms=100):
        """block until data ready or timeout"""
        start = utime.ticks_ms()
        while utime.ticks_diff(utime.ticks_ms(), start) < timeout_ms:
            if self.is_data_ready():
                return True
            utime.sleep_us(100)
        return False

    def get_accel_raw(self):
        """raw accel values (16-bit signed)"""
        data = self._read_reg(_ACCEL_XOUT_H, 6)
        ax = struct.unpack('>h', data[0:2])[0]
        ay = struct.unpack('>h', data[2:4])[0]
        az = struct.unpack('>h', data[4:6])[0]
        return ax, ay, az

    def get_accel(self):
        """accel in g units"""
        ax, ay, az = self.get_accel_raw()
        return (
            ax / self._accel_scale,
            ay / self._accel_scale,
            az / self._accel_scale
        )

    def get_gyro_raw(self):
        """raw gyro values (16-bit signed)"""
        data = self._read_reg(_GYRO_XOUT_H, 6)
        gx = struct.unpack('>h', data[0:2])[0]
        gy = struct.unpack('>h', data[2:4])[0]
        gz = struct.unpack('>h', data[4:6])[0]
        return gx, gy, gz

    def get_gyro(self):
        """gyro in deg/s with bias correction"""
        gx, gy, gz = self.get_gyro_raw()
        return (
            gx / self._gyro_scale - self._gyro_bias[0],
            gy / self._gyro_scale - self._gyro_bias[1],
            gz / self._gyro_scale - self._gyro_bias[2]
        )

    def get_all_raw(self):
        """read everything in one I2C transaction (faster)"""
        # 14 bytes: accel(6) + temp(2) + gyro(6)
        data = self._read_reg(_ACCEL_XOUT_H, 14)
        ax = struct.unpack('>h', data[0:2])[0]
        ay = struct.unpack('>h', data[2:4])[0]
        az = struct.unpack('>h', data[4:6])[0]
        # skip temp bytes [6:8]
        gx = struct.unpack('>h', data[8:10])[0]
        gy = struct.unpack('>h', data[10:12])[0]
        gz = struct.unpack('>h', data[12:14])[0]
        return ax, ay, az, gx, gy, gz

    def get_all(self):
        """accel (g) + gyro (deg/s) in one shot"""
        ax, ay, az, gx, gy, gz = self.get_all_raw()
        return (
            ax / self._accel_scale,
            ay / self._accel_scale,
            az / self._accel_scale,
            gx / self._gyro_scale - self._gyro_bias[0],
            gy / self._gyro_scale - self._gyro_bias[1],
            gz / self._gyro_scale - self._gyro_bias[2]
        )

    def get_temperature(self):
        """temp from IMU in celsius"""
        data = self._read_reg(_TEMP_OUT_H, 2)
        raw_temp = struct.unpack('>h', data)[0]
        return (raw_temp / 333.87) + 21.0

    def calibrate_gyro(self, samples=200):
        """calibrate gyro bias - KEEP ROBOT STILL during this!"""
        print("Calibrating gyro... keep still!")

        # disable interrupt during cal to avoid I2C conflicts
        had_interrupt = self._int_pin is not None
        if had_interrupt:
            self.disable_interrupt()
            utime.sleep_ms(20)

        sum_gx = 0.0
        sum_gy = 0.0
        sum_gz = 0.0
        successful_samples = 0

        for i in range(samples):
            try:
                gx, gy, gz = self.get_gyro_raw()
                sum_gx += gx / self._gyro_scale
                sum_gy += gy / self._gyro_scale
                sum_gz += gz / self._gyro_scale
                successful_samples += 1
            except OSError as e:
                print(f"  read error on sample {i}, retrying...")
                utime.sleep_ms(10)
            utime.sleep_ms(5)

        if successful_samples < samples // 2:
            print(f"ERROR: only {successful_samples}/{samples} samples!")
            if had_interrupt:
                self.enable_interrupt()
            return tuple(self._gyro_bias)

        self._gyro_bias[0] = sum_gx / successful_samples
        self._gyro_bias[1] = sum_gy / successful_samples
        self._gyro_bias[2] = sum_gz / successful_samples

        print(f"Gyro bias: X={self._gyro_bias[0]:.3f}, Y={self._gyro_bias[1]:.3f}, Z={self._gyro_bias[2]:.3f}")
        print(f"  ({successful_samples}/{samples} samples)")

        if had_interrupt:
            utime.sleep_ms(20)
            self.enable_interrupt()

        return tuple(self._gyro_bias)

    def is_connected(self):
        try:
            who = self._read_reg(_WHO_AM_I)[0]
            return who in (0x70, 0x71, 0x73)
        except OSError:
            return False

    def reset(self):
        """hard reset and reinitialize"""
        print("Resetting MPU6500...")
        if self._int_pin:
            self.disable_interrupt()
        self._write_reg(_PWR_MGMT_1, 0x80)
        utime.sleep_ms(100)
        self._init_sensor()
        if self._int_pin_num:
            self._setup_interrupt(self._int_pin_num)


# quick test
if __name__ == '__main__':
    from machine import I2C, Pin

    i2c = I2C(1, scl=Pin(25), sda=Pin(26), freq=400000)

    print("Scanning I2C...")
    devices = i2c.scan()
    print(f"Found: {[hex(d) for d in devices]}")

    if 0x68 in devices or 0x69 in devices:
        addr = 0x68 if 0x68 in devices else 0x69
        imu = MPU6500(i2c, address=addr)
        imu.calibrate_gyro()

        print("\nReading (Ctrl+C to stop):")
        while True:
            ax, ay, az, gx, gy, gz = imu.get_all()
            temp = imu.get_temperature()
            print(f"Accel: ({ax:+.2f}, {ay:+.2f}, {az:+.2f})g | "
                  f"Gyro: ({gx:+.1f}, {gy:+.1f}, {gz:+.1f})deg/s | "
                  f"Temp: {temp:.1f}C")
            utime.sleep_ms(100)
    else:
        print("MPU6500 not found! check wiring.")
