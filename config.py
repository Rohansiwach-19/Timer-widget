"""
Dynamic Island Floating Timer - Configuration
All constants for layout, colors, presets, and behavior.
"""

# Positioning & Screen Anchor
# Options: "top-left", "top-right", "bottom-left", "bottom-right"
CORNER = "bottom-right"

# Distance in pixels from the screen boundary / taskbar
MARGIN = 24

# Colors
ACCENT = "#FF9F0A"            # iOS Dynamic Island orange accent
ACCENT_MUTED = "#3D2B00"      # Track / dim orange for progress ring
SURFACE_COLOR = "#000000"     # Pure solid black surface
TEXT_COLOR = "#FFFFFF"        # Main text color in expanded card
TEXT_MUTED = "#8E8E93"        # Subtle secondary text / headers
BUTTON_BG = "#1C1C1E"         # Secondary button background
BUTTON_HOVER = "#2C2C2E"      # Button hover background
BORDER_SUBTLE = "#2C2C2E"     # Subtle border for inputs

# Presets and Bounds
DEFAULT_MIN = 25
MIN_MINUTES = 1
MAX_MINUTES = 12 * 60
TICK_SOUND = False

# Sizes (width, height) of the visible black capsule
COLLAPSED_SIZE = (200, 44)
EXPANDED_SIZE = (300, 150)

# Window drop-shadow padding around the capsule (in pixels)
SHADOW_PADDING = 14

# Morph animation duration in milliseconds
ANIM_MS = 300

# Progress style: "ring" (default) or "fill"
PROGRESS_STYLE = "ring"

# Drag threshold in pixels to distinguish click vs drag
DRAG_THRESHOLD = 4

# Timer tick interval in ms (~30 fps for smooth ruler drain while running)
TICK_INTERVAL_MS = 33

