"""
ESP-NOW Slave for MicroPython
works with ESP-IDF C/C++ master on ESP32-S3

supports two modes:
1. JSON mode: {"type": "command", "command": "forward", ...}
2. simple string mode: "UP", "DOWN", "RANGE:123cm", etc
"""

import network
import espnow as esp_now_module
import utime
import json
import ubinascii

# commands the master can send as plain strings
SIMPLE_COMMANDS = [
    "UP", "DOWN", "LEFT", "RIGHT", "STOP",
    "HELLO", "SCAN", "MOONWALK", "TEST",
    "FORWARD", "BACKWARD", "HOME", "STAND",
    "SPM",   # far from home routine
    "TROT"   # trot gait
]


class ESPNowSlaveCompatible:
    """ESP-NOW slave that handles both JSON and simple string commands
    auto-ACKs simple commands and maps them to robot actions"""

    def __init__(self, master_mac=None, channel=1, auto_ack=True):
        self.master_mac_str = master_mac
        self.master_mac_bytes = self._parse_mac(master_mac) if master_mac else None
        self.channel = channel
        self.auto_ack = auto_ack
        self.esp_now = None
        self.sta = None
        self.own_mac = None

        # stats
        self.send_count = 0
        self.recv_count = 0
        self.send_errors = 0
        self.recv_errors = 0

        self.command_callback = None

    def _parse_mac(self, mac_str):
        """convert MAC string to bytes"""
        if isinstance(mac_str, bytes):
            return mac_str
        mac_str = mac_str.replace(':', '').replace('-', '').replace(' ', '')
        return ubinascii.unhexlify(mac_str)

    def init(self):
        """setup ESP-NOW"""
        try:
            self.sta = network.WLAN(network.STA_IF)
            self.sta.active(True)
            self.sta.disconnect()  # important: must disconnect for espnow to work

            self.own_mac = self.sta.config('mac')
            mac_str = ubinascii.hexlify(self.own_mac, ':').decode()

            print(f"ESP-NOW Slave init")
            print(f"MAC: {mac_str}")
            print(f"Channel: {self.channel}")

            self.esp_now = esp_now_module.ESPNow()
            self.esp_now.active(True)

            if self.master_mac_bytes:
                self.esp_now.add_peer(self.master_mac_bytes)
                print(f"Master: {self.master_mac_str}")
            else:
                print("Broadcast mode")

            print("ESP-NOW ready\n")
            return True

        except Exception as e:
            print(f"ESP-NOW init failed: {e}")
            return False

    def set_command_callback(self, callback):
        """callback signature: callback(command_str, params_dict)"""
        self.command_callback = callback

    def send_sensor_data(self, distance=None, temperature=None, status="OK"):
        """send sensor readings as JSON"""
        data = {
            "type": "sensor_data",
            "distance": distance if distance is not None else -1.0,
            "temperature": temperature if temperature is not None else 0.0,
            "status": status,
            "timestamp": utime.ticks_ms(),
            "count": self.send_count
        }
        return self._send_json(data)

    def send_response(self, result=None, error=None):
        data = {
            "type": "response",
            "result": result,
            "error": error,
            "timestamp": utime.ticks_ms()
        }
        return self._send_json(data)

    def send_alert(self, alert_type, message):
        data = {
            "type": "alert",
            "alert_type": alert_type,
            "message": message,
            "timestamp": utime.ticks_ms()
        }
        return self._send_json(data)

    # --- simple string methods (for ESP-IDF C master) ---

    def send_simple_string(self, message):
        """send raw string (e.g. "ACK", "RANGE:123cm")"""
        try:
            msg_bytes = message.encode('utf-8')
            if len(msg_bytes) > 250:
                print(f"Warning: msg too big ({len(msg_bytes)} bytes)")
                return False

            if self.master_mac_bytes:
                self.esp_now.send(self.master_mac_bytes, msg_bytes)
            else:
                self.esp_now.send(None, msg_bytes)

            self.send_count += 1
            return True
        except Exception as e:
            self.send_errors += 1
            print(f"Send error: {e}")
            return False

    def send_range(self, distance_cm):
        """send distance as simple string (e.g. RANGE:45cm)"""
        try:
            if distance_cm < 0:
                message = "RANGE:ERROR"
            elif distance_cm < 100:
                message = f"RANGE:{int(distance_cm)}cm"
            else:
                distance_m = distance_cm / 100.0
                message = f"RANGE:{distance_m:.2f}m"
            return self.send_simple_string(message)
        except Exception as e:
            print(f"Range send error: {e}")
            return False

    def send_temperature(self, temp_celsius):
        """send temp as simple string (e.g. TEMP:25.5C)"""
        try:
            if temp_celsius is None or temp_celsius < -50 or temp_celsius > 150:
                message = "TEMP:ERROR"
            else:
                message = f"TEMP:{temp_celsius:.1f}C"
            return self.send_simple_string(message)
        except Exception as e:
            print(f"Temp send error: {e}")
            return False

    def send_ack(self, command=None):
        """send ACK (or ACK:command)"""
        try:
            if command:
                message = f"ACK:{command}"
            else:
                message = "ACK"
            return self.send_simple_string(message)
        except Exception as e:
            print(f"ACK send error: {e}")
            return False

    def _send_json(self, data):
        """send dict as JSON via ESP-NOW"""
        try:
            json_str = json.dumps(data)
            message = json_str.encode('utf-8')

            if len(message) > 250:
                print(f"Warning: JSON too big ({len(message)} bytes)")
                return False

            if self.master_mac_bytes:
                self.esp_now.send(self.master_mac_bytes, message)
            else:
                self.esp_now.send(None, message)

            self.send_count += 1
            return True
        except Exception as e:
            self.send_errors += 1
            print(f"Send error: {e}")
            return False

    def _recv_with_rssi(self, timeout_ms):
        """try irecv() for RSSI, fallback to recv()"""
        try:
            if hasattr(self.esp_now, "irecv"):
                result = self.esp_now.irecv(timeout_ms)
                if result and len(result) >= 3:
                    return result[0], result[1], result[2]
                elif result and len(result) == 2:
                    return result[0], result[1], None
        except:
            pass

        result = self.esp_now.recv(timeout_ms)
        if result:
            return result[0], result[1], None
        return None, None, None

    def receive(self, timeout_ms=100):
        """receive and parse incoming data (JSON or simple string)"""
        try:
            host, msg, rssi = self._recv_with_rssi(timeout_ms)

            if host is None:
                return None, None

            sender_mac = ubinascii.hexlify(host, ':').decode()

            try:
                msg_str = msg.decode('utf-8').strip()
            except UnicodeDecodeError:
                self.recv_errors += 1
                print(f"Decode error")
                return sender_mac, {"type": "error", "raw": msg, "rssi": rssi}

            # try JSON first
            try:
                data = json.loads(msg_str)
                self.recv_count += 1

                # new format: {"cmd":"MOVE","dir":"UP","speed":75}
                if data.get("cmd") == "MOVE" and self.command_callback:
                    direction = data.get("dir", "STOP")
                    speed = data.get("speed", 75)
                    dir_map = {
                        "UP": "forward", "DOWN": "backward",
                        "LEFT": "turn_left", "RIGHT": "turn_right",
                        "STOP": "stand"
                    }
                    command = dir_map.get(direction, "stand")
                    self.command_callback(command, {"speed": speed})

                # old format: {"type":"command","command":"forward","params":{...}}
                elif data.get("type") == "command" and self.command_callback:
                    command = data.get("command")
                    params = data.get("params", {})
                    self.command_callback(command, params)

                if rssi is not None:
                    data["rssi"] = rssi
                return sender_mac, data

            except (ValueError, KeyError):
                # not JSON - treat as simple string command
                self.recv_count += 1
                command_upper = msg_str.upper()

                if command_upper in SIMPLE_COMMANDS:
                    if self.auto_ack:
                        self.send_ack(command_upper)

                    if self.command_callback:
                        command_map = {
                            "UP": "forward", "DOWN": "backward",
                            "LEFT": "turn_left", "RIGHT": "turn_right",
                            "STOP": "stand", "HELLO": "hello",
                            "SCAN": "scan", "MOONWALK": "moonwalk",
                            "FORWARD": "forward", "BACKWARD": "backward",
                            "HOME": "home", "STAND": "stand",
                            "TEST": "test", "SPM": "spm_far_from_home",
                            "TROT": "trot_walk"
                        }
                        mapped = command_map.get(command_upper, command_upper.lower())
                        self.command_callback(mapped, {})

                    return sender_mac, {
                        "type": "simple_command",
                        "command": command_upper,
                        "raw": msg_str,
                        "rssi": rssi
                    }
                else:
                    print(f"Unknown cmd: {msg_str}")
                    return sender_mac, {
                        "type": "unknown",
                        "raw": msg_str,
                        "rssi": rssi
                    }

        except Exception as e:
            self.recv_errors += 1
            print(f"Receive error: {e}")
            return None, None

    def get_stats(self):
        return {
            "send_count": self.send_count,
            "recv_count": self.recv_count,
            "send_errors": self.send_errors,
            "recv_errors": self.recv_errors,
            "success_rate": (self.send_count - self.send_errors) / self.send_count * 100 if self.send_count > 0 else 0
        }

    def deinit(self):
        if self.esp_now:
            self.esp_now.active(False)
            print("ESP-NOW off")

    def get_mac(self):
        if self.own_mac:
            return ubinascii.hexlify(self.own_mac, ':').decode()
        return None


def get_mac_address():
    """helper to get device MAC"""
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    mac = sta.config('mac')
    return ubinascii.hexlify(mac, ':').decode()


"""
command mapping reference:
  "UP"       -> "forward"      "DOWN"     -> "backward"
  "LEFT"     -> "turn_left"    "RIGHT"    -> "turn_right"
  "STOP"     -> "stand"        "HELLO"    -> "hello"
  "SCAN"     -> "scan"         "MOONWALK" -> "moonwalk"
  "FORWARD"  -> "forward"      "BACKWARD" -> "backward"
  "HOME"     -> "home"         "STAND"    -> "stand"
  "SPM"      -> "spm_far_from_home"
  "TROT"     -> "trot_walk"

simple string format examples:
  "RANGE:45cm"  "TEMP:25.5C"  "ACK:UP"
"""
