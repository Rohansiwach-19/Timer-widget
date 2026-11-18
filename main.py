"""
Dynamic Island Floating Timer for Windows
Built with PySide6 from scratch according to DYNAMIC_ISLAND_TIMER_SPEC.md.
"""
import sys
import threading
import time
from typing import Optional

try:
    import winsound
except ImportError:
    winsound = None

from PySide6.QtCore import (
    Qt,
    QRect,
    QRectF,
    QPoint,
    QPointF,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    QVariantAnimation,
    QEvent,
)
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QScreen,
    QMouseEvent,
    QPaintEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QGraphicsOpacityEffect,
)

import config
from timer_logic import TimerLogic, TimerState
from widgets import ExpandedView, get_tabular_font


class DynamicIslandTimer(QWidget):
    """
    Main floating always-on-top window styled after the iOS Dynamic Island.
    Features:
    - Pure solid black capsule with true rounded corners and custom drop shadow.
    - Smooth geometry animation with OutCubic easing anchored to screen corner.
    - Drag vs Click distinction using movement threshold.
    - Accurate countdown with monotonic end timestamp.
    - Auto-collapse on start, auto-expand on finish with gentle pulse and beep.
    """

    def __init__(self, initial_expanded: bool = True):
        super().__init__()
        self.is_expanded: bool = initial_expanded
        self.is_animating: bool = False

        # Home center (in screen coordinates) for the collapsed pill
        self._home_center: QPoint = QPoint()

        # Timer logic model (no UI code)
        self.timer_logic = TimerLogic(default_duration_sec=config.DEFAULT_MIN * 60)

        # Dragging state
        self._drag_start_pos: QPoint = QPoint()
        self._win_start_pos: QPoint = QPoint()
        self._is_dragging: bool = False

        # Pulse animation state for timer finished
        self._pulse_alpha: int = 0
        self._pulse_anim: Optional[QVariantAnimation] = None

        # Content opacity for crossfading
        self._morph_progress: float = 1.0 if initial_expanded else 0.0

        self._init_window()
        self._init_ui()
        self._init_timer_loop()

    def _init_window(self) -> None:
        # Window flags: Frameless, Always on Top, Tool (hidden from taskbar and Alt-Tab)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("Focus Timer")

        # Initial geometry computation anchored to configured corner
        init_geom = self._calc_initial_geom(self.is_expanded)
        self.setGeometry(init_geom)

        # Initialize home center for the collapsed pill
        if self.is_expanded:
            card_center = self._get_visible_center(init_geom)
            pill_rect = self._calc_target_geom(config.COLLAPSED_SIZE, card_center)
            self._home_center = self._get_visible_center(pill_rect)
        else:
            self._home_center = self._get_visible_center(init_geom)

    def _init_ui(self) -> None:
        p = config.SHADOW_PADDING
        self.expanded_view = ExpandedView(self)
        self.expanded_view.move(p, p)

        # Opacity effect for cross-fading expanded contents
        self.expanded_opacity = QGraphicsOpacityEffect(self.expanded_view)
        self.expanded_view.setGraphicsEffect(self.expanded_opacity)
        self.expanded_opacity.setOpacity(1.0 if self.is_expanded else 0.0)
        self.expanded_view.setVisible(self.is_expanded)

        # Connect signals
        self.expanded_view.start_pause_clicked.connect(self._on_start_pause_clicked)
        self.expanded_view.reset_clicked.connect(self._on_reset_clicked)
        self.expanded_view.duration_changed.connect(self._on_duration_changed)
        self.expanded_view.close_requested.connect(self.close)

    def _init_timer_loop(self) -> None:
        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(config.TICK_INTERVAL_MS)
        self.tick_timer.timeout.connect(self._on_timer_tick)
        self.tick_timer.start()

    # --------------------------------------------------------------------------
    # Positioning and Anchoring Calculations
    # --------------------------------------------------------------------------
    def _calc_initial_geom(self, is_expanded: bool) -> QRect:
        p = config.SHADOW_PADDING
        target_size = config.EXPANDED_SIZE if is_expanded else config.COLLAPSED_SIZE
        total_w = target_size[0] + 2 * p
        total_h = target_size[1] + 2 * p

        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        margin = config.MARGIN
        corner = config.CORNER.lower()

        if corner == "bottom-right":
            win_right = avail.right() - margin + p
            win_bottom = avail.bottom() - margin + p
            x = win_right - total_w + 1
            y = win_bottom - total_h + 1
        elif corner == "bottom-left":
            x = avail.left() + margin - p
            win_bottom = avail.bottom() - margin + p
            y = win_bottom - total_h + 1
        elif corner == "top-right":
            win_right = avail.right() - margin + p
            x = win_right - total_w + 1
            y = avail.top() + margin - p
        elif corner == "top-left":
            x = avail.left() + margin - p
            y = avail.top() + margin - p
        else:
            win_right = avail.right() - margin + p
            win_bottom = avail.bottom() - margin + p
            x = win_right - total_w + 1
            y = win_bottom - total_h + 1

        return QRect(x, y, total_w, total_h)

    def _get_visible_center(self, rect: Optional[QRect] = None) -> QPoint:
        """Returns the center of the visible shape for the given window rect (or self.geometry())."""
        r = rect if rect is not None else self.geometry()
        return QPoint(r.x() + r.width() // 2, r.y() + r.height() // 2)

    def _get_screen_for_point(self, point: QPoint) -> Optional[QScreen]:
        """Finds the screen containing point, falling back to window or primary screen."""
        screen = QApplication.screenAt(point)
        if screen is None:
            screen = self.screen() or QApplication.primaryScreen()
        return screen

    def _calc_target_geom(self, size: tuple[int, int], home_center: Optional[QPoint] = None) -> QRect:
        """
        Computes centered window geometry clamped into the screen usable area (availableGeometry).
        Accounts for shadow padding so the visible shape stays within the usable area.
        """
        center = home_center if home_center is not None else self._home_center
        screen = self._get_screen_for_point(center)
        avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        w, h = size
        p = config.SHADOW_PADDING

        # Visible shape top-left centered on center
        vx = center.x() - w // 2
        vy = center.y() - h // 2

        # Usable screen boundaries
        s_left = avail.left()
        s_top = avail.top()
        s_right = avail.left() + avail.width()
        s_bottom = avail.top() + avail.height()

        # Clamp visible rect into screen_rect
        if vx + w > s_right:
            vx = s_right - w
        if vx < s_left:
            vx = s_left

        if vy + h > s_bottom:
            vy = s_bottom - h
        if vy < s_top:
            vy = s_top

        return QRect(vx - p, vy - p, w + 2 * p, h + 2 * p)

    # --------------------------------------------------------------------------
    # Morph Animation (Expand / Collapse)
    # --------------------------------------------------------------------------
    def expand(self) -> None:
        if self.is_expanded:
            return
        self._animate_to_state(expand=True)

    def collapse(self) -> None:
        if not self.is_expanded:
            return
        self._animate_to_state(expand=False)

    def _animate_to_state(self, expand: bool) -> None:
        if expand and not self.is_animating:
            # Remember the pill's center from before expanding (Req 4)
            self._home_center = self._get_visible_center()

        self.is_expanded = expand
        self.is_animating = True

        target_size = config.EXPANDED_SIZE if expand else config.COLLAPSED_SIZE
        target_geom = self._calc_target_geom(target_size, self._home_center)

        # Stop any in-flight animation before starting a new one (Req 3)
        if hasattr(self, "_geom_anim") and self._geom_anim is not None:
            self._geom_anim.stop()

        # Geometry property animation starting from current in-flight geometry
        self._geom_anim = QPropertyAnimation(self, b"geometry")
        self._geom_anim.setDuration(config.ANIM_MS)
        self._geom_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._geom_anim.setStartValue(self.geometry())
        self._geom_anim.setEndValue(target_geom)

        if expand:
            self.expanded_view.setVisible(True)

        self._geom_anim.valueChanged.connect(self._on_anim_step)
        self._geom_anim.finished.connect(lambda: self._on_anim_finished(expand))
        self._geom_anim.start()

    def _on_anim_step(self, val: QRect) -> None:
        curr_h = self.height() - 2 * config.SHADOW_PADDING
        h_range = config.EXPANDED_SIZE[1] - config.COLLAPSED_SIZE[1]
        progress = (curr_h - config.COLLAPSED_SIZE[1]) / float(h_range) if h_range > 0 else 1.0
        self._morph_progress = max(0.0, min(1.0, progress))

        # Fade expanded controls as window morphs
        if self._morph_progress < 0.2:
            self.expanded_opacity.setOpacity(0.0)
            self.expanded_view.setVisible(False)
        else:
            self.expanded_view.setVisible(True)
            opacity = (self._morph_progress - 0.2) / 0.8
            self.expanded_opacity.setOpacity(opacity)

        self.update()

    def _on_anim_finished(self, expand: bool) -> None:
        self.is_animating = False
        self._morph_progress = 1.0 if expand else 0.0
        if expand:
            self.expanded_view.setVisible(True)
            self.expanded_opacity.setOpacity(1.0)
            self.activateWindow()
        else:
            self.expanded_view.setVisible(False)
            self.expanded_opacity.setOpacity(0.0)
        self.update()

    # --------------------------------------------------------------------------
    # Drag vs Click Event Handling
    # --------------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint()
            self._win_start_pos = self.pos()
            self._is_dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            if not self._is_dragging:
                if delta.manhattanLength() >= config.DRAG_THRESHOLD:
                    self._is_dragging = True
                    if hasattr(self, "_geom_anim") and self._geom_anim is not None:
                        self._geom_anim.stop()
                    self.is_animating = False
            if self._is_dragging:
                self.move(self._win_start_pos + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_dragging:
                curr_center = self._get_visible_center()
                pill_rect = self._calc_target_geom(config.COLLAPSED_SIZE, curr_center)
                self._home_center = self._get_visible_center(pill_rect)
                if not self.is_expanded:
                    self.setGeometry(pill_rect)
                self._is_dragging = False
            else:
                # Pure click detected!
                if not self.is_expanded:
                    self.expand()
        super().mouseReleaseEvent(event)

    def changeEvent(self, event: QEvent) -> None:
        # Spec 6.2: Click outside the window (focus lost) collapses back to pill
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                if self.is_expanded and not self._is_dragging:
                    # End editing and keep live value without starting (Req 4)
                    self.expanded_view.time_display.end_editing()
                    self.collapse()
        super().changeEvent(event)

    def keyPressEvent(self, event) -> None:
        # All keyboard handling only works while window is focused (Req 4)
        if self.isActiveWindow() and self.is_expanded:
            if self.expanded_view.time_display.handle_key(event):
                event.accept()
                return
            if not self.expanded_view.ruler.locked and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                self.expanded_view.ruler.keyPressEvent(event)
                event.accept()
                return
        super().keyPressEvent(event)

    # --------------------------------------------------------------------------
    # Timer Callbacks & State Management
    # --------------------------------------------------------------------------
    def _on_timer_tick(self) -> None:
        finished = self.timer_logic.tick()
        is_running = self.timer_logic.state == TimerState.RUNNING
        is_finished = self.timer_logic.state == TimerState.FINISHED

        # Update expanded display
        self.expanded_view.update_display(self.timer_logic.remaining_seconds, is_running, is_finished)

        # Live countdown ruler drains smoothly while running (Req 2)
        if is_running:
            self.expanded_view.ruler.set_locked(True)
            remaining_min = max(0.0, self.timer_logic.remaining_seconds / 60.0)
            self.expanded_view.ruler.set_minutes(remaining_min, emit_signal=False)

            # Compute "Ends 05:12 PM" from monotonic end time
            now_mono = time.monotonic()
            rem = max(0.0, self.timer_logic.end_timestamp - now_mono)
            end_epoch = time.time() + rem
            end_time_str = time.strftime("%I:%M %p", time.localtime(end_epoch))
            self.expanded_view.set_ends_text(f"Ends {end_time_str}")
        else:
            self.expanded_view.ruler.set_locked(False)
            self.expanded_view.set_ends_text("")

        if finished:
            self._on_timer_finished()

        # Repaint collapsed pill if visible
        if not self.is_expanded or self.is_animating:
            self.update()

    def _on_start_pause_clicked(self) -> None:
        self._stop_pulse()
        if self.timer_logic.remaining_seconds <= 0:
            self.expanded_view.time_display.shake()
            return

        state = self.timer_logic.toggle()
        if state == TimerState.RUNNING:
            self.expanded_view.ruler.set_locked(True)
            now_mono = time.monotonic()
            rem = max(0.0, self.timer_logic.end_timestamp - now_mono)
            end_epoch = time.time() + rem
            end_time_str = time.strftime("%I:%M %p", time.localtime(end_epoch))
            self.expanded_view.set_ends_text(f"Ends {end_time_str}")
            # Spec 6.4: Starting the timer auto-collapses to the pill
            self.collapse()
        else:
            # Paused: ruler unlocks again (Req 2)
            self.expanded_view.update_display(self.timer_logic.remaining_seconds, is_running=False, is_finished=False)
            self.expanded_view.ruler.set_locked(False)
            self.expanded_view.ruler.set_minutes(self.timer_logic.remaining_seconds / 60.0, emit_signal=False)
            self.expanded_view.set_ends_text("")
            self.update()

    def _on_reset_clicked(self) -> None:
        self._stop_pulse()
        self.timer_logic.reset()
        # Spec 6.4: Reset returns to last chosen duration and expands the card
        self.expanded_view.ruler.set_locked(False)
        self.expanded_view.ruler.set_minutes(self.timer_logic.total_duration / 60.0, emit_signal=False)
        self.expanded_view.update_display(self.timer_logic.total_duration, is_running=False, is_finished=False)
        self.expanded_view.set_ends_text("")
        self.expand()
        self.update()

    def _on_duration_changed(self, total_seconds: float) -> None:
        self._stop_pulse()
        # Single source of truth: updates timer immediately (Req 3a, 3g)
        self.timer_logic.set_duration(total_seconds)
        self.expanded_view.update_display(
            total_seconds,
            is_running=False,
            is_finished=False,
        )
        self.update()

    def _on_timer_finished(self) -> None:
        # Spec 6.4: Finishing auto-expands and shows the done state
        # Spec 9: Done state pulses and beeps, and the card expands automatically
        self.expanded_view.ruler.set_locked(False)
        self.expanded_view.ruler.set_minutes(self.timer_logic.total_duration / 60.0, emit_signal=False)
        self.expanded_view.set_ends_text("")
        self.expand()
        self._start_pulse()
        self._play_beep()

    def _play_beep(self) -> None:
        """Plays a gentle, non-blocking notification chime."""
        def beep_worker():
            if winsound:
                try:
                    winsound.Beep(880, 160)
                    winsound.Beep(1175, 260)
                except Exception:
                    try:
                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
                    except Exception:
                        pass
            else:
                QApplication.beep()

        threading.Thread(target=beep_worker, daemon=True).start()

    def _start_pulse(self) -> None:
        if self._pulse_anim is None:
            self._pulse_anim = QVariantAnimation(self)
            self._pulse_anim.setDuration(1200)
            self._pulse_anim.setLoopCount(4)  # 4 gentle pulses
            self._pulse_anim.setStartValue(0)
            self._pulse_anim.setKeyValueAt(0.5, 140)
            self._pulse_anim.setEndValue(0)
            self._pulse_anim.valueChanged.connect(self._on_pulse_step)
            self._pulse_anim.finished.connect(self._stop_pulse)
        self._pulse_anim.start()

    def _on_pulse_step(self, val: int) -> None:
        self._pulse_alpha = val
        self.update()

    def _stop_pulse(self) -> None:
        if self._pulse_anim and self._pulse_anim.state() == QVariantAnimation.State.Running:
            self._pulse_anim.stop()
        self._pulse_alpha = 0
        self.update()

    # --------------------------------------------------------------------------
    # Custom Painting: Shadow, Black Capsule & Collapsed Pill
    # --------------------------------------------------------------------------
    def _calc_current_radius(self) -> float:
        """Interpolates corner radius smoothly between pill (h/2) and card (28px)."""
        collapsed_r = config.COLLAPSED_SIZE[1] / 2.0
        expanded_r = 28.0
        return (1.0 - self._morph_progress) * collapsed_r + self._morph_progress * expanded_r

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        p = config.SHADOW_PADDING
        capsule_rect = QRectF(p, p, self.width() - 2 * p, self.height() - 2 * p)
        radius = self._calc_current_radius()

        # 1. Subtle drop shadow painted in transparent padding
        for i in range(1, p):
            alpha = int(22 * ((p - i) / p) ** 1.8)
            if alpha <= 0:
                continue
            shadow_rect = capsule_rect.adjusted(-i, -i + 2, i, i + 2)
            shadow_radius = radius + i * 0.5
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(shadow_rect, shadow_radius, shadow_radius)

        # 2. Done pulse glow (gentle orange/red halo when finished)
        if self._pulse_alpha > 0:
            glow_pen = QPen(QColor(255, 69, 58, self._pulse_alpha), 2.5)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(capsule_rect.adjusted(-1, -1, 1, 1), radius + 1, radius + 1)

        # 3. Solid pure-black capsule surface (#000000)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(config.SURFACE_COLOR))
        painter.drawRoundedRect(capsule_rect, radius, radius)

        # 4. Optional subtle fill progress style
        if config.PROGRESS_STYLE == "fill" and self.timer_logic.progress > 0:
            fill_w = capsule_rect.width() * self.timer_logic.progress
            fill_rect = QRectF(capsule_rect.left(), capsule_rect.top(), fill_w, capsule_rect.height())
            painter.save()
            clip_path = QPainterPath()
            clip_path.addRoundedRect(capsule_rect, radius, radius)
            painter.setClipPath(clip_path)
            painter.setBrush(QColor(255, 159, 10, 18))
            painter.drawRect(fill_rect)
            painter.restore()

        # 5. Collapsed state content (fades out as morph_progress increases)
        if self._morph_progress < 0.4:
            fade_factor = (0.4 - self._morph_progress) / 0.4
            self._paint_collapsed_content(painter, capsule_rect, fade_factor)

    def _paint_collapsed_content(self, painter: QPainter, rect: QRectF, alpha_factor: float) -> None:
        """
        Paints the iOS Dynamic Island collapsed pill:
        Left: thin progress ring with accent dot and 'Timer' label in orange.
        Right: formatted time string in orange tabular numbers.
        """
        alpha = int(255 * alpha_factor)
        orange = QColor(config.ACCENT)
        orange.setAlpha(alpha)

        cy = rect.center().y()

        # Left: Progress ring + dot
        ring_x = rect.left() + 16.0
        ring_r = 7.5
        ring_rect = QRectF(ring_x - ring_r, cy - ring_r, ring_r * 2.0, ring_r * 2.0)

        # Track ring
        track_color = QColor(config.ACCENT_MUTED)
        track_color.setAlpha(int(140 * alpha_factor))
        painter.setPen(QPen(track_color, 1.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ring_rect)

        # Active progress arc
        if config.PROGRESS_STYLE == "ring":
            progress = self.timer_logic.progress
            if progress > 0:
                span_angle = int(progress * 360 * 16)
                painter.setPen(QPen(orange, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawArc(ring_rect, 90 * 16, -span_angle)

        # Center dot
        dot_r = 2.4
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(orange)
        painter.drawEllipse(QPointF(ring_x, cy), dot_r, dot_r)

        # "Timer" label next to the ring
        label_font = get_tabular_font(11, QFont.Weight.DemiBold)
        painter.setFont(label_font)
        painter.setPen(orange)
        label_rect = QRectF(ring_x + ring_r + 6.0, rect.top(), 50.0, rect.height())
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "Timer")

        # Right: remaining time in orange tabular numbers
        time_str = self.timer_logic.format_time()
        time_font = get_tabular_font(13, QFont.Weight.DemiBold)
        painter.setFont(time_font)
        painter.setPen(orange)
        time_rect = QRectF(rect.right() - 80.0, rect.top(), 64.0, rect.height())
        painter.drawText(time_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, time_str)


def main():
    app = QApplication(sys.argv)
    # Ensure app closes when the window closes
    app.setQuitOnLastWindowClosed(True)

    # Launch expanded card by default (idle state), click or starting timer collapses to pill
    window = DynamicIslandTimer(initial_expanded=True)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

