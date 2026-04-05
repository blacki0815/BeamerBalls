# 🎱 Beamer Balls — Interactive Physics Projection

An interactive real-time augmented reality installation that projects physics-simulated balls onto a wall. Physical sticky notes attached to the wall act as collision surfaces — the camera detects them and the balls bounce off them realistically.

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [How It Works — Technical Overview](#how-it-works--technical-overview)
3. [Hardware Requirements](#hardware-requirements)
4. [Software Requirements](#software-requirements)
5. [Project Structure](#project-structure)
6. [Installation](#installation)
7. [Setup & Calibration](#setup--calibration)
8. [Running the Project](#running-the-project)
9. [Configuration & Tuning](#configuration--tuning)
10. [Troubleshooting](#troubleshooting)
11. [Architecture Deep Dive](#architecture-deep-dive)

---

## What It Does

Beamer Balls turns any wall into an interactive physics playground:

- A **projector** displays white glowing balls on a dark wall
- The balls fall under **simulated gravity** and bounce realistically
- You stick **neon yellow sticky notes** anywhere on the wall
- A **camera** detects the sticky notes in real time
- The balls **collide and bounce off** the sticky notes as if they were physical ramps
- By arranging multiple sticky notes you can create elaborate tracks and courses

The result looks like glowing balls rolling and bouncing through obstacles you physically place on the wall with your hands — no touchscreen, no AR glasses, just a projector, a camera, and sticky notes.

---

## How It Works — Technical Overview

The system consists of four major components running simultaneously:

### 1. Color Detection (OpenCV)
The camera continuously films the wall. Each video frame goes through the following pipeline:

- **Color space conversion**: The frame is converted from BGR to HSV (Hue, Saturation, Value). HSV is far better suited for color detection than RGB because the actual color (H) is separated from brightness (V), making detection robust under varying lighting conditions.
- **Color masking**: `cv2.inRange()` creates a binary mask — pixels within the calibrated HSV range of neon yellow become white, everything else becomes black.
- **Morphological cleanup**: `MORPH_CLOSE` fills small holes within detected areas; `MORPH_OPEN` removes small noise specks outside them.
- **Contour detection**: `cv2.findContours()` finds connected white regions in the mask.
- **Rotated bounding box**: For each sufficiently large contour, `cv2.minAreaRect()` computes the smallest enclosing rectangle — crucially, this works even when the sticky note is tilted at an angle. `cv2.boxPoints()` returns the 4 exact corner coordinates.

### 2. Coordinate Transformation (Homography)
The camera and projector look at the wall from different positions and angles. A pixel at position (x, y) in the camera image does not correspond to the same position in the projector image. This offset causes balls to float above or miss sticky notes entirely if uncorrected.

The solution is a **homography matrix** — a 3×3 transformation matrix computed once during calibration. It encodes the full perspective transformation between the camera's view and the projector's coordinate system. At runtime, `cv2.perspectiveTransform()` maps every detected sticky note corner from camera coordinates to exact projector pixel coordinates, correcting for perspective, rotation, and lens offset in one step.

### 3. Physics Engine (Pymunk)
Pymunk is a Python wrapper around the Chipmunk 2D physics library written in C. It handles all collision detection and response.

- **Static segments**: The transformed sticky note corners are added to the physics space as `pymunk.Segment` objects — infinitely thin static lines with configurable elasticity and friction.
- **Dynamic bodies**: Each ball is a `pymunk.Body` with a `pymunk.Circle` shape. Bodies have mass and a moment of inertia computed via `pymunk.moment_for_circle()`.
- **Fixed timestep**: The physics simulation runs at a fixed internal rate of 120 steps per second, completely independent of the rendering framerate. A `physik_akkumulator` variable accumulates real elapsed time and calls `space.step(1/120)` as many times as needed per frame. This makes the physics deterministic and prevents inconsistent bounce behavior caused by frame rate spikes.
- **Elasticity multiplication**: In Pymunk, the effective elasticity of a collision is the product of both shapes' elasticity values. With the ball at `0.5` and the segment at `0.6`, the effective restitution is `0.30` — equivalent to a rubber ball bouncing on a hard surface.
- **Damping**: `space.damping = 0.98` applies a small global velocity damping each step, simulating air resistance and preventing balls from accelerating uncontrollably after glancing collisions.

### 4. Rendering (Pygame)
Pygame handles the visual output sent to the projector.

- A borderless window (`pygame.NOFRAME`) is positioned at the exact pixel offset where the projector monitor begins using `SDL_VIDEO_WINDOW_POS`.
- Every frame the entire screen is filled with pure black `(0, 0, 0)`. Because projectors work by emitting light, black pixels emit no light — only the drawn balls are visible on the wall.
- Balls are drawn as two overlapping white circles (outer + slightly smaller inner with a cool blue tint) to give them a glowing appearance on the dark wall.

### 5. Threading
Camera processing and physics/rendering run on separate threads to prevent either from blocking the other:

- The **camera thread** runs as fast as the camera allows (~30 fps), continuously updating the list of detected sticky note positions.
- The **main thread** runs the physics and rendering loop at 60 fps.
- A `threading.Lock` protects the shared sticky note list from simultaneous read/write access.
- Collision surfaces are updated every 0.5 seconds — frequent enough to react when notes are added or removed, without the overhead of rebuilding the physics space every frame.

### Data Flow Diagram

```
Camera Feed
    │
    ▼
HSV Color Filter
    │
    ▼
Contour Detection (cv2.findContours)
    │
    ▼
Rotated Bounding Box (cv2.minAreaRect)
    │
    ▼
Homography Transform (camera → projector coords)
    │
    ▼
Pymunk Static Segments (collision surfaces)
    │
    ◄──────────────────────────────────────────┐
    ▼                                          │
Ball Physics (gravity, collision response)     │
    │                                   0.5s update
    ▼                                          │
Pygame Rendering → Projector              Camera Thread
```

---

## Hardware Requirements

### Projector
Any projector with an HDMI input works. The project was developed with a **Panasonic PT-LW362** (WXGA, 1280×800, 3600 lumens).

Recommendations:
- **Resolution**: 1280×800 (WXGA) or 1920×1080 (Full HD). The simulation resolution matches the projector's native resolution.
- **Brightness**: At least 2000 lumens for dimly lit rooms, 3000+ lumens if you cannot fully darken the room. The darker the room, the more dramatic the effect.
- **Throw distance**: Standard throw projectors work fine. Short-throw projectors reduce shadows from people standing near the wall.
- **Connection**: HDMI to the computer. Use a USB-C to HDMI adapter if your laptop only has USB-C ports.

### Camera
Any camera that appears as a standard webcam device works. The project was developed using a **MacBook built-in FaceTime HD camera** for testing, with an **iPhone 7** as the target webcam via [Camo](https://reincubate.com/camo/).

Recommendations:
- **Resolution**: 720p (1280×720) is sufficient. Higher resolution doesn't improve detection quality significantly.
- **Position**: Mount the camera as close to the projector as possible, pointing at the same area of the wall. The closer they are, the simpler the homography transformation.
- **Stability**: The camera must not move after calibration. Any movement invalidates the homography and requires recalibration.
- **Frame rate**: 30 fps is sufficient for smooth sticky note tracking.

Good camera options:
- Built-in laptop webcam (simplest to start with)
- Logitech C920 / C922 (reliable, widely supported)
- iPhone via [Camo](https://reincubate.com/camo/) (USB, low latency)
- Any IP camera via RTSP/HTTP stream

### Computer
- **macOS**: Fully supported. Tested on MacBook Pro 14" M-series.
- **Windows / Linux**: Should work, but `SDL_VIDEO_WINDOW_POS` behavior for multi-monitor positioning may differ slightly.
- **Performance**: The simulation is not computationally demanding. Any modern laptop handles it at 60 fps.

### Sticky Notes
- **Color**: Use highly saturated neon colors. Neon yellow, neon pink, neon green all work well.
- **Size**: Standard 76×76mm sticky notes are ideal — large enough for the camera to detect reliably.
- **Contrast**: Avoid colors that are common in the environment (skin tones, white walls under warm light). Neon colors stand out well against neutral backgrounds.
- **One color at a time**: The current implementation detects one color. If you want to use multiple colors simultaneously, the HSV detection pipeline would need to be extended.

---

## Software Requirements

- **Python** 3.9 or higher
- **pygame** — window management and rendering
- **pymunk** — 2D physics engine
- **opencv-python** — camera capture and computer vision
- **numpy** — array operations (installed automatically with opencv)

---

## Installation

```bash
# Clone or download the project files into a folder
cd ~/Downloads   # or wherever your files are

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate   # macOS / Linux
# or on Windows: venv\Scripts\activate

# Install dependencies
pip install pygame pymunk opencv-python numpy
```

---

## Setup & Calibration

Calibration is a **one-time step** that must be redone only if the camera or projector is moved.

### Step 1 — Physical Setup

1. Mount the projector so it covers the desired area of the wall.
2. Mount the camera as close to the projector as possible, pointing at the same wall area.
3. Connect both to your computer.
4. Make sure the projector appears as a **second monitor** (not mirrored) in your display settings.
   - macOS: System Settings → Displays → select "Use as separate display"

### Step 2 — Set the Projector Offset

Open `beamer_balls.py` and set `BEAMER_OFFSET_X` to the width of your primary screen in points:

```python
BEAMER_OFFSET_X = 1512   # MacBook Pro 14" — adjust to your screen width
```

To find your screen width: System Settings → Displays → note the resolution of your primary display.

If the projector is to the **left** of your primary screen, use a negative value (e.g. `-1280`).

### Step 3 — Color Calibration

Run the color calibration tool to find the correct HSV values for your specific sticky notes under your specific lighting:

```bash
python3 kalibrierung.py
```

A window appears with two panels:
- **Left**: Live camera image with green boxes around detected sticky notes
- **Right**: The binary mask (white = detected color, black = ignored)

Adjust the 6 sliders until the sticky note appears solid white in the mask and everything else is black. Press `Q` when satisfied — the final HSV values are printed to the terminal.

Enter these values into `beamer_balls.py`:
```python
HSV_MIN = np.array([27,  34,  41])   # your values here
HSV_MAX = np.array([82, 224, 233])   # your values here
```

### Step 4 — Homography Calibration

This step calibrates the coordinate mapping between camera and projector. Run:

```bash
python3 homographie_kalibrierung.py
```

The projector displays 4 numbered colored circles on the wall. In the camera window, click each circle in order (1 → 2 → 3 → 4). The tool computes the homography matrix and saves it to `homographie.npy`. From this point on, `beamer_balls.py` loads this file automatically on startup.

The terminal prints a verification table showing how closely the computed points match the expected projector positions — errors below 10 pixels are excellent.

---

## Running the Project

```bash
# Make sure your virtual environment is active
source venv/bin/activate

# Start the simulation
python3 beamer_balls.py
```

**Controls:**
| Key | Action |
|-----|--------|
| `ESC` or `Q` | Quit |
| `D` | Toggle debug window on/off |

The debug window (toggle with `D`) shows the live camera feed with detected sticky notes outlined in green, ignored contours in red, and the binary color mask — useful for diagnosing detection problems.

---

## Configuration & Tuning

All key parameters are at the top of `beamer_balls.py`:

```python
# Ball appearance and behavior
BALL_RADIUS = 10          # Size of each ball in projector pixels
SPAWN_INTERVAL = 1.5      # Seconds between new balls spawning
GRAVITY = 500             # Downward acceleration (pixels/s²)

# Spawn positions — balls appear at these X coordinates in turn
SPAWN_POSITIONEN = [160, 320, 480, 640, 800, 960, 1120]

# Camera
KAMERA_INDEX = 0          # 0 = built-in, 1 = first external camera
ZOOM = 2.0                # Digital zoom (1.0 = no zoom, 2.0 = 2× crop)

# Color detection
HSV_MIN = np.array([27,  34,  41])   # From kalibrierung.py
HSV_MAX = np.array([82, 224, 233])   # From kalibrierung.py
MIN_ZETTEL_FLAECHE = 300  # Minimum contour area in pixels to count as a sticky note

# Collision offset — increase if balls float above notes, decrease if they sink in
ZETTEL_Y_OFFSET = 30
```

**Physics tuning:**

| Parameter | Effect |
|-----------|--------|
| `shape.elasticity` (ball) | How much energy the ball retains. `0.5` = moderate bounce |
| `segment elasticity` (note) | Combined with ball elasticity via multiplication |
| `space.damping` | `1.0` = no damping, `0.95` = noticeable slowdown |
| `GRAVITY` | Higher = faster fall, lower = floaty feel |

---

## Troubleshooting

**Balls float above sticky notes**
Increase `ZETTEL_Y_OFFSET` (try 40, 50, 60). This shifts the collision surface downward to match what the camera sees.

**Balls pass through sticky notes**
The sticky note may have been moved between camera updates. The collision surfaces refresh every 0.5 seconds. Also check that `MIN_ZETTEL_FLAECHE` isn't set too high — the note might be getting filtered out.

**Debug window shows red contours instead of green**
The detected area is below `MIN_ZETTEL_FLAECHE`. Either the camera is too far away (increase `ZOOM`), the lighting changed (re-run `kalibrierung.py`), or the HSV range needs adjustment.

**Camera not found / only index 0 works**
On macOS, virtual camera apps (Camo, iVCam) require a system extension to register as a real camera device. Go to System Settings → Privacy & Security → scroll down and allow the extension, then restart.

**Projector window appears on wrong screen**
Adjust `BEAMER_OFFSET_X` to match your primary display width. Check System Settings → Displays → Arrangement to see which side the projector is on.

**Bouncing is inconsistent**
This is caused by variable frame timing. Make sure the physics runs at fixed timestep — `PHYSIK_DT = 1/120` with the accumulator pattern. Do not replace `space.step(PHYSIK_DT)` with `space.step(dt)`.

**Color detection breaks when projector is on**
The projected white light from the balls can reflect off the wall and interfere with HSV detection. Increase `S_min` (saturation minimum) — white light has near-zero saturation while neon yellow has high saturation. A value of `S_min = 80` or higher usually separates them cleanly.

---

## Architecture Deep Dive

```
beamer_balls.py
│
├── Main Thread (60 fps)
│   ├── pygame event loop
│   ├── Read sticky note positions (thread-safe via Lock)
│   ├── Rebuild Pymunk segments every 0.5s
│   ├── Spawn new balls on interval
│   ├── space.step() with fixed timestep accumulator
│   ├── Render balls to screen (black background)
│   └── Show debug window if enabled
│
├── Camera Thread (daemon, ~30 fps)
│   ├── cv2.VideoCapture — raw frames
│   ├── Digital zoom (center crop + resize)
│   ├── BGR → HSV conversion
│   ├── cv2.inRange() color mask
│   ├── Morphological cleanup
│   ├── cv2.findContours()
│   ├── cv2.minAreaRect() per contour
│   └── Write results to shared list (thread-safe via Lock)
│
├── homographie.npy  (generated by homographie_kalibrierung.py)
│   └── 3×3 float32 matrix for cv2.perspectiveTransform()
│
└── kalibrierung.py  (standalone tool, run separately)
    └── Interactive HSV slider window → prints HSV_MIN / HSV_MAX
```

### Key Files

| File | Purpose |
|------|---------|
| `beamer_balls.py` | Main program — physics, rendering, camera integration |
| `kalibrierung.py` | One-time color calibration tool |
| `homographie_kalibrierung.py` | One-time projector↔camera coordinate calibration |
| `homographie.npy` | Saved homography matrix (auto-generated) |

---

## Credits & Libraries

- [Pygame](https://www.pygame.org/) — rendering and window management
- [Pymunk](http://www.pymunk.org/) — 2D physics (wrapper around [Chipmunk](https://chipmunk-physics.net/))
- [OpenCV](https://opencv.org/) — computer vision and camera capture
- [NumPy](https://numpy.org/) — numerical array operations
- [Camo by Reincubate](https://reincubate.com/camo/) — iPhone as webcam

---

*Built with Python · OpenCV · Pymunk · Pygame*
