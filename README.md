# ORVIX — Vision-Based Hand Gesture Desktop Automation System

Webcam → MediaPipe HandLandmarker → rule-based gesture recognition →
user-defined gesture→action mapping → Windows `.bat` execution.

## 1. Setup

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Get the hand_landmarker.task model (REQUIRED — fixes your current error)

Your `RuntimeError: Unable to get file size, errno=2` means MediaPipe can't
find the model file. This sandbox has no network access to Google's model
host, so you'll need to download it yourself on your machine:

1. Download the model:
   https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
2. Place it at exactly:
   ```
   GestureAutomation/hand/models/hand_landmarker.task
   ```
3. Verify it (PowerShell, from the project root):
   ```powershell
   Test-Path .\hand\models\hand_landmarker.task
   Get-Item .\hand\models\hand_landmarker.task | Select-Object FullName, Length
   ```
   Expect `True` and a non-zero length (the float16 model is a few MB).

`hand/detector.py` already validates this path with a clear
`FileNotFoundError` (including the exact expected path) if the file is
missing or empty, so you'll get a readable error instead of MediaPipe's
raw `errno=2` if something's still wrong.

## 3. Run it

```powershell
python main.py
```

This opens the ORVIX GUI. From there:

1. Click **+ Add Mapping**, pick a gesture, browse to a `.bat` file, save.
2. Click **Start Camera**.
3. Hold a configured gesture steady for ~0.6s — the mapped `.bat` runs once,
   then a 2s cooldown prevents repeat execution while you're still holding it.

## 4. Run the test suite

The gesture/mapping/executor tests are pure logic (no camera, no MediaPipe,
no Tkinter) and run anywhere:

```powershell
pytest tests/test_gesture.py tests/test_mapping.py tests/test_executor.py -v
```

`hand/detector.py` and `gui/app.py` require a real webcam / model file /
display and are meant to be exercised manually per the steps above.

## 5. Architecture

```
Webcam → Camera → HandDetector (MediaPipe Tasks) → GestureRecognizer
       → GestureState (stability + cooldown) → MappingManager (JSON)
       → Executor (.bat)
```

Strict separation, per the design principle: `gesture/recognizer.py` only
ever answers "what gesture is this?" — it never knows about `.bat` files.
All gesture→action knowledge lives in `mapping/manager.py` and
`config/mappings.json`.

## 6. Current status vs. spec

Implemented (V1, all 30 spec sections):

- Webcam capture (`camera/camera.py`)
- MediaPipe Tasks HandLandmarker, not the legacy `mp.solutions.hands` API
  (`hand/detector.py`)
- Four rule-based gestures: `V_SHAPE`, `THUMBS_UP`, `FIST`, `OPEN_PALM`
  (`gesture/recognizer.py`)
- JSON-backed, user-editable gesture→action mapping with add/edit/delete/
  enable-disable (`mapping/manager.py`)
- `.bat` execution with path/extension validation
  (`execution/executor.py`) — architecture supports adding `exe`, `url`,
  `powershell`, `python`, `command`, `hotkey` action types later by adding
  entries to `Executor._dispatch` only
- Stability (~0.6s hold) + cooldown (2s) state machine so a held gesture
  fires its action exactly once (`core/state.py`)
- Tkinter GUI: mapping table, add/edit/delete/toggle, start/stop camera,
  live preview with landmarks, current gesture + status
  (`gui/app.py`)
- Unit tests for recognizer, mapping manager, executor (`tests/`)

Not yet built (explicitly out of scope for V1 per spec sections 22–23):
dynamic/swipe gestures, ML-trained classifier, multi-user profiles,
app-specific/context-aware actions, voice input, execution history/
analytics, non-`.bat` action types.

## 7. Known tuning note

The thumb-up / thumb-down heuristic in `gesture/recognizer.py`
(`_thumb_up`) is the least geometrically stable of the four rules, since
the thumb doesn't fold like the other fingers. If you see `THUMBS_UP`
misfiring as `FIST` or vice versa for your hand/camera angle, adjust the
`0.02` and `1.15` thresholds in `_thumb_up` first — that's the intended
tuning point before considering a move to ML classification in V2.
