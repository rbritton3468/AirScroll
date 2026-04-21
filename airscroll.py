from __future__ import annotations

import argparse
import collections
import os
import time
from dataclasses import dataclass
from pathlib import Path
import math
from typing import Deque, Optional

import cv2

CACHE_ROOT = Path(__file__).resolve().parent / ".cache"
MATPLOTLIB_CACHE = CACHE_ROOT / "matplotlib"
CACHE_ROOT.mkdir(exist_ok=True)
MATPLOTLIB_CACHE.mkdir(exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(MATPLOTLIB_CACHE))

try:
    import mediapipe as mp
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing dependency: mediapipe. Run `python3 -m pip install -r requirements.txt`."
    ) from exc

try:
    from pynput.keyboard import Controller, Key
except ModuleNotFoundError:
    Controller = None
    Key = None


mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles


@dataclass
class Sample:
    timestamp: float
    tip_x: float
    tip_y: float
    knuckle_x: float
    knuckle_y: float


@dataclass
class DetectionDebug:
    tip_travel_y: float = 0.0
    knuckle_travel_y: float = 0.0
    finger_lead_y: float = 0.0
    velocity_y: float = 0.0
    drift_x: float = 0.0
    index_extension: float = 0.0
    cooldown_remaining: float = 0.0


class FlickDetector:
    def __init__(
        self,
        history_seconds: float,
        min_tip_travel: float,
        min_finger_lead: float,
        min_velocity: float,
        max_horizontal_drift: float,
        cooldown_seconds: float,
    ) -> None:
        self.history_seconds = history_seconds
        self.min_tip_travel = min_tip_travel
        self.min_finger_lead = min_finger_lead
        self.min_velocity = min_velocity
        self.max_horizontal_drift = max_horizontal_drift
        self.cooldown_seconds = cooldown_seconds
        self.samples: Deque[Sample] = collections.deque()
        self.last_trigger_time = 0.0

    def update(
        self,
        now: float,
        tip_x: float,
        tip_y: float,
        knuckle_x: float,
        knuckle_y: float,
    ) -> tuple[bool, DetectionDebug]:
        debug = DetectionDebug()
        self.samples.append(Sample(now, tip_x, tip_y, knuckle_x, knuckle_y))

        while self.samples and now - self.samples[0].timestamp > self.history_seconds:
            self.samples.popleft()

        if len(self.samples) < 2:
            return False, debug

        end = self.samples[-1]
        peak = max(self.samples, key=lambda sample: sample.tip_y)
        dt = end.timestamp - peak.timestamp
        if dt <= 0:
            return False, debug

        debug.tip_travel_y = peak.tip_y - end.tip_y
        debug.knuckle_travel_y = peak.knuckle_y - end.knuckle_y
        debug.finger_lead_y = debug.tip_travel_y - debug.knuckle_travel_y
        debug.velocity_y = debug.finger_lead_y / dt
        peak_relative_x = peak.tip_x - peak.knuckle_x
        end_relative_x = end.tip_x - end.knuckle_x
        debug.drift_x = abs(end_relative_x - peak_relative_x)
        debug.cooldown_remaining = max(0.0, self.cooldown_seconds - (now - self.last_trigger_time))

        should_trigger = (
            debug.cooldown_remaining <= 0.0
            and debug.tip_travel_y >= self.min_tip_travel
            and debug.finger_lead_y >= self.min_finger_lead
            and debug.velocity_y >= self.min_velocity
            and debug.drift_x <= self.max_horizontal_drift
        )

        if should_trigger:
            self.last_trigger_time = now
            self.samples.clear()
            self.samples.append(end)
            debug.cooldown_remaining = self.cooldown_seconds
            return True, debug

        return False, debug


class DownKeyController:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.error: Optional[str] = None

        if not enabled:
            self.keyboard = None
            return

        if Controller is None or Key is None:
            raise SystemExit(
                "Missing dependency: pynput. Run `python3 -m pip install -r requirements.txt`."
            )

        self.keyboard = Controller()

    def press_down(self) -> bool:
        if not self.enabled or self.keyboard is None:
            return False

        try:
            self.keyboard.press(Key.down)
            self.keyboard.release(Key.down)
            return True
        except Exception as exc:  # pragma: no cover - depends on OS accessibility permissions
            self.error = str(exc)
            return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track your index finger and press the Down Arrow when you swipe upward."
    )
    parser.add_argument("--camera-index", type=int, default=0, help="Webcam index to open.")
    parser.add_argument("--min-detection-confidence", type=float, default=0.6)
    parser.add_argument("--min-tracking-confidence", type=float, default=0.6)
    parser.add_argument("--history-seconds", type=float, default=0.3)
    parser.add_argument("--min-travel", type=float, default=0.065)
    parser.add_argument("--min-finger-lead", type=float, default=0.035)
    parser.add_argument("--min-velocity", type=float, default=0.22)
    parser.add_argument("--min-index-extension", type=float, default=0.45)
    parser.add_argument("--max-horizontal-drift", type=float, default=0.2)
    parser.add_argument("--cooldown-seconds", type=float, default=0.9)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect the flick and show it on screen without sending a keyboard event.",
    )
    return parser


def point_distance(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def compute_index_extension(landmarks) -> float:
    index_tip = landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP]
    index_pip = landmarks[mp_hands.HandLandmark.INDEX_FINGER_PIP]
    index_mcp = landmarks[mp_hands.HandLandmark.INDEX_FINGER_MCP]
    wrist = landmarks[mp_hands.HandLandmark.WRIST]
    middle_mcp = landmarks[mp_hands.HandLandmark.MIDDLE_FINGER_MCP]

    palm_scale = max(point_distance(wrist, middle_mcp), 1e-6)
    extension_amount = point_distance(index_tip, index_mcp) - point_distance(index_pip, index_mcp)
    return extension_amount / palm_scale


def draw_status(
    frame,
    debug: DetectionDebug,
    trigger_count: int,
    dry_run: bool,
    key_error: Optional[str],
    last_fired_at: float,
    hand_visible: bool,
    index_ready: bool,
) -> None:
    lines = [
        "Press q to quit",
        f"Mode: {'dry-run' if dry_run else 'send Down Arrow'}",
        f"Tracking: {'hand found' if hand_visible else 'show your hand'}",
        f"Index: {'extended' if index_ready else 'extend index finger'}",
        f"Triggers: {trigger_count}",
        f"Tip travel: {debug.tip_travel_y:.3f}",
        f"Knuckle travel: {debug.knuckle_travel_y:.3f}",
        f"Finger lead: {debug.finger_lead_y:.3f}",
        f"Lead velocity: {debug.velocity_y:.3f}",
        f"Index extension: {debug.index_extension:.3f}",
        f"Drift X: {debug.drift_x:.3f}",
        f"Cooldown: {debug.cooldown_remaining:.2f}s",
    ]

    if last_fired_at > 0:
        lines.append(f"Last trigger: {time.strftime('%H:%M:%S', time.localtime(last_fired_at))}")

    if key_error:
        lines.append(f"Keypress error: {key_error[:50]}")

    for index, line in enumerate(lines):
        y = 28 + (index * 26)
        cv2.putText(
            frame,
            line,
            (16, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.63,
            (0, 255, 180),
            2,
            cv2.LINE_AA,
        )


def main() -> int:
    args = build_parser().parse_args()

    cap = cv2.VideoCapture(args.camera_index)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera index {args.camera_index}.")

    detector = FlickDetector(
        history_seconds=args.history_seconds,
        min_tip_travel=args.min_travel,
        min_finger_lead=args.min_finger_lead,
        min_velocity=args.min_velocity,
        max_horizontal_drift=args.max_horizontal_drift,
        cooldown_seconds=args.cooldown_seconds,
    )
    key_controller = DownKeyController(enabled=not args.dry_run)
    trigger_count = 0
    last_fired_at = 0.0

    with mp_hands.Hands(
        model_complexity=0,
        max_num_hands=1,
        min_detection_confidence=args.min_detection_confidence,
        min_tracking_confidence=args.min_tracking_confidence,
    ) as hands:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb_frame)
            debug = DetectionDebug()
            hand_visible = False
            index_ready = False

            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]
                landmarks = hand_landmarks.landmark
                hand_visible = True
                index_tip = landmarks[mp_hands.HandLandmark.INDEX_FINGER_TIP]
                index_mcp = landmarks[mp_hands.HandLandmark.INDEX_FINGER_MCP]
                index_extension = compute_index_extension(landmarks)
                debug.index_extension = index_extension
                index_ready = index_extension >= args.min_index_extension

                if index_ready:
                    now = time.monotonic()
                    triggered, motion_debug = detector.update(
                        now,
                        tip_x=index_tip.x,
                        tip_y=index_tip.y,
                        knuckle_x=index_mcp.x,
                        knuckle_y=index_mcp.y,
                    )
                    motion_debug.index_extension = index_extension
                    debug = motion_debug

                    if triggered:
                        key_controller.press_down()
                        trigger_count += 1
                        last_fired_at = time.time()
                else:
                    detector.samples.clear()

                tip_x = int(index_tip.x * frame.shape[1])
                tip_y = int(index_tip.y * frame.shape[0])
                tip_color = (0, 220, 120) if index_ready else (0, 140, 255)
                cv2.circle(frame, (tip_x, tip_y), 14, tip_color, -1)

                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style(),
                )
            else:
                detector.samples.clear()

            draw_status(
                frame=frame,
                debug=debug,
                trigger_count=trigger_count,
                dry_run=args.dry_run,
                key_error=key_controller.error,
                last_fired_at=last_fired_at,
                hand_visible=hand_visible,
                index_ready=index_ready,
            )

            cv2.imshow("AirScroll", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
