# Project Brief: Dynamic Island-Style Floating Timer (PySide6)

## 1. Goal

Rebuild an existing always-on-top focus timer from scratch so it looks and behaves like the iOS **Dynamic Island**: a solid black capsule that stays small while the timer runs and expands into a fuller control card on click, with an animated morph between the two.

The existing prototype (`timer_v3.py`, pywebview + HTML/CSS) is only a reference for features. **Do not reuse its code or tech stack.**

## 2. Why a rewrite

- The prototype uses **pywebview**, which cannot do true per-pixel window transparency on Windows. Rounded corners always show a black/white box at the corners, and CSS cannot fix this because the OS window shape is what matters.
- pywebview resizes the OS window instantly, so a smooth expand/collapse animation is impossible.
- Conclusion: use a native toolkit where the window itself can be translucent and animated.

## 3. Tech stack (decided)

- **Python 3.10+**
- **PySide6 (Qt 6)**, installed with `pip install PySide6`
- Target platform: **Windows 10/11 only** (assumed, since this was not specified; keep platform-specific code isolated so macOS/Linux could be added later)
- No web view, no HTML/CSS, no Electron, no Tauri

Key Qt features to use:
- `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool` (the `Tool` flag keeps it out of the taskbar and Alt-Tab)
- `Qt.WA_TranslucentBackground` plus custom painting in `paintEvent` with `QPainter` (antialiased `drawRoundedRect`)
- `QPropertyAnimation` on window geometry (size and position) with an easing curve (`OutBack` or `OutCubic`) for the morph
- `QTimer` for the countdown tick
- Optional `QSystemTrayIcon` for quit/show

## 4. Reference

Screenshot provided by the user, with two apps side by side:

- **Left (target style):** a small pure-black pill, fully rounded ends. Orange label "Timer" on the left and the remaining time `1:15:42` on the right in the same orange. Tiny text, no borders, no gradient, no buttons visible.
- **Right (current prototype, to be replaced):** a rectangle with a dark purple/blue gradient, a "FOCUS TIMER" header, a settings arrow and an X, large `39:27`, a purple pause button and a reset button, and a gradient progress strip along the bottom edge. This is what the user wants to move away from.

## 5. Visual design requirements

- **Surface:** solid `#000000` (or `#050505`), no gradient, no border, no glass or blur effect.
- **Shape:** fully rounded ends. Collapsed pill radius = height / 2. Expanded card radius about 28 px.
- **Shadow:** a soft drop shadow drawn manually (the window is translucent, so leave padding around the shape for it). Keep it subtle.
- **Typography:** Segoe UI Variable / Segoe UI. Use tabular (monospaced-digit) rendering for the time so digits do not jiggle while counting. Collapsed text is small; expanded time is large (about 40 px, semi-bold).
- **Accent:** default **orange** (`#FF9F0A`) to match the reference. Make it a single constant so it can be swapped (alternatives: white, or the old blue-purple gradient).
- **Progress:** no bottom strip. Use one of these (make it configurable, default to the first):
  1. A thin progress arc/ring around the left dot in the collapsed pill, and a thin ring or arc in the expanded card.
  2. A subtle fill that shrinks along the pill's inner edge.
- **Done state:** the pill gently pulses or glows (orange or red) and plays a short beep. No harsh inset flash.
- **Unfocused "glass" effect from the old version: remove it.** It conflicts with the solid-black look.

## 6. States and behavior

### 6.1 Collapsed (default while running)
- Size about **200 × 44** (tune to fit the longest time `HH:MM:SS`).
- Left: small accent dot or a "Timer" label. Right: remaining time.
- Click (without dragging) expands it. Optionally show a tiny pause icon on hover.

### 6.2 Expanded (idle, paused, finished, or on click)
- Size about **260 × 150** card with rounded corners.
- Contents:
  - Large remaining time
  - Play/pause button and reset button (round)
  - Preset buttons: **5m, 15m, 25m, 50m** (25m selected by default)
  - Custom time inputs: **hours** and **minutes** plus a Set button (Enter key also confirms)
  - Close (X) button
- Click outside the window (focus lost), or starting the timer, collapses it back to the pill.

### 6.3 Transitions
- Expand/collapse animates **geometry** (width, height, and position so it stays anchored to its screen corner) over about 250–350 ms with easing.
- Content crossfades or scales during the morph. Avoid text flicker.
- Use **click to expand, not hover**. Hover-expand makes the window resize under the cursor and causes flicker loops.

### 6.4 Timer logic
- Presets: 5, 15, 25, 50 minutes. Default 25.
- Custom: hours + minutes (accept decimals; total must be greater than 0).
- Start/pause toggle. Reset returns to the last chosen duration and expands the card.
- Starting the timer auto-collapses to the pill. Finishing auto-expands and shows the done state.
- Use a **monotonic end timestamp** (`time.monotonic()`), not repeated decrements, so the time stays accurate if the system lags. Tick about every 250 ms.
- Show `MM:SS`, or `H:MM:SS` when an hour or more remains.
- Starting again after finishing restarts from the full duration.

### 6.5 Window behavior
- Always on top, frameless, not in the taskbar.
- **Draggable anywhere** by pressing and dragging. Distinguish a drag from a click with a small movement threshold (about 4 px), so a click expands and a drag moves.
- Anchored to a corner by default. Position computed with `QScreen.availableGeometry()`, which already excludes the taskbar (no hardcoded offsets).
- After the user drags it, remember the position for the session. Re-anchoring on resize should keep whichever edges are nearest the screen edge fixed.
- Handle high-DPI scaling and multi-monitor setups (use the screen the window is on).

## 7. Configuration

Constants at the top of the main file (or in a small `config.py`):

```python
CORNER = "bottom-right"      # top-left, top-right, bottom-left, bottom-right
MARGIN = 24
ACCENT = "#FF9F0A"
PRESETS_MIN = [5, 15, 25, 50]
DEFAULT_MIN = 25
COLLAPSED_SIZE = (200, 44)
EXPANDED_SIZE = (260, 150)
ANIM_MS = 300
PROGRESS_STYLE = "ring"      # "ring" or "fill"
```

## 8. Suggested structure

```
dynamic_island_timer/
├─ main.py            # app entry, window, state machine
├─ widgets.py         # painted pill/card, buttons, custom inputs
├─ timer_logic.py     # countdown model (no Qt UI code)
├─ config.py          # constants above
├─ requirements.txt   # PySide6
└─ README.md          # run and build instructions
```

A single-file version is acceptable if kept clean. Separate the timer model from the UI.

## 9. Acceptance criteria

1. Corners are truly rounded with **no black or white box** on Windows 10/11.
2. Collapsed state looks like a Dynamic Island pill (solid black, capsule shape, small orange text).
3. Expand/collapse **animates smoothly** with no flicker or jump.
4. Click expands, drag moves, and the two never get confused.
5. Timer is accurate, with correct `MM:SS` and `H:MM:SS` formats, and pause/resume/reset work.
6. Done state pulses and beeps, and the card expands automatically.
7. Stays always on top and does not appear in the taskbar.
8. Window anchors correctly to the chosen corner and clears the taskbar.
9. Custom hours/minutes input works, including Enter to confirm and rejecting zero or empty values.
10. Runs with only `pip install PySide6`.

## 10. Known pitfalls to handle

- Translucent windows need extra padding for the drop shadow, so size the window larger than the visible shape and paint the shape inset.
- Do not call `setGeometry` every frame manually. Use `QPropertyAnimation` on the `geometry` property (or `QVariantAnimation` driving position and size together).
- With `Qt.Tool`, the app may quit when the last window closes unexpectedly. Set `app.setQuitOnLastWindowClosed(True)` explicitly, or use a tray icon and manage quit yourself.
- Line edits inside a frameless window need `activateWindow()` / focus handling so typing works after a click.
- Disable spin-box arrows on the number inputs and style them to match the black theme.
- For the done sound use `winsound.Beep` (Windows) or `QSoundEffect` / `QApplication.beep()`. Keep it non-blocking.

## 11. Stretch goals (do not build unless asked)

- Global hotkey to start/pause
- System tray menu (show, quit, change corner)
- Session history or daily focus total
- Auto-start with Windows
- Packaging into a single `.exe` (PyInstaller)

## 12. Deliverables

- Working source code meeting the acceptance criteria
- `requirements.txt`
- Short `README.md` with run instructions and how to change the config
