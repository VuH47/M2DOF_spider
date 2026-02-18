# HC-SR04 ultrasonic distance sensor driver
# measures distance using sound waves

from machine import Pin
import utime


class Ultrasonic:
    """HC-SR04 ultrasonic sensor for distance measurement
    sends a sound pulse, measures echo time, calculates distance"""

    def __init__(self, trigger_pin, echo_pin, timeout_us=30000):
        self.trigger = Pin(trigger_pin, Pin.OUT)
        self.echo = Pin(echo_pin, Pin.IN)
        self.timeout_us = timeout_us
        self.trigger.off()

    def get_distance(self):
        """get distance in cm (-1 if no echo/timeout)"""
        # send 10us trigger pulse
        self.trigger.off()
        utime.sleep_us(2)
        self.trigger.on()
        utime.sleep_us(10)
        self.trigger.off()

        # wait for echo to go high
        start_wait = utime.ticks_us()
        while self.echo.value() == 0:
            if utime.ticks_diff(utime.ticks_us(), start_wait) > self.timeout_us:
                return -1  # timeout waiting for echo start

        # measure how long echo stays high
        pulse_start = utime.ticks_us()
        while self.echo.value() == 1:
            if utime.ticks_diff(utime.ticks_us(), pulse_start) > self.timeout_us:
                return -1  # timeout waiting for echo end

        pulse_duration = utime.ticks_diff(utime.ticks_us(), pulse_start)

        # speed of sound = 343m/s = 0.0343 cm/us
        # divide by 2 because sound goes there and back
        distance_cm = (pulse_duration * 0.0343) / 2

        return distance_cm

    def get_distance_averaged(self, samples=3):
        """average multiple readings for stability"""
        readings = []
        for _ in range(samples):
            d = self.get_distance()
            if d > 0:
                readings.append(d)
            utime.sleep_ms(30)  # small delay between pings

        if len(readings) == 0:
            return -1
        return sum(readings) / len(readings)

    def is_obstacle(self, threshold_cm=20):
        """check if something is closer than threshold"""
        distance = self.get_distance()
        if distance < 0:
            return False  # no reading = no obstacle (probably)
        return distance < threshold_cm


# bonus: hall sensor heading (for compass-like stuff)
def get_heading():
    """read ESP32 hall sensor - gives magnetic field strength
    not a real compass but can detect magnets nearby"""
    import esp32
    return esp32.hall_sensor()
