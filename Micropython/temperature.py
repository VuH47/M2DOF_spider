# ESP32 internal temperature sensor driver
# reads the built-in temp sensor for thermal monitoring

import esp32
import utime


class ESP32Temperature:
    """ESP32 built-in temp sensor
    note: raw reading varies between chips, needs calibration offset"""

    def __init__(self, offset=17, scale=1.0):
        # offset calibrated: actual 30C, chip reads 13C, so +17
        self.offset = offset
        self.scale = scale
        self._readings_history = []
        self._max_history = 10

    def get_raw_reading(self):
        """raw sensor value (usually 100-150ish)"""
        return esp32.raw_temperature()

    def get_temperature_f(self):
        """temp in fahrenheit"""
        temp_c = self.get_temperature_c()
        temp_f = (temp_c * 9.0 / 5.0) + 32.0
        return temp_f

    def get_temperature_c(self):
        """temp in celsius with calibration offset applied"""
        raw = self.get_raw_reading()
        temp_c = raw + self.offset
        temp_c = temp_c * self.scale
        return temp_c

    def get_temperature_c_averaged(self, samples=5):
        """average multiple readings for more stable value"""
        readings = []
        for _ in range(samples):
            readings.append(self.get_temperature_c())
            utime.sleep_ms(50)
        return sum(readings) / len(readings)

    def record_reading(self):
        """save temp to history buffer"""
        temp = self.get_temperature_c()
        self._readings_history.append(temp)
        if len(self._readings_history) > self._max_history:
            self._readings_history.pop(0)
        return temp

    def get_temperature_trend(self):
        """check if temp is going up, down, or stable"""
        if len(self._readings_history) < 2:
            return None

        temp_min = min(self._readings_history)
        temp_max = max(self._readings_history)
        temp_avg = sum(self._readings_history) / len(self._readings_history)

        last_temp = self._readings_history[-1]
        if last_temp > temp_avg + 2:
            trend = "HEATING"
        elif last_temp < temp_avg - 2:
            trend = "COOLING"
        else:
            trend = "STABLE"

        return {
            "min_c": temp_min,
            "max_c": temp_max,
            "avg_c": temp_avg,
            "current_c": last_temp,
            "trend": trend
        }

    def is_overheating(self, threshold_c=60):
        """check if chip is too hot (ESP32 max is 85C)"""
        temp = self.get_temperature_c()
        return temp > threshold_c

    def calibrate(self, known_temp_c):
        """calibrate against a known temp (e.g. from external thermometer)
        example: if actual is 30C but sensor reads 13C, call calibrate(30.0)"""
        raw_readings = []
        for _ in range(10):
            raw_readings.append(self.get_raw_reading())
            utime.sleep_ms(50)
        avg_raw = sum(raw_readings) / len(raw_readings)

        # offset = known - raw
        self.offset = known_temp_c - avg_raw

        print(f"\n{'='*40}")
        print("Temp Sensor Calibration")
        print(f"{'='*40}")
        print(f"Raw: {avg_raw:.2f}")
        print(f"Actual: {known_temp_c:.2f}C")
        print(f"Offset: {self.offset:.2f}C")
        print(f"Calibrated: {self.get_temperature_c():.2f}C")
        print(f"{'='*40}\n")
