# main_rpi.py
from __future__ import annotations
import time
from datetime import datetime

from config import DBConfig, HardwareConfig, ControlConfig, SessionConfig
from controller_serial import SerialControllerReader
from vision import VisionPipeLine
from fusion import FusionEngine, FusionConfig
from motor_driver import DifferentialDrive, MotorPins
from buzzer import BuzzerController

from db_writer import MySQLWriter, TelemetrySample, now_dt3


def main():
    dbcfg = DBConfig()
    hw = HardwareConfig()
    ccfg = ControlConfig()
    scfg = SessionConfig()

    # --- DB ---
    writer = MySQLWriter(
        host=dbcfg.host,
        port=dbcfg.port,
        user=dbcfg.user,
        password=dbcfg.password,
        database=dbcfg.database,
        pool_size=5,
    )

    session_id = writer.start_session(
        user_id=scfg.user_id,
        profile_id=scfg.profile_id,
        controller_device_id=scfg.controller_device_id,
        vehicle_device_id=scfg.vehicle_device_id,
        camera_device_id=scfg.camera_device_id,
        buzzer_device_id=scfg.buzzer_device_id,
        note="rpi run",
        vehicle_sw_version=scfg.vehicle_sw_version,
        vision_sw_version=scfg.vision_sw_version,
        algo_version=scfg.algo_version,
    )

    # --- Controller input ---
    ctrl = SerialControllerReader(hw.serial_port, hw.serial_baud)

    # --- Vision ---
    vision = VisionPipeline(hw.camera_index, hw.camera_width, hw.camera_height)

    # --- Fusion ---
    fcfg = FusionConfig(
        gaze_assist_weight=ccfg.gaze_assist_weight,
        gaze_left_threshold=ccfg.gaze_left_threshold,
        gaze_right_threshold=ccfg.gaze_right_threshold,
        # 아래 emg_th_on/emg_mvc는 실제로는 DB의 profile에서 읽어 적용하는 게 정석
        emg_th_on=160.0,
        emg_mvc=340.0,
    )
    fusion = FusionEngine(fcfg)

    # --- Motors ---
    motors = DifferentialDrive(MotorPins(
        pwm_left=hw.pwm_left_pin,
        dir_left=hw.dir_left_pin,
        pwm_right=hw.pwm_right_pin,
        dir_right=hw.dir_right_pin
    ))

    # --- Buzzer ---
    buzzer = BuzzerController(hw.buzzer_pin)

    # --- loop configs ---
    hz = ccfg.hz
    dt = 1.0 / hz
    batch = []
    batch_size = hz  # 1초에 1번 DB insert (20Hz면 20개)

    last_mode = None
    drowsy_active = False
    connection_lost = False

    writer.log_event(session_id, "CALIBRATION_APPLIED", "using profile defaults")

    print("RPI vehicle main started. Ctrl+C to stop.")
    try:
        while True:
            loop_start = time.time()

            # 1) read controller
            frame = ctrl.read_latest()

            # timeout -> safety stop
            timed_out = ctrl.is_timed_out(ccfg.controller_timeout_s)
            if timed_out and not connection_lost:
                connection_lost = True
                writer.log_event(session_id, "CONNECTION_LOST", "controller timeout")
            elif (not timed_out) and connection_lost:
                connection_lost = False
                writer.log_event(session_id, "CONNECTION_RESTORED", "controller back")

            # 2) vision process
            gaze, drowsy = vision.read_and_process()

            # 3) fuse
            if timed_out or frame is None:
                throttle = 0.0
                steer_raw = 0.0
                steer_assisted = 0.0
                mode = "STOP"
                gaze_dir = gaze.gaze_dir if gaze.valid else None
            else:
                out = fusion.fuse(
                    emg_filtered=frame.emg_filtered,
                    roll_deg=frame.roll_deg,
                    gaze_x=gaze.gaze_x if gaze.valid else None
                )
                throttle, steer_raw, steer_assisted, mode, gaze_dir = (
                    out.throttle, out.steer_raw, out.steer_assisted, out.mode, out.gaze_dir
                )

            # 4) drowsy -> buzzer
            is_drowsy = (drowsy.drowsy_score is not None and drowsy.drowsy_score >= ccfg.drowsy_score_threshold) or (drowsy.state == "DROWSY")
            if is_drowsy and not drowsy_active:
                drowsy_active = True
                writer.log_event(session_id, "DROWSY_DETECTED", f"score={drowsy.drowsy_score}")
                writer.log_event(session_id, "BUZZER_ON", "pattern=BEEP_3_SHORT")
                buzzer.beep_pattern_3_short()
            elif (not is_drowsy) and drowsy_active:
                drowsy_active = False
                writer.log_event(session_id, "DROWSY_CLEARED", f"score={drowsy.drowsy_score}")
                writer.log_event(session_id, "BUZZER_OFF", "")

            # 5) motor control
            if mode == "STOP":
                motors.stop()
                pwmL, pwmR = 0, 0
            else:
                pwmL, pwmR = motors.set(throttle=throttle, steer=steer_assisted, reverse=False)

            # 6) events: mode change / gaze turns
            if last_mode is None:
                last_mode = mode
            if mode != last_mode:
                writer.log_event(session_id, "MODE_CHANGE", f"{last_mode}->{mode}")
                last_mode = mode

            if gaze_dir == "LEFT":
                writer.log_event(session_id, "GAZE_TURN_LEFT", f"x={gaze.gaze_x},conf={gaze.confidence}")
            elif gaze_dir == "RIGHT":
                writer.log_event(session_id, "GAZE_TURN_RIGHT", f"x={gaze.gaze_x},conf={gaze.confidence}")

            # 7) telemetry sample
            ts = now_dt3()
            if frame is None:
                emg_raw = 0.0
                emg_f = 0.0
                roll = 0.0
                pitch = None
            else:
                emg_raw = frame.emg_raw
                emg_f = frame.emg_filtered
                roll = frame.roll_deg
                pitch = frame.pitch_deg

            sample = TelemetrySample(
                ts=ts,
                emg_raw=float(emg_raw),
                emg_filtered=float(emg_f),
                roll_deg=float(roll),
                pitch_deg=float(pitch) if pitch is not None else None,

                gaze_valid=bool(gaze.valid),
                gaze_x=float(gaze.gaze_x) if (gaze.valid and gaze.gaze_x is not None) else None,
                gaze_y=float(gaze.gaze_y) if (gaze.valid and gaze.gaze_y is not None) else None,
                gaze_dir=gaze.gaze_dir if gaze.valid else None,
                gaze_confidence=float(gaze.confidence) if (gaze.valid and gaze.confidence is not None) else None,

                face_valid=bool(drowsy.face_valid),
                ear=float(drowsy.ear) if drowsy.ear is not None else None,
                perclos=float(drowsy.perclos) if drowsy.perclos is not None else None,
                drowsy_score=float(drowsy.drowsy_score) if drowsy.drowsy_score is not None else None,
                drowsy_state=drowsy.state,

                throttle=float(throttle),
                steer_raw=float(steer_raw),
                steer_assisted=float(steer_assisted),
                mode=mode,

                motor_pwm_left=int(pwmL),
                motor_pwm_right=int(pwmR),
                battery_v=None,
            )

            batch.append(sample)
            if len(batch) >= batch_size:
                writer.insert_telemetry_batch(session_id, batch)
                batch.clear()

            # loop sleep
            elapsed = time.time() - loop_start
            if elapsed < dt:
                time.sleep(dt - elapsed)

    except KeyboardInterrupt:
        print("\nStopping...")

    finally:
        # flush
        try:
            if batch:
                writer.insert_telemetry_batch(session_id, batch)
        except Exception:
            pass

        # ensure stop hardware
        try:
            motors.stop()
        except Exception:
            pass

        try:
            buzzer.off()
        except Exception:
            pass

        # end session
        try:
            writer.end_session(session_id, note="rpi stop")
        except Exception:
            pass

        ctrl.close()
        vision.close()
        motors.close()
        buzzer.close()

        print("Clean shutdown complete.")


if __name__ == "__main__":
    main()
