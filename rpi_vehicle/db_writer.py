from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Optional, Iterable, Any, Dict

import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool

def now_dt3() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

@dataclass
class TelemetrySample:
    ts: datetime

    # EMG/IMU
    emg_raw: float
    emg_filtered: float
    roll_deg: float
    pitch_deg: Optional[float] = None
    yaw_deg: Optional[float] = None

    # Gaze
    gaze_valid: bool = False
    gaze_x: Optional[float] = None
    gaze_y: Optional[float] = None
    gaze_dir: Optional[str] = None
    gaze_confidence: Optional[float] = None

    # Drowsy
    face_valid: bool = False
    ear: Optional[float] = None
    blink_rate: Optional[float] = None
    perclos: Optional[float] = None
    drowsy_score: Optional[float] = None
    drowsy_state: Optional[str] = None

    # Command
    throttle: float = 0.0
    steer_raw: float = 0.0
    steer_assisted: float = 0.0
    mode: str = "STOP"

    # Vehicle feedback
    motor_pwm_left: Optional[int] = None
    motor_pwm_right: Optional[int] = None
    battery_v: Optional[float] = None

class MySQLWriter:
    """
    - sessions 시작 및 종료
    - telemetry_samples 배치 insert
    - events 기록
    """
    def __init__(
            self,
            host: str,
            port: int,
            user: str,
            password: str,
            database: str,
            pool_name: str = "emgpool",
            pool_size: int = 5,
    ):
        self.pool=MySQLConnectionPool(
            pool_name=pool_name,
            pool_size=pool_size,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            autocommit=False
        )
    
    def _conn(self):
        return self.pool.get_connection()
    
    # ---------- Session -------------
    def start_session(
            self,
            user_id: int,
            profile_id: int,
            controller_device_id: Optional[int] = None,
            vehicle_device_id: Optional[int] = None,
            camera_device_id: Optional[int] = None,
            buzzer_device_id: Optional[int] = None,
            note: str = "",
            app_version: Optional[str] = None,
            vehicle_sw_version: Optional[str] = None,
            vision_sw_version: Optional[str] = None,
            algo_version: Optional[str] = None,
            started_at: Optional[datetime] = None,
    ) -> int:
        started_at = started_at or now_dt3()

        sql = """
        INSERT INTO sessions(
          user_id, profile_id,
          controller_device_id, vehicle_device_id, camera_device_id, buzzer_device_id,
          started_at, note,
          app_version, vehicle_sw_version, vision_sw_version, algo_version
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """

        params = (
            user_id,profile_id,
            controller_device_id, vehicle_device_id, camera_device_id, buzzer_device_id,
            started_at, note,
            app_version, vehicle_sw_version, vision_sw_version, algo_version
        )

        conn =  self._conn()
        try:
            cur = conn.cursor()
            cur.execute(sql,params)
            session_id = cur.lastrowid

            # Session_start 이벤트
            self._insert_event(cur, session_id, started_at, "SESSION_START", note or "")

            conn.commit()
            cur.close()
            return int(session_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def end_session(self,session_id: int, note: str = "") -> None:
        ended_at = now_dt3()

        conn = self._conn()
        try:
            cur = conn.cursor()

            cur.execute(
                "UPDATE sessinos SET ended_at=%s, note=COALESCE(note,'') WHERE session_id=%s",
                (ended_at, session_id)
            )

            self._insert_event(cur, session_id, ended_at, "SESSION_END", note)

            conn.commit()
            cur.close()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------ Events -------
    def log_event(self, session_id: int, event_type: str, detail: str="", ts: Optional[datetime] = None) -> None:
        ts = ts or now_dt3()
        conn = self._conn()
        try:
            cur = conn.cursor()
            self._insert_event(cur,session_id, ts, event_type, detail)
            conn.commit()
            cur.close()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _insert_event(self, cur, session_id: int, ts: datetime, event_type: str, detail: str) -> None:
        cur.execute(
            "INSERT INTO events(session_id, ts, event_type, detail) VALUES (%s,%s,%s,%s)",
            (session_id,ts,event_type,detail[:500] if detail else None),
        )
    
    def insert_telemetry_batch(self,session_id: int, samples: List[TelemetrySample]) -> None:
        if not samples:
            return
        
        sql = """
        INSERT INTO telemetry_samples(
            session_id, ts,
            emg_raw, emg_filtered, roll_deg, pitch_deg, yaw_deg,
            gaze_valid, gaze_x, gaze_y, gaze_dir, gaze_confidence,
            face_valid, ear, blink_rate, perclos, drowsy_score, drowsy_state,
            throttle, steer_raw, steer_assisted, mode,
            motor_pwm_left, motor_pwm_right, battery_v
        )
        VALUES(
            %s,%s,
            %s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,
            %s,%s,%s
        )
        """
        rows=[]
        for s in samples:
            rows.append((
                session_id, s.ts,

                s.emg_raw, s.emg_filtered, s.roll_deg, s.pitch_deg, s.yaw_deg,
                1 if s.gaze_valid else 0, s.gaze_x, s.gaze_y, s.gaze_dir, s.gaze_confidence,
                1 if s.face_valid else 0, s.ear, s.blink_rate, s.perclos, s.drowsy_score, s.drowsy_state,
                s.throttle,s.steer_raw,s.steer_assisted,s.mode,
                s.motor_pwm_left,s.motor_pwm_right,s.battery_v
            ))
        
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.executemany(sql,rows)
            conn.commit()
            cur.close()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()