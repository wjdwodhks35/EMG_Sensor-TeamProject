from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo,min(hi,x))

@dataclass
class FusionConfig:
    imu_deadzone_deg: float = 3.0
    imu_max_angle_deg: float = 20.0
    imu_roll0_deg: float = 0.0
    imu_sensitivity: float = 1.0

    gaze_assist_weight: float = 0.35
    gaze_left_threshold: float = -0.4
    gaze_right_threshold: float = 0.4

    emg_th_on: float = 160.0
    emg_mvc: float = 340.0

@dataclass(frozen=True)
class ControlOut:
    throttle: float
    steer_raw: float
    steer_assisted: float
    mode: str # 'STOP'/'DRIVE'/'REVERSE'
    gaze_dir: str | None

class FusionEngine:
    def __init__(self, cfg: FusionConfig):
        self.cfg = cfg
    
    def roll_to_steer(self, roll_deg: float) -> float:
        x = (roll_deg - self.cfg.imu_roll0_deg) * self.cfg.imu_sensitivity
        if abs(x) < self.cfg.imu_deadzone_deg:
            return 0.0
        
        sign = 1.0 if x > 0 else -1.0
        x2 = abs(x) - self.cfg.imu_deadzone_deg
        span = max(1e-6, self.cfg.imu_max_angle_deg - self.cfg.imu_deadzone_deg)
        return sign * clamp(x2 / span, 0.0, 1.0)
    
    def gaze_to_steer_delta(self, gaze_x: Optional[float]) -> tuple[float, str | None]:
        if gaze_x is None:
            return 0.0, None
        if gaze_x <= self.cfg.gaze_left_threshold:
            return -self.cfg.gaze_assist_weight, "LEFT"
        if gaze_x >= self.cfg.gaze_right_threshold:
            return +self.cfg.gaze_assist_weight, "RIGHT"
        return 0.0, "CENTER"
    
    def fuse(self, emg_filtered: float, roll_deg: float, gaze_x: Optional[float]) -> ControlOut:
        throttle = self.emg_to_throttle(emg_filtered)
        steer_raw = self.roll_to_steer(roll_deg)

        delta, gaze_dir = self.gaze_to_steer_delta(gaze_x)
        steer_assisted = clamp(steer_raw + delta, -1.0, 1.0)

        mode = "DRIVE" if throttle > 0 else "STOP"
        return ControlOut(throttle, steer_raw, steer_assisted, mode, gaze_dir)