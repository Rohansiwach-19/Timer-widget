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
- **Third reference (target style for the expanded card):** a black rounded card with a horizontal **tick-mark ruler** across the top. Orange vertical ticks, taller ticks every 5 with small orange number labels above them (0, 5, 10, 15), a small orange triangle indicator under the current value, and ticks fading out toward the edges. Below it, a "Start Timer" pill button on the left and a large orange time (`5:00`) on the right. The home/music/image icon group in that screenshot belongs to a different app and must **not** be copied. The user wants to keep our existing round play/pause button instead of the "Start Timer" pill.

## 5. Visual design requirements

- **Surface:** solid `#000000` (or `#050505`), no gradient, no border, no glass or blur effect.
- **Shape:** fully rounded ends. Collapsed pill radius = height / 2. Expanded card radius about 28 px.
- **Shadow:** a soft drop shadow drawn manually (the window is translucent, so leave padding around the shape for it). Keep it subtle.
- **Typography:** Segoe UI Variable / Segoe UI. Use tabular (monospaced-digit) rendering for the time so digits do not jiggle while counting. Collapsed text is small; expanded time is large (about 40 px, semi-bold).
- **Accent:** default **orange** (`#FF9F0A`) to match the reference. Make it a single constant so it can be swapped (alternatives: white, or the old blue-purple gradient).
- **Ruler (expanded card):** orange ticks on black, major ticks taller with small orange labels, a small orange triangle indicator, soft fade at both edges. Large remaining time in the same orange. Play/pause button filled with the accent color, reset button in dark grey.
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
- Size about **300 × 150** card with rounded corners.
- Layout, top to bottom:
  1. **Tick ruler** (see 6.2.1) across the full width.
  2. Bottom row: round **play/pause** button and round **reset** button on the left, large **remaining time** on the right.
  3. Small, faint **close (X)** in the top-right corner, visible on hover only.
- **No preset buttons, no hrs/min input boxes, no Set button, no "FOCUS TIMER" header.**
- Click outside the window (focus lost), or starting the timer, collapses it back to the pill.
- While the timer is **running**, the ruler is hidden and the card shows only the time, controls and progress. The ruler is available when idle, paused or finished. Scrubbing while paused sets a new duration and resets the timer.

#### 6.2.1 Tick ruler (duration picker)
- Horizontal ruler like the third reference: orange ticks, taller major ticks with number labels above them, a fixed small triangle indicator marking the current value, and ticks fading out at both edges (gradient alpha mask).
- **Interaction:**
  - Drag left/right on the ruler to change the value. Dragging right increases time.
  - Mouse wheel scrolls it. Left/Right arrow keys step it when the window has focus.
  - Release with a small **inertia/fling** and a soft snap to the nearest tick.
  - Optional tick haptics: a very quiet click sound per tick (off by default, config flag).
- **Auto-zoom levels (this solves the "too much sliding to reach hours" problem).** The ruler's scale changes automatically with the current value, so long durations take one short swipe:
  | Range | Tick step | Labels |
  |---|---|---|
  | 1 – 30 min | 1 min | every 5 (`5`, `10`, `15`...) |
  | 30 min – 2 h | 5 min | every 30 min (`30m`, `1h`, `1h30`...) |
  | 2 h – 12 h | 15 min | every hour (`2h`, `3h`...) |
  Transitions between zoom levels must be smooth (cross-fade or scale), never a jump of the value.
- **Fast scrub:** holding **Shift** while dragging or using the wheel moves in 15-minute steps. Fast flings also speed up the movement.
- Minimum value 1 minute, maximum 12 hours (configurable).

#### 6.2.2 Typed entry (custom time)
- The big remaining time is **clickable, but must not look clickable** (no underline, no button styling). Only the cursor changes to a pointer on hover.
- Clicking it turns the time into an inline text field with a blinking caret. **Enter** confirms, **Esc** cancels, and clicking elsewhere confirms.
- It must accept natural input: `90` (minutes), `1h30`, `1:30` (h:mm), `2h`, `45m`, `1.5h`. Invalid or zero values are rejected with a brief shake and revert to the previous value.
- Small `h` and `m` hints may appear beside the field so it is clear that hours are supported.
- Confirming updates the ruler position and starts nothing by itself (the user presses play), unless config `TYPED_ENTRY_AUTOSTART = True`.

### 6.3 Transitions
- Expand/collapse animates **geometry** (width, height, and position so it stays anchored to its screen corner) over about 250–350 ms with easing.
- Content crossfades or scales during the morph. Avoid text flicker.
- Use **click to expand, not hover**. Hover-expand makes the window resize under the cursor and causes flicker loops.

### 6.4 Timer logic
- Default duration 25 minutes. Duration is set with the tick ruler or typed entry (section 6.2). It must be at least 1 minute and at most 12 hours.
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
DEFAULT_MIN = 25
MIN_MINUTES = 1
MAX_MINUTES = 12 * 60
TYPED_ENTRY_AUTOSTART = False
TICK_SOUND = False
COLLAPSED_SIZE = (200, 44)
EXPANDED_SIZE = (300, 150)
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
9. The tick ruler matches the third reference (orange ticks, labels, center triangle, edge fade), scrolls by drag, wheel and arrow keys, has inertia, and auto-zooms so 2 hours is reachable with one short swipe.
10. Clicking the time opens inline typed entry (looks non-clickable at rest) and parses `90`, `1h30`, `1:30`, `2h`, `45m`; Enter confirms, Esc cancels, invalid or zero values are rejected.
11. No preset buttons, hrs/min boxes or Set button exist anywhere in the UI.
10. Runs with only `pip install PySide6`.

## 10. Known pitfalls to handle

- Translucent windows need extra padding for the drop shadow, so size the window larger than the visible shape and paint the shape inset.
- Do not call `setGeometry` every frame manually. Use `QPropertyAnimation` on the `geometry` property (or `QVariantAnimation` driving position and size together).
- With `Qt.Tool`, the app may quit when the last window closes unexpectedly. Set `app.setQuitOnLastWindowClosed(True)` explicitly, or use a tray icon and manage quit yourself.
- Line edits inside a frameless window need `activateWindow()` / focus handling so typing works after a click.
- The ruler should be a custom-painted widget (`QPainter`), not a stock slider. Draw only the visible ticks, use a gradient alpha mask for the edge fade, and keep the value as a float "position" internally so inertia and zoom transitions stay smooth, snapping to a tick only on release.
- The inline typed-entry field should be a borderless `QLineEdit` styled to match the time text exactly, so tapping the time feels like editing in place rather than opening a form.
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
