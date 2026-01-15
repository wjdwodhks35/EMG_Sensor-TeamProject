from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import time

import cv2

@dataclass(frozen=True)
class GazeResult:
    ts: float
    valid: bool
    gaze_x: float | None=None
    gaze_y: float | None=None
    gaze_dir: str | None=None
    confidence: float | None=None

@dataclass(frozen=True)
class DrowsyResult:
    ts: float
    face_valid: bool
    ear: float | None=None
    perclos: float | None=None
    drowsy_score: float | None=None
    state: str | None=None

class VisionPipeLine:
    def __init__(self, cam_index: int, width: int, height: int):
        self.cap = cv2.VideoCapture(cam_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        self._last_frame_ts = time.time()
    
    def read_and_process(self) -> tuple[GazeResult, DrowsyResult]:
        """
        - 프레임 읽기
        - 시선 추출
        - 계산
        """
        ts = time.time()
        ok,frame = self.cap.read()
        if not ok:
            # 카메라 실패 -> invalid
            return (
                GazeResult(ts=ts, valid=False),
                DrowsyResult(ts=ts, face_valid=False, drowsy_score=None, state=None),
            )
        
        gaze = GazeResult(ts=ts, valid=True, gaze_x=0.0, gaze_y=0.0, gaze_dir="CENTER", confidence=0.8)
        drowsy = DrowsyResult(ts=ts,face_valid=True, ear=0.25,perclos=0.1, drowsy_score=0.2, state="NORMAL")

        return gaze, drowsy
    
    def close(self):
        try:
            self.cap.release()
        except Exception:
            pass