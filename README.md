# AirScroll

AirScroll watches your index finger through the webcam and presses the Down Arrow when you swipe upward, like scrolling on a phone.

## How it works

- MediaPipe Hands tracks a single hand in real time.
- The program tracks your index fingertip relative to the base knuckle of that same finger.
- It does not require the "one index finger only" pose anymore.
- It only triggers when the fingertip moves upward more than the knuckle, which helps reject whole-hand lifts.
- It can also require your other fingers to stay mostly still during the swipe.
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

Swipe your index finger upward in the camera view. The fingertip dot stays green whenever your hand is being tracked.

## Tuning

If it fires too easily, raise one or more of these:

```bash
python3 airscroll.py --min-travel 0.08 --min-finger-lead 0.05 --min-velocity 0.3 --max-horizontal-drift 0.16 --max-other-finger-motion 0.04 --cooldown-seconds 0.75
```

If it misses your flicks, lower one or more of these:

```bash
python3 airscroll.py --min-travel 0.05 --min-finger-lead 0.02 --min-velocity 0.16 --max-horizontal-drift 0.28 --max-other-finger-motion 0.09
```

Useful flags:

- `--camera-index 1` to switch webcams
- `--dry-run` to disable keyboard events
- `--min-finger-lead` to require the fingertip to move more than the knuckle
- `--max-horizontal-drift` to allow more or less sideways motion during the swipe
- `--max-other-finger-motion` to limit how much the middle, ring, and pinky can move during the swipe
- `--history-seconds` to change how much recent fingertip motion is considered part of one swipe
