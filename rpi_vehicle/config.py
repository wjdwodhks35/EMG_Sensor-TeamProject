from dataclasses import dataclass

@dataclass
class DBConfig:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = "YOUR_PASSWORD"
    database: str = "emg_rc"

@dataclass
class HardwareConfig:
    # Serial from controller (Arduino)
    serial_port: str = "/dev/ttyACM0"
    serial_baud: int = 115200

    # Camera
    camera_index: int = 0
    camera_width: int = 640
    camera_height: int = 480

    # Motor pins (BCM numbering) - EXAMPLE
    pwm_left_pin: int = 18
    dir_left_pin: int = 23
    pwm_right_pin: int = 19
    dir_right_pin: int = 24
    pwm_freq: int = 20000 # PWM 해상도

    # Buzzer pin
    buzzer_pin: int = 12

@dataclass
class ControlConfig:
    hz: int = 20
    controller_timeout_s: float = 0.35

    gaze_assist_weight: float = 0.35

    gaze_left_threshold: float = -0.4
    gaze_right_threshold: float = 0.4

    drowsy_score_threshold: float = 0.8

@dataclass
class SessionConfig:
    user_id: int = 1
    profile_id: int = 1
    controller_device_id: int | None=None
    vehicle_device_id: int | None=None
    camera_device_id: int | None=None
    buzzer_device_id: int | None=None

    vehicle_sw_version: str = "rpi-0.1.0"
    vision_sw_version: str = "vision-0.1.0"
    algo_version: str="fusion-0.1.0"