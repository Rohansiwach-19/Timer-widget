# Dynamic Island Floating Timer

A floating, always-on-top focus timer for Windows built from scratch with **Python & PySide6**, styled after the iOS **Dynamic Island**.

It stays as a compact, solid-black pill while your timer counts down and smoothly morphs into an expanded control card on click, with smooth geometry easing, corner anchoring, and true per-pixel rounded corners (no black/white background boxes).

---

## Features

- **iOS Dynamic Island Styling:** Solid black surface (`#000000`), truly rounded corners, and a subtle drop shadow drawn manually into translucent window padding.
- **Two Morphing States:**
  - **Collapsed (Running):** Minimal 200×44 pill displaying a thin progress ring with an accent dot, "Timer" label, and remaining time in tabular orange numbers.
  - **Expanded (Card):** 300×150 card featuring a horizontal tick ruler duration picker across the top, round play/pause and reset buttons on the left, an inline editable time display on the right, and a subtle hover-only close button.
- **Tick Ruler Duration Picker:** Custom-painted ruler with orange ticks, taller major ticks with number labels, center indicator triangle, edge gradient fade, auto-zoom (1m / 5m / 15m), dragging, mouse wheel, arrow keys, Shift fast scrub (15m), and inertia with soft snap on release.
- **Inline Typed Entry:** Click the large remaining time to edit in place. Parses natural expressions (`90`, `1h30`, `1:30`, `2h`, `45m`, `1.5h`), confirms on Enter / focus loss, cancels on Esc, and rejects invalid inputs with a brief shake.
- **Smooth Geometry Animation:** Morphs between states over 300 ms with `OutCubic` easing while staying anchored to the screen corner.
- **Accurate Countdown:** Powered by `time.monotonic()` end timestamp to prevent clock drift.
- **Smart Drag vs. Click:** Distinguishes a click from a drag with a 4 px movement threshold. Dragging moves the window; clicking expands it.
- **Done State Alert:** Gently pulses the capsule and plays a non-blocking chime when the timer finishes, automatically expanding the card.
- **Auto-Collapse / Focus Loss:** Starting the timer or clicking outside the window automatically collapses the card into the pill.

---

## Requirements

- Python 3.10+
- Windows 10 or 11
- `PySide6`

---

## Quick Start

1. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
   *(or `pip install PySide6`)*

2. Run the timer:
   ```powershell
   python main.py
   ```
   *(Or using the project's virtual environment directly: `.\.venv\Scripts\python.exe main.py`)*

To run silently without a console window:
```powershell
pythonw main.py
```
*(Or `.\.venv\Scripts\pythonw.exe main.py`)*

---

## Building a Windows Executable (`.exe`)

You can package Focus Timer into a standalone Windows application using [PyInstaller](https://pyinstaller.org/).

### Prerequisites & Important Troubleshooting

1. **Virtual Environment PATH Issue (`pyinstaller : The term is not recognized...`):**
   If `pyinstaller` was installed inside the virtual environment (`.venv`), Windows PowerShell won't find it globally. You should either:
   - Call it directly from the `.venv` path: `.\.venv\Scripts\pyinstaller.exe`
   - Run it as a Python module: `python -m PyInstaller` (or `.\.venv\Scripts\python.exe -m PyInstaller`)
   - Activate the virtual environment in PowerShell first: `.\.venv\Scripts\Activate.ps1`

2. **Access Denied / File Lock (`PermissionError: [Errno 13] Access is denied: ... FocusTimer.exe`):**
   Windows locks running executables. If `FocusTimer.exe` is already open or running in the background, PyInstaller cannot overwrite it during a rebuild. Terminate running instances before building:
   ```powershell
   Get-Process -Name "FocusTimer" -ErrorAction SilentlyContinue | Stop-Process -Force
   ```

---

### Build Command (Directory Bundle — Recommended for Fast Startup)

Run this command from the project root:

```powershell
.\.venv\Scripts\pyinstaller.exe --clean --noconfirm --noconsole --onedir --icon timer.ico --name "FocusTimer" --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtPdf main.py
```

*(If your virtual environment is already activated or PyInstaller is in your system PATH, you can run `pyinstaller` directly without the `.\.venv\Scripts\` prefix).*

#### Flags Explained:
- `--clean`: Clears PyInstaller cache and removes temporary files before building.
- `--noconfirm`: Overwrites existing output directory (`dist\FocusTimer`) without prompting.
- `--noconsole`: Hides the background terminal window on launch.
- `--onedir`: Generates a folder bundle with dependencies (starts instantly without unpacking overhead).
- `--icon timer.ico`: Embeds the application icon.
- `--name "FocusTimer"`: Sets the executable name to `FocusTimer.exe`.
- `--exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtPdf`: Strips heavy unused Qt modules to save over 120 MB of space.

---

### Running the Built Executable

After building, the application is located at:
```powershell
.\dist\FocusTimer\FocusTimer.exe
```

> [!NOTE]
> Keep the entire `dist\FocusTimer\` folder together when moving or distributing the app, as it contains the required PySide6 DLLs and Qt plugins.

---

### Alternative: Portable Single-File Executable (`--onefile`)

If you prefer a single self-contained `.exe` file that can be distributed standalone:

```powershell
.\.venv\Scripts\pyinstaller.exe --clean --noconfirm --noconsole --onefile --icon timer.ico --name "FocusTimer" --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtPdf main.py
```

The output file will be at `dist\FocusTimer.exe` (note that `--onefile` extracts files to a temporary folder on launch, so startup is slightly slower than `--onedir`).

---

## Configuration

All visual and behavioral settings are defined in [config.py](file:///d:/zed/timerontop/config.py):

| Setting | Default | Description |
|---|---|---|
| `CORNER` | `"bottom-right"` | Screen corner anchor: `"top-left"`, `"top-right"`, `"bottom-left"`, `"bottom-right"` |
| `MARGIN` | `24` | Distance in pixels from the screen available geometry (taskbar excluded) |
| `ACCENT` | `"#FF9F0A"` | Primary accent color (iOS orange) |
| `DEFAULT_MIN` | `25` | Default duration on launch (minutes) |
| `MIN_MINUTES` | `1` | Minimum timer duration in minutes |
| `MAX_MINUTES` | `720` | Maximum timer duration in minutes (12 hours) |
| `TYPED_ENTRY_AUTOSTART` | `False` | Whether confirming a typed duration immediately starts the timer |
| `TICK_SOUND` | `False` | Optional subtle click sound on each tick scrub |
| `COLLAPSED_SIZE` | `(200, 44)` | Width and height of the visible collapsed pill |
| `EXPANDED_SIZE` | `(300, 150)` | Width and height of the visible expanded card |
| `SHADOW_PADDING` | `14` | Padding around the capsule for the soft drop shadow |
| `ANIM_MS` | `300` | Duration of the expand/collapse morph animation |
| `PROGRESS_STYLE` | `"ring"` | Progress indicator style: `"ring"` or `"fill"` |
| `DRAG_THRESHOLD` | `4` | Movement threshold in pixels to distinguish click vs drag |

---

## File Structure

```
timerontop/
├── config.py         # Configuration constants
├── timer_logic.py    # Countdown model using monotonic timestamps (no UI code)
├── widgets.py        # Circular buttons, preset pills, custom inputs & expanded view
├── main.py           # Top-level frameless translucent window, painting & animations
├── requirements.txt  # Dependencies (PySide6)
└── README.md         # Documentation & run instructions
```
