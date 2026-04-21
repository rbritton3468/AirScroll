# AirScroll

AirScroll watches your index finger through the webcam and presses the Down Arrow when you swipe upward, like scrolling on a phone.

## How it works

- MediaPipe Hands tracks a single hand in real time.
- The program tracks your index fingertip relative to the base knuckle of that same finger.
- It does not require the "one index finger only" pose anymore, but it does require the index finger to be extended.
- It only triggers when the fingertip moves upward more than the knuckle, which helps reject whole-hand lifts.
- A cooldown prevents the gesture from firing multiple times from the same flick.

## Setup

1. Create and activate a virtual environment if you want one:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

3. On macOS, grant Accessibility permission to the terminal or Python app you use to run this. Without that, the program can detect the flick but cannot send the Down Arrow key.

## Run

Start in dry-run mode first so you can tune the gesture without sending keypresses:

```bash
python3 airscroll.py --dry-run
```

When the overlay looks stable, run the real version:

```bash
python3 airscroll.py
```

Press `q` to quit.

Swipe your index finger upward in the camera view. The fingertip dot turns green when the index finger is extended enough to arm the detector.

## Tuning

If it fires too easily, raise one or more of these:

```bash
python3 airscroll.py --min-travel 0.08 --min-finger-lead 0.05 --min-index-extension 0.55 --min-velocity 0.3 --max-horizontal-drift 0.16 --cooldown-seconds 0.75
```

If it misses your flicks, lower one or more of these:

```bash
python3 airscroll.py --min-travel 0.05 --min-finger-lead 0.02 --min-index-extension 0.35 --min-velocity 0.16 --max-horizontal-drift 0.28
```

Useful flags:

- `--camera-index 1` to switch webcams
- `--dry-run` to disable keyboard events
- `--min-finger-lead` to require the fingertip to move more than the knuckle
- `--min-index-extension` to require the index finger to be extended before a swipe can trigger
- `--max-horizontal-drift` to allow more or less sideways motion during the swipe
- `--history-seconds` to change how much recent fingertip motion is considered part of one swipe
