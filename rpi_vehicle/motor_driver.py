from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from gpiozero import PWMOutputDevice, DigitalOutputDevice

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi,x))

@dataclass
class MotorPins:
    pwm_left: int
    dir_left: int
    pwm_right: int
    dir_right: int

class DifferentialDrive:
    def __init__(self, pins: MotorPins):
        self.pwmL = PWMOutputDevice(pins.pwm_left, frequency=20000, initial_value=0.0)
        self.dirL = DigitalOutputDevice(pins.dir_left, initial_value=False)

        self.pwmR = PWMOutputDevice(pins.pwm_right, frequency=20000, initial_value=0.0)
        self.dirR = DigitalOutputDevice(pins.dir_right, initial_value=False)

    def set(self, throttle: float, steer: float, reverse: bool = False) -> tuple[int,int]:
        throttle = clamp(throttle, 0.0, 1.0)
        steer = clamp(steer, -1.0, 1.0)

        left = throttle * (1.0 - steer)
        right = throttle * (1.0 + steer)

        left = clamp(left, 0.0, 1.0)
        right = clamp(right, 0.0, 1.0)

        self.dirL.value = reverse
        self.dirR.value = reverse

        self.pwmL.value = left
        self.pwmR.value = right

        return int(left * 255), int(right * 255)
    
    def stop(self):
        self.pwmL.value = 0.0
        self.pwmR.value = 0.0
    
    def close(self):
        self.stop()
        self.pwmL.close()
        self.pwmR.close()
        self.dirL.close()
        self.dirR.close()