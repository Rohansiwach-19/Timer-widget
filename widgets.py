"""
Custom UI Widgets for Dynamic Island Timer
Includes custom buttons, interactive tick ruler, per-segment editable time display,
and the expanded card view.
"""
import math
import time
from typing import Optional

try:
    import winsound
except ImportError:
    winsound = None

from PySide6.QtCore import (
    Qt,
    QSize,
    QRect,
    QRectF,
    QPoint,
    QPointF,
    Signal,
    QTimer,
    QVariantAnimation,
    QEasingCurve,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QBrush,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QMouseEvent,
    QWheelEvent,
    QKeyEvent,
    QPaintEvent,
)
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
)
import config


def get_tabular_font(size: int = 12, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Returns a Segoe UI / Segoe UI Variable font configured with tabular numbers."""
    font = QFont()
    font.setFamilies(["Segoe UI Variable Display", "Segoe UI Variable Text", "Segoe UI", "system-ui", "sans-serif"])
    font.setPixelSize(size)
    font.setWeight(weight)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    try:
        font.setFeature(QFont.Tag("tnum"), 1)
    except Exception:
        pass
    return font


class CloseButton(QPushButton):
    """
    Minimal close button with 24x24 px hit target, inset from corner
    so it is never clipped, fading in on hover only (Spec 6.2).
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Close")

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self.underMouse():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(QColor(255, 255, 255, 28))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 6, 6)

        pen = QPen(QColor("#FFFFFF"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        m = 7.0
        w = float(self.width())
        h = float(self.height())
        painter.drawLine(QPointF(m, m), QPointF(w - m, h - m))
        painter.drawLine(QPointF(w - m, m), QPointF(m, h - m))


class CircleButton(QPushButton):
    """
    Round button with vector icon (Play, Pause, or Reset).
    Supports custom background colors and hover styling.
    """
    def __init__(
        self,
        icon_type: str = "play",
        bg_color: str = config.ACCENT,
        fg_color: str = "#000000",
        size: int = 34,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.icon_type = icon_type
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.btn_size = size
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_icon_type(self, icon_type: str) -> None:
        if self.icon_type != icon_type:
            self.icon_type = icon_type
            self.update()

    def set_bg_color(self, bg_color: str) -> None:
        if self.bg_color != bg_color:
            self.bg_color = bg_color
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, self.width(), self.height())
        bg = QColor(self.bg_color)
        if self.underMouse():
            bg = bg.lighter(115)
        if self.isDown():
            bg = bg.darker(115)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawEllipse(rect)

        fg = QColor(self.fg_color)
        cx = rect.center().x()
        cy = rect.center().y()

        if self.icon_type == "play":
            path = QPainterPath()
            w = 11.0
            h = 13.0
            x_offset = 1.0
            path.moveTo(cx - w / 2.0 + x_offset, cy - h / 2.0)
            path.lineTo(cx + w / 2.0 + x_offset, cy)
            path.lineTo(cx - w / 2.0 + x_offset, cy + h / 2.0)
            path.closeSubpath()
            painter.setBrush(fg)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)

        elif self.icon_type == "pause":
            bar_w = 3.2
            bar_h = 12.0
            gap = 3.8
            painter.setBrush(fg)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(cx - gap / 2.0 - bar_w, cy - bar_h / 2.0, bar_w, bar_h), 1.5, 1.5)
            painter.drawRoundedRect(QRectF(cx + gap / 2.0, cy - bar_h / 2.0, bar_w, bar_h), 1.5, 1.5)

        elif self.icon_type == "reset":
            pen = QPen(fg, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            radius = 6.0
            arc_rect = QRectF(cx - radius, cy - radius, radius * 2.0, radius * 2.0)
            painter.drawArc(arc_rect, 45 * 16, 270 * 16)

            arrow_path = QPainterPath()
            tip_x = cx + radius * 0.707
            tip_y = cy - radius * 0.707
            arrow_path.moveTo(tip_x - 3.5, tip_y - 2.5)
            arrow_path.lineTo(tip_x + 0.5, tip_y - 2.5)
            arrow_path.lineTo(tip_x + 0.5, tip_y + 1.5)
            painter.drawPath(arrow_path)


class TickRuler(QWidget):
    """
    Horizontal duration picker ruler (Spec 6.2.1).
    Features:
    - Orange ticks, taller major ticks with number labels above them.
    - Fixed small orange triangle indicator under the current value.
    - Soft edge gradient fade.
    - Auto-zoom levels (1m, 5m, 15m) with smooth transitions and no value jumps.
    - Drag left/right (dragging right increases time), wheel, and arrow keys.
    - Shift key moves in 15-minute steps.
    - Inertia / fling on release with soft snap to nearest tick.
    - Lockable while running: ticks follow countdown live, ticks on remaining side
      are bright orange and elapsed ticks are dimmed.
    """
    minutes_changed = Signal(float)
    minutes_committed = Signal(float)

    def __init__(self, initial_minutes: float = float(config.DEFAULT_MIN), parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_minutes: float = float(initial_minutes)
        self.locked: bool = False
        self.setFixedHeight(44)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.SizeHorCursor)

        # Interaction & inertia state
        self._is_dragging: bool = False
        self._last_mouse_x: float = 0.0
        self._velocity: float = 0.0
        self._last_time: float = 0.0
        self._shift_held: bool = False

        self._inertia_timer = QTimer(self)
        self._inertia_timer.setInterval(16)
        self._inertia_timer.timeout.connect(self._on_inertia_step)

        self._snap_anim: Optional[QVariantAnimation] = None
        self._last_tick_sound: int = -1

    def set_locked(self, locked: bool) -> None:
        if self.locked != locked:
            self.locked = locked
            if locked:
                if self._inertia_timer.isActive():
                    self._inertia_timer.stop()
                if self._snap_anim and self._snap_anim.state() == QVariantAnimation.State.Running:
                    self._snap_anim.stop()
                self._is_dragging = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
            else:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.update()

    def set_minutes(self, minutes: float, emit_signal: bool = True) -> None:
        clamped = max(float(config.MIN_MINUTES), min(float(config.MAX_MINUTES), float(minutes)))
        if abs(clamped - self.current_minutes) > 0.001:
            self.current_minutes = clamped
            if not self.locked:
                self._check_tick_sound()
            self.update()
            if emit_signal and not self.locked:
                self.minutes_changed.emit(self.current_minutes)

    def animate_to_minutes(self, target_minutes: float, duration_ms: int = 120) -> None:
        """Smoothly animates ruler position to target_minutes (e.g. following typed entry)."""
        clamped = max(float(config.MIN_MINUTES), min(float(config.MAX_MINUTES), float(target_minutes)))
        if self._snap_anim and self._snap_anim.state() == QVariantAnimation.State.Running:
            self._snap_anim.stop()
        if abs(clamped - self.current_minutes) < 0.05:
            self.current_minutes = clamped
            self.update()
            return

        self._snap_anim = QVariantAnimation(self)
        self._snap_anim.setDuration(duration_ms)
        self._snap_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._snap_anim.setStartValue(self.current_minutes)
        self._snap_anim.setEndValue(clamped)
        self._snap_anim.valueChanged.connect(lambda val: (setattr(self, 'current_minutes', float(val)), self.update()))
        self._snap_anim.start()

    def _get_scale(self, m: float) -> float:
        """
        Calculates pixels per minute as a smooth continuous function of m.
        Level 1 (1–30m): 10.0 px/min
        Level 2 (30m–2h): 2.0 px/min
        Level 3 (2h–12h): 0.67 px/min
        """
        if m <= 26.0:
            return 10.0
        elif m < 34.0:
            t = (m - 26.0) / 8.0
            return 10.0 * (1.0 - t) + 2.0 * t
        elif m <= 110.0:
            return 2.0
        elif m < 130.0:
            t = (m - 110.0) / 20.0
            return 2.0 * (1.0 - t) + 0.67 * t
        else:
            return 0.67

    def _get_nearest_tick(self, m: float) -> float:
        if self._shift_held or m >= 120.0:
            step = 15.0
        elif m >= 30.0:
            step = 5.0
        else:
            step = 1.0
        snapped = round(m / step) * step
        return max(float(config.MIN_MINUTES), min(float(config.MAX_MINUTES), snapped))

    def _check_tick_sound(self) -> None:
        if not config.TICK_SOUND:
            return
        current_int = int(round(self.current_minutes))
        if current_int != self._last_tick_sound:
            self._last_tick_sound = current_int
            if winsound:
                try:
                    winsound.Beep(2200, 10)
                except Exception:
                    pass

    # --------------------------------------------------------------------------
    # Mouse & Keyboard Event Handlers
    # --------------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.locked:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self._is_dragging = True
            self._last_mouse_x = event.position().x()
            self._velocity = 0.0
            self._last_time = time.monotonic()
            self._shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

            if self._inertia_timer.isActive():
                self._inertia_timer.stop()
            if self._snap_anim and self._snap_anim.state() == QVariantAnimation.State.Running:
                self._snap_anim.stop()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.locked:
            return
        if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            now = time.monotonic()
            dt = max(0.001, now - self._last_time)
            curr_x = event.position().x()
            dx = curr_x - self._last_mouse_x
            self._last_mouse_x = curr_x
            self._last_time = now

            self._shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            scale = self._get_scale(self.current_minutes)
            multiplier = 3.0 if self._shift_held else 1.0
            d_min = (dx / scale) * multiplier

            inst_vel = d_min / dt
            self._velocity = 0.6 * self._velocity + 0.4 * inst_vel

            self.set_minutes(self.current_minutes + d_min, emit_signal=True)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.locked:
            return
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            self._shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

            if abs(self._velocity) > 6.0:
                self._inertia_timer.start()
            else:
                self._start_soft_snap()
        super().mouseReleaseEvent(event)

    def _on_inertia_step(self) -> None:
        if self.locked:
            self._inertia_timer.stop()
            return
        d_min = self._velocity * 0.016
        new_val = self.current_minutes + d_min
        self._velocity *= 0.88

        if new_val <= config.MIN_MINUTES or new_val >= config.MAX_MINUTES or abs(self._velocity) < 1.0:
            self._inertia_timer.stop()
            self.set_minutes(new_val, emit_signal=True)
            self._start_soft_snap()
        else:
            self.set_minutes(new_val, emit_signal=True)

    def _start_soft_snap(self) -> None:
        if self.locked:
            return
        target_tick = self._get_nearest_tick(self.current_minutes)
        if abs(target_tick - self.current_minutes) < 0.05:
            self.set_minutes(target_tick, emit_signal=True)
            self.minutes_committed.emit(self.current_minutes)
            return

        self._snap_anim = QVariantAnimation(self)
        self._snap_anim.setDuration(120)
        self._snap_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._snap_anim.setStartValue(self.current_minutes)
        self._snap_anim.setEndValue(target_tick)
        self._snap_anim.valueChanged.connect(lambda val: self.set_minutes(float(val), emit_signal=True))
        self._snap_anim.finished.connect(lambda: self.minutes_committed.emit(self.current_minutes))
        self._snap_anim.start()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.locked:
            return
        num_degrees = event.angleDelta().y() / 8.0
        num_steps = num_degrees / 15.0

        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if shift:
            step_size = 15.0
        elif self.current_minutes >= 120.0:
            step_size = 15.0
        elif self.current_minutes >= 30.0:
            step_size = 5.0
        else:
            step_size = 1.0

        d_min = num_steps * step_size
        target = self.current_minutes + d_min
        target_snapped = self._get_nearest_tick(target)
        self.set_minutes(target_snapped, emit_signal=True)
        self.minutes_committed.emit(self.current_minutes)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.locked:
            return
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if shift:
            step_size = 15.0
        elif self.current_minutes >= 120.0:
            step_size = 15.0
        elif self.current_minutes >= 30.0:
            step_size = 5.0
        else:
            step_size = 1.0

        if event.key() == Qt.Key.Key_Left:
            target = max(float(config.MIN_MINUTES), self.current_minutes - step_size)
            self.set_minutes(self._get_nearest_tick(target), emit_signal=True)
            self.minutes_committed.emit(self.current_minutes)
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            target = min(float(config.MAX_MINUTES), self.current_minutes + step_size)
            self.set_minutes(self._get_nearest_tick(target), emit_signal=True)
            self.minutes_committed.emit(self.current_minutes)
            event.accept()
        else:
            super().keyPressEvent(event)

    # --------------------------------------------------------------------------
    # Custom Painting
    # --------------------------------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = float(self.width())
        h = float(self.height())
        cx = w / 2.0
        m = self.current_minutes
        scale = self._get_scale(m)

        # Visible range of minutes
        half_range = (cx + 30.0) / scale
        min_m = max(float(config.MIN_MINUTES), m - half_range)
        max_m = min(float(config.MAX_MINUTES), m + half_range)

        font = get_tabular_font(9, QFont.Weight.DemiBold)
        painter.setFont(font)

        accent = QColor(config.ACCENT)
        base_line_y = 34.0

        def get_tick_color(val: float, is_major: bool, alpha_mult: float) -> tuple[QColor, QColor]:
            """Returns (tick_color, label_color) applying dimming to elapsed side while running."""
            is_elapsed = self.locked and (val > m)
            dim_factor = 0.22 if is_elapsed else 1.0
            t_col = QColor(accent)
            base_t_alpha = (240 if is_major else 150) * alpha_mult * dim_factor
            t_col.setAlpha(int(max(0, min(255, base_t_alpha))))

            l_col = QColor(accent)
            base_l_alpha = 255 * alpha_mult * dim_factor
            l_col.setAlpha(int(max(0, min(255, base_l_alpha))))
            return t_col, l_col

        # Level 1 ticks (1-minute step)
        if min_m < 34.0:
            alpha_l1 = max(0.0, min(1.0, (34.0 - m) / 8.0)) if m > 26.0 else 1.0
            if alpha_l1 > 0:
                start_tick = max(1, int(math.floor(min_m)))
                end_tick = min(30, int(math.ceil(max_m)))
                for t in range(start_tick, end_tick + 1):
                    tx = cx + (t - m) * scale
                    if -10 <= tx <= w + 10:
                        is_major = (t % 5 == 0)
                        tick_h = 13.0 if is_major else 6.5
                        t_color, l_color = get_tick_color(float(t), is_major, alpha_l1)
                        painter.setPen(QPen(t_color, 1.2))
                        painter.drawLine(QPointF(tx, base_line_y - tick_h), QPointF(tx, base_line_y))

                        if is_major:
                            painter.setPen(l_color)
                            painter.drawText(
                                QRectF(tx - 15, 4, 30, 14),
                                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                                str(t),
                            )

        # Level 2 ticks (5-minute step)
        if max_m >= 25.0 and min_m <= 135.0:
            alpha_l2 = 1.0
            if m < 34.0:
                alpha_l2 = max(0.0, min(1.0, (m - 26.0) / 8.0))
            elif m > 110.0:
                alpha_l2 = max(0.0, min(1.0, (130.0 - m) / 20.0))

            start_5 = max(30, int(math.floor(min_m / 5.0) * 5))
            end_5 = min(120, int(math.ceil(max_m / 5.0) * 5))
            for t in range(start_5, end_5 + 1, 5):
                tx = cx + (t - m) * scale
                if -15 <= tx <= w + 15:
                    is_major = (t % 30 == 0)
                    tick_h = 13.0 if is_major else 6.5
                    t_color, l_color = get_tick_color(float(t), is_major, alpha_l2)
                    painter.setPen(QPen(t_color, 1.2))
                    painter.drawLine(QPointF(tx, base_line_y - tick_h), QPointF(tx, base_line_y))

                    if is_major and alpha_l2 > 0.1:
                        if t == 30:
                            lbl = "30m"
                        elif t == 60:
                            lbl = "1h"
                        elif t == 90:
                            lbl = "1h30"
                        elif t == 120:
                            lbl = "2h"
                        else:
                            lbl = f"{t}m"
                        painter.setPen(l_color)
                        painter.drawText(
                            QRectF(tx - 20, 4, 40, 14),
                            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                            lbl,
                        )

        # Level 3 ticks (15-minute step)
        if max_m >= 115.0:
            alpha_l3 = max(0.0, min(1.0, (m - 110.0) / 20.0)) if m < 130.0 else 1.0
            start_15 = max(120, int(math.floor(min_m / 15.0) * 15))
            end_15 = min(config.MAX_MINUTES, int(math.ceil(max_m / 15.0) * 15))
            for t in range(start_15, end_15 + 1, 15):
                tx = cx + (t - m) * scale
                if -20 <= tx <= w + 20:
                    is_major = (t % 60 == 0)
                    tick_h = 13.0 if is_major else 6.5
                    t_color, l_color = get_tick_color(float(t), is_major, alpha_l3)
                    painter.setPen(QPen(t_color, 1.2))
                    painter.drawLine(QPointF(tx, base_line_y - tick_h), QPointF(tx, base_line_y))

                    if is_major and alpha_l3 > 0.1:
                        lbl = f"{t // 60}h"
                        painter.setPen(l_color)
                        painter.drawText(
                            QRectF(tx - 18, 4, 36, 14),
                            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                            lbl,
                        )

        # Center triangle indicator pointing up at current value
        tri_path = QPainterPath()
        tri_path.moveTo(cx - 4.0, base_line_y + 6.0)
        tri_path.lineTo(cx + 4.0, base_line_y + 6.0)
        tri_path.lineTo(cx, base_line_y + 0.5)
        tri_path.closeSubpath()
        painter.setBrush(accent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(tri_path)

        # Edge fade gradient masks (left and right edges)
        fade_w = 32.0
        grad_l = QLinearGradient(0, 0, fade_w, 0)
        grad_l.setColorAt(0.0, QColor(config.SURFACE_COLOR))
        grad_l.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(0, 0, fade_w, h), grad_l)

        grad_r = QLinearGradient(w - fade_w, 0, w, 0)
        grad_r.setColorAt(0.0, QColor(0, 0, 0, 0))
        grad_r.setColorAt(1.0, QColor(config.SURFACE_COLOR))
        painter.fillRect(QRectF(w - fade_w, 0, fade_w, h), grad_r)


class SegmentedTimeDisplay(QWidget):
    """
    Remaining time display with per-segment live editing (Requirement 3).
    - Hours (shown when > 0 or active), minutes, seconds.
    - Clicking a segment activates only that segment with subtle accent underline & caret.
    - At rest: looks non-clickable, pointer cursor on hover.
    - Live updates: 1st digit replaces, 2nd appends, normalizes >59 live into hours.
    - H and M keys are unit shortcuts (digits + H -> hours, digits + M -> minutes,
      alone -> switch active segment).
    - Left/Right arrow keys navigate segments.
    - Enter ONLY starts the timer (ends editing & runs current live value; if 0 -> shake).
    - Esc exits editing and restores value from edit start.
    - No editing while running.
    """
    duration_changed_live = Signal(float)  # duration in seconds
    start_timer_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setMinimumWidth(150)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.hours: int = 0
        self.minutes: int = int(config.DEFAULT_MIN)
        self.seconds: int = 0
        self.total_seconds: float = float(config.DEFAULT_MIN * 60)

        self.is_editing: bool = False
        self.active_segment: str = "minutes"  # "hours", "minutes", "seconds"
        self.segment_buffer: str = ""
        self.initial_seconds_on_edit: float = self.total_seconds

        self.is_running: bool = False
        self.is_finished: bool = False

        # Caret blinking
        self.caret_visible: bool = True
        self.caret_timer = QTimer(self)
        self.caret_timer.setInterval(500)
        self.caret_timer.timeout.connect(self._toggle_caret)

        # Shake animation
        self.shake_offset: float = 0.0
        self.is_shaking: bool = False
        self._shake_anim: Optional[QVariantAnimation] = None

        # Hit-test bounding rects calculated in paintEvent or helper
        self._rects: dict[str, QRectF] = {}
        self._calc_rects()

    def sizeHint(self) -> QSize:
        return QSize(160, 48)

    def minimumSizeHint(self) -> QSize:
        return QSize(140, 48)

    def _calc_rects(self) -> dict[str, QRectF]:
        font = get_tabular_font(34, QFont.Weight.DemiBold)
        fm = QFontMetrics(font)

        show_hours = (self.hours > 0 or (self.is_editing and self.active_segment == "hours"))

        if show_hours:
            parts = [
                ("hours", f"{self.hours}"),
                ("colon1", ":"),
                ("minutes", f"{self.minutes:02d}"),
                ("colon2", ":"),
                ("seconds", f"{self.seconds:02d}"),
            ]
        else:
            parts = [
                ("minutes", f"{self.minutes:02d}"),
                ("colon2", ":"),
                ("seconds", f"{self.seconds:02d}"),
            ]

        part_widths = {}
        total_w = 0.0
        for name, text in parts:
            pw = float(fm.horizontalAdvance(text))
            part_widths[name] = pw
            total_w += pw

        w = float(self.width()) if self.width() > 0 else 150.0
        start_x = w - total_w - 2.0 + self.shake_offset
        y_text = 37.0

        rects = {}
        curr_x = start_x
        for name, text in parts:
            pw = part_widths[name]
            rects[name] = QRectF(curr_x, y_text - fm.ascent(), pw, fm.height())
            curr_x += pw

        self._rects = rects
        return rects

    def _toggle_caret(self) -> None:
        if self.is_editing:
            self.caret_visible = not self.caret_visible
            self.update()

    def set_duration_from_ruler(self, seconds: float) -> None:
        """Called when the ruler changes to update time display live."""
        self.end_editing()
        self.set_total_seconds(seconds, emit_live=False)

    def set_total_seconds(self, seconds: float, emit_live: bool = False) -> None:
        sec = max(0.0, min(float(config.MAX_MINUTES * 60), float(seconds)))
        self.total_seconds = sec
        rem = int(math.ceil(sec))
        self.hours = rem // 3600
        self.minutes = (rem % 3600) // 60
        self.seconds = rem % 60
        self.update()
        if emit_live:
            self.duration_changed_live.emit(self.total_seconds)

    def set_timer_state(self, is_running: bool, is_finished: bool) -> None:
        self.is_running = is_running
        self.is_finished = is_finished
        if is_running and self.is_editing:
            self.end_editing()
        self.update()

    def end_editing(self) -> None:
        """Ends editing and keeps the live value."""
        if self.is_editing:
            self.is_editing = False
            self.segment_buffer = ""
            self.caret_timer.stop()
            self.update()

    # --------------------------------------------------------------------------
    # Mouse Click & Segment Activation
    # --------------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.is_running:
            return  # No editing while running (Req 3g)

        if event.button() == Qt.MouseButton.LeftButton:
            top_win = self.window()
            if top_win:
                top_win.activateWindow()

            if not self.is_editing:
                self.is_editing = True
                self.initial_seconds_on_edit = self.total_seconds
                self.caret_timer.start()

            # Find nearest segment
            self._calc_rects()
            click_x = event.position().x()
            candidates = [("minutes", self._rects.get("minutes")), ("seconds", self._rects.get("seconds"))]
            if "hours" in self._rects and self._rects["hours"] is not None:
                candidates.insert(0, ("hours", self._rects["hours"]))

            best_seg = "minutes"
            best_dist = 999999.0
            for seg_name, rect in candidates:
                if rect is not None:
                    dist = abs(click_x - rect.center().x())
                    if dist < best_dist:
                        best_dist = dist
                        best_seg = seg_name

            self.active_segment = best_seg
            self.segment_buffer = ""
            self.caret_visible = True
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    # --------------------------------------------------------------------------
    # Keyboard Handling (Normal Widget-level Events)
    # --------------------------------------------------------------------------
    def handle_key(self, event: QKeyEvent) -> bool:
        if self.is_running:
            return False

        key = event.key()
        text = event.text()

        # Enter starts timer immediately (Req 3e)
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.handle_enter()
            return True

        # Esc cancels and restores initial value (Req 3f)
        if key == Qt.Key.Key_Escape:
            self.handle_escape()
            return True

        # Navigation
        if key == Qt.Key.Key_Left:
            self.handle_left_arrow()
            return True
        if key == Qt.Key.Key_Right:
            self.handle_right_arrow()
            return True
        if key == Qt.Key.Key_Backspace:
            self.handle_backspace()
            return True

        # Digits 0-9
        if text.isdigit():
            self.handle_digit(text)
            return True

        # H and M unit shortcuts
        if text.lower() == 'h':
            self.handle_h()
            return True
        if text.lower() == 'm':
            self.handle_m()
            return True

        return False

    def handle_digit(self, d: str) -> None:
        if not self.is_editing:
            self.is_editing = True
            self.active_segment = "minutes"
            self.segment_buffer = ""
            self.initial_seconds_on_edit = self.total_seconds
            self.caret_timer.start()

        # The first digit replaces that segment's value. Second appends (max 2 digits).
        if self.segment_buffer == "":
            self.segment_buffer = d
        elif len(self.segment_buffer) == 1:
            self.segment_buffer += d
        else:
            self.segment_buffer = d

        val = int(self.segment_buffer)

        if self.active_segment == "hours":
            self.hours = min(12, val)
        elif self.active_segment == "minutes":
            # Minutes above 59 normalize live into hours (typing 90 gives 1:30:00, 120 gives 2:00:00)
            if val >= 60:
                self.hours = min(12, val // 60)
                self.minutes = val % 60
            else:
                self.minutes = val
        elif self.active_segment == "seconds":
            if val >= 60:
                self.minutes = min(59, self.minutes + val // 60)
                self.seconds = val % 60
            else:
                self.seconds = val

        self._clamp_and_emit_live()

    def handle_h(self) -> None:
        if not self.is_editing:
            self.is_editing = True
            self.active_segment = "hours"
            self.segment_buffer = ""
            self.initial_seconds_on_edit = self.total_seconds
            self.caret_timer.start()
            self.update()
            return

        # Digits just typed, then H: those digits become HOURS, minutes reset to 0,
        # and active segment moves to minutes (Req 3d)
        if self.segment_buffer != "":
            val = int(self.segment_buffer)
            self.hours = min(12, val)
            self.minutes = 0
            self.seconds = 0
            self.segment_buffer = ""
            self.active_segment = "minutes"
            self._clamp_and_emit_live()
        else:
            # H pressed with no pending digits: move active segment to hours
            self.active_segment = "hours"
            self.segment_buffer = ""
            self.update()

    def handle_m(self) -> None:
        if not self.is_editing:
            self.is_editing = True
            self.active_segment = "minutes"
            self.segment_buffer = ""
            self.initial_seconds_on_edit = self.total_seconds
            self.caret_timer.start()
            self.update()
            return

        # Digits just typed, then M: those digits are MINUTES, active segment stays minutes
        if self.segment_buffer != "":
            val = int(self.segment_buffer)
            if val >= 60:
                self.hours = min(12, val // 60)
                self.minutes = val % 60
            else:
                self.minutes = val
            self.segment_buffer = ""
            self.active_segment = "minutes"
            self._clamp_and_emit_live()
        else:
            # M pressed with no pending digits: return active segment to minutes
            self.active_segment = "minutes"
            self.segment_buffer = ""
            self.update()

    def handle_backspace(self) -> None:
        if not self.is_editing:
            return
        if self.segment_buffer != "":
            self.segment_buffer = self.segment_buffer[:-1]
            val = int(self.segment_buffer) if self.segment_buffer else 0
            if self.active_segment == "hours":
                self.hours = val
            elif self.active_segment == "minutes":
                self.minutes = val
            elif self.active_segment == "seconds":
                self.seconds = val
            self._clamp_and_emit_live()
        else:
            # Reset active segment to 0
            if self.active_segment == "hours":
                self.hours = 0
            elif self.active_segment == "minutes":
                self.minutes = 0
            elif self.active_segment == "seconds":
                self.seconds = 0
            self._clamp_and_emit_live()

    def handle_left_arrow(self) -> None:
        if not self.is_editing:
            return
        if self.active_segment == "seconds":
            self.active_segment = "minutes"
        elif self.active_segment == "minutes":
            self.active_segment = "hours"
        self.segment_buffer = ""
        self.update()

    def handle_right_arrow(self) -> None:
        if not self.is_editing:
            return
        if self.active_segment == "hours":
            self.active_segment = "minutes"
        elif self.active_segment == "minutes":
            self.active_segment = "seconds"
        self.segment_buffer = ""
        self.update()

    def handle_enter(self) -> None:
        """Enter ONLY starts the timer (Req 3e)."""
        if self.total_seconds <= 0:
            self.shake()
            return
        self.end_editing()
        self.start_timer_requested.emit()

    def handle_escape(self) -> None:
        """Esc exits editing and restores value from edit start (Req 3f)."""
        self.set_total_seconds(self.initial_seconds_on_edit, emit_live=True)
        self.end_editing()

    def _clamp_and_emit_live(self) -> None:
        total = self.hours * 3600 + self.minutes * 60 + self.seconds
        max_sec = config.MAX_MINUTES * 60
        if total > max_sec:
            total = max_sec
            self.hours = 12
            self.minutes = 0
            self.seconds = 0

        self.total_seconds = float(total)
        self.caret_visible = True
        self.update()
        self.duration_changed_live.emit(self.total_seconds)

    def shake(self) -> None:
        """Shake animation when Enter pressed with zero duration."""
        if self._shake_anim and self._shake_anim.state() == QVariantAnimation.State.Running:
            self._shake_anim.stop()

        self.is_shaking = True
        self._shake_anim = QVariantAnimation(self)
        self._shake_anim.setDuration(220)
        self._shake_anim.setStartValue(0.0)
        self._shake_anim.setKeyValueAt(0.2, -5.0)
        self._shake_anim.setKeyValueAt(0.4, 5.0)
        self._shake_anim.setKeyValueAt(0.6, -4.0)
        self._shake_anim.setKeyValueAt(0.8, 4.0)
        self._shake_anim.setEndValue(0.0)
        self._shake_anim.valueChanged.connect(lambda val: (setattr(self, 'shake_offset', float(val)), self.update()))

        def on_done():
            self.is_shaking = False
            self.shake_offset = 0.0
            self.update()

        self._shake_anim.finished.connect(on_done)
        self._shake_anim.start()

    # --------------------------------------------------------------------------
    # Custom Painting
    # --------------------------------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        font = get_tabular_font(34, QFont.Weight.DemiBold)
        painter.setFont(font)
        fm = QFontMetrics(font)

        show_hours = (self.hours > 0 or (self.is_editing and self.active_segment == "hours"))

        if show_hours:
            parts = [
                ("hours", f"{self.hours}"),
                ("colon1", ":"),
                ("minutes", f"{self.minutes:02d}"),
                ("colon2", ":"),
                ("seconds", f"{self.seconds:02d}"),
            ]
        else:
            parts = [
                ("minutes", f"{self.minutes:02d}"),
                ("colon2", ":"),
                ("seconds", f"{self.seconds:02d}"),
            ]

        # Calculate widths
        part_widths = {}
        total_w = 0.0
        for name, text in parts:
            pw = float(fm.horizontalAdvance(text))
            part_widths[name] = pw
            total_w += pw

        # Right-aligned with shake offset
        w = float(self.width())
        start_x = w - total_w - 2.0 + self.shake_offset
        y_text = 37.0

        # Clear bounding rects
        self._rects.clear()

        curr_x = start_x
        for name, text in parts:
            pw = part_widths[name]
            seg_rect = QRectF(curr_x, y_text - fm.ascent(), pw, fm.height())
            self._rects[name] = seg_rect

            # Determine color: accent color at rest (idle, paused, finished, running)
            if self.is_shaking:
                col = QColor("#FF453A")
            elif self.is_editing and name in ("hours", "minutes", "seconds") and self.active_segment != name:
                col = QColor(config.ACCENT)
                col.setAlpha(160)
            else:
                col = QColor(config.ACCENT)

            painter.setPen(col)
            painter.drawText(QPointF(curr_x, y_text), text)

            # Draw subtle accent underline and blinking caret on active segment
            if self.is_editing and self.active_segment == name:
                # Subtle accent underline (Req 3b)
                pen_underline = QPen(QColor(config.ACCENT), 1.6)
                painter.setPen(pen_underline)
                painter.drawLine(QPointF(seg_rect.left(), y_text + 4.0), QPointF(seg_rect.right(), y_text + 4.0))

                # Blinking caret
                if self.caret_visible:
                    caret_pen = QPen(QColor(config.ACCENT), 1.6)
                    painter.setPen(caret_pen)
                    caret_x = seg_rect.right() + 1.0
                    painter.drawLine(QPointF(caret_x, y_text - fm.ascent() + 4.0), QPointF(caret_x, y_text - 2.0))

            curr_x += pw


class ExpandedView(QWidget):
    """
    The full control card widget shown when expanded.
    Layout:
    1. CloseButton at top right (inset from curve, 24x24 px, fades in on hover).
    2. Tick ruler across full width on top (locked and drains smoothly while running).
    3. Small faint line below ruler ("Ends 05:12 PM") computed from monotonic end time.
    4. Bottom row: round Play/Pause and Reset on left, SegmentedTimeDisplay on right.
    """
    start_pause_clicked = Signal()
    reset_clicked = Signal()
    duration_changed = Signal(float)  # duration in seconds
    close_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(config.EXPANDED_SIZE[0], config.EXPANDED_SIZE[1])
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._init_ui()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 8, 14, 12)
        root_layout.setSpacing(2)

        # 1. Ruler on top across full width
        self.ruler = TickRuler(initial_minutes=float(config.DEFAULT_MIN), parent=self)
        self.ruler.minutes_changed.connect(self._on_ruler_scrolled)
        self.ruler.minutes_committed.connect(self._on_ruler_scrolled)
        root_layout.addWidget(self.ruler)

        # 2. Ends line ("Ends 05:12 PM") below ruler
        self.ends_label = QLabel(self)
        self.ends_label.setFont(get_tabular_font(10, QFont.Weight.Medium))
        self.ends_label.setStyleSheet(f"color: {config.TEXT_MUTED}; background: transparent;")
        self.ends_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ends_label.setFixedHeight(14)
        self.ends_label.hide()
        root_layout.addWidget(self.ends_label)

        root_layout.addStretch()

        # 3. Bottom row: round buttons on left, segmented time display on right
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(10)

        self.play_button = CircleButton(icon_type="play", bg_color=config.ACCENT, fg_color="#000000", size=36, parent=self)
        self.play_button.clicked.connect(self.start_pause_clicked.emit)

        self.reset_button = CircleButton(icon_type="reset", bg_color=config.BUTTON_HOVER, fg_color="#FFFFFF", size=36, parent=self)
        self.reset_button.clicked.connect(self.reset_clicked.emit)

        bottom_row.addWidget(self.play_button)
        bottom_row.addWidget(self.reset_button)
        bottom_row.addStretch()

        self.time_display = SegmentedTimeDisplay(self)
        self.time_display.duration_changed_live.connect(self._on_time_typed_live)
        self.time_display.start_timer_requested.connect(self.start_pause_clicked.emit)
        bottom_row.addWidget(self.time_display)

        root_layout.addLayout(bottom_row)

        # 4. Faint close button top-right (inset by at least 28px corner radius)
        # Position at x = 300 - 32 = 268, y = 8. Click target 24x24 px.
        self.close_button = CloseButton(self)
        self.close_button.move(config.EXPANDED_SIZE[0] - 32, 8)
        self.close_button.clicked.connect(self.close_requested.emit)
        self.close_button.raise_()

    def _on_ruler_scrolled(self, minutes: float) -> None:
        seconds = minutes * 60.0
        self.time_display.set_duration_from_ruler(seconds)
        self.duration_changed.emit(seconds)

    def _on_time_typed_live(self, seconds: float) -> None:
        self.ruler.animate_to_minutes(seconds / 60.0, duration_ms=120)
        self.duration_changed.emit(seconds)

    def set_ends_text(self, text: str) -> None:
        if text:
            self.ends_label.setText(text)
            self.ends_label.show()
        else:
            self.ends_label.hide()

    def update_display(self, remaining_sec: float, is_running: bool, is_finished: bool) -> None:
        self.time_display.set_timer_state(is_running, is_finished)
        if not self.time_display.is_editing:
            self.time_display.set_total_seconds(remaining_sec, emit_live=False)

        if is_finished:
            self.play_button.set_icon_type("play")
            self.play_button.set_bg_color(config.ACCENT)
        elif is_running:
            self.play_button.set_icon_type("pause")
            self.play_button.set_bg_color(config.ACCENT)
        else:
            self.play_button.set_icon_type("play")
            self.play_button.set_bg_color(config.ACCENT)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Route keys to time_display or ruler
        if self.time_display.handle_key(event):
            event.accept()
            return
        if not self.ruler.locked and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.ruler.keyPressEvent(event)
            event.accept()
            return
        super().keyPressEvent(event)

    # Forward mouse press/move/release on background of expanded card to parent window for dragging
    def mousePressEvent(self, event: QMouseEvent) -> None:
        # If user clicks elsewhere on card while editing, end editing and keep live value (Req 3f)
        if self.time_display.is_editing:
            self.time_display.end_editing()

        top_win = self.window()
        if top_win and top_win != self:
            top_win.mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        top_win = self.window()
        if top_win and top_win != self:
            top_win.mouseMoveEvent(event)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        top_win = self.window()
        if top_win and top_win != self:
            top_win.mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)
