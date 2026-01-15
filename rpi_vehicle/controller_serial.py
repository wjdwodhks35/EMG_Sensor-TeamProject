from __future__ import annotations
from dataclasses import dataclass
import json
import time
from typing import Optional, Tuple

import serial

@dataclass(frozen=True)
class ControllerFrame:
    ts: float
    emg_raw: float
    emg_filtered: float
    roll_deg: float
    pitch_deg: float | None = None

class SerialControllerReader:
    def __init__(self, port: str, baud: int):
        self.ser = serial.Serial(port, baudrate=baud, timeout=0.05)
        self.last_rx_ts: float | None=None
    
    def read_latest(self) -> Optional[ControllerFrame]:
        try:
            line = self.ser.readline()
            if not line:
                return None
            
            s = line.decode("utf-8", errors="ignore").strip()
            if not s:
                return None
            
            obj = json.loads(s)
            ts=float(obj.get("ts", time.time()))
            frame = ControllerFrame(
                ts=ts,
                emg_raw=float(obj["emg_raw"]),
                emg_filtered=float(obj.get("emg_filtered", obj["emg_raw"])),
                roll_deg=float(obj.get("roll", 0.0)),
                pitch_deg=float(obj.get("pitch",0.0)) if "pitch" in obj else None,
            )
            self.last_rx_ts = time.time()
            return frame
        except Exception:
            # 파싱 실패는 무시하고 진행
            return None
        
    def is_timed_out(self, timeout_s: float) -> bool:
        if self.last_rx_ts is None:
            return True
        return (time.time() - self.last_rx_ts) > timeout_s
        
    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass