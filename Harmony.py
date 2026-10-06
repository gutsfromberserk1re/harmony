import sys

import os

os.environ["YTDLP_NO_LAZY_EXTRACTORS"] = "1"

import json

import math

import ctypes

import threading

# Quiet the noisy FFmpeg/Qt multimedia debug output (best effort, must be set before QApplication)

os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg*=false")

from PySide6.QtCore import (

    Qt, QObject, QEvent, Signal, QUrl, QTimer, QRectF, QVariantAnimation,

    QPropertyAnimation, QEasingCurve, Property, QSettings

)

from PySide6.QtGui import (

    QFont, QPainter, QColor, QPen, QBrush, QPainterPath, QPixmap,

    QShortcut, QKeySequence, QIcon

)

from PySide6.QtWidgets import (

    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,

    QPushButton, QLabel, QMenu, QDialog, QLineEdit, QSlider, QTreeWidget,

    QTreeWidgetItem, QGraphicsDropShadowEffect, QStyle, QSizePolicy, QAbstractItemView

)

from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

import yt_dlp

SIDEBAR_WIDTH = 210

MAX_RETRIES = 3

# --- COLOR THEMES (alpha is controlled separately by the transparency setting) ---

THEMES = {

    "Pink": {"accent": QColor(255, 182, 193), "accent_hex": "#ffb6c1",

           "bg": QColor(18, 10, 14), "sidebar_bg": QColor(10, 5, 8)},

    "Blue": {"accent": QColor(135, 206, 235), "accent_hex": "#87ceeb",

           "bg": QColor(10, 14, 20), "sidebar_bg": QColor(5, 8, 12)},

    "Green": {"accent": QColor(144, 238, 144), "accent_hex": "#90ee90",

            "bg": QColor(10, 18, 12), "sidebar_bg": QColor(5, 10, 7)},

    "Black": {"accent": QColor(220, 220, 220), "accent_hex": "#dcdcdc",

            "bg": QColor(12, 12, 12), "sidebar_bg": QColor(6, 6, 6)},

    "Purple": {"accent": QColor(187, 134, 252), "accent_hex": "#bb86fc",

             "bg": QColor(16, 10, 24), "sidebar_bg": QColor(9, 5, 15)},

    "Deep Blue": {"accent": QColor(77, 124, 255), "accent_hex": "#4d7cff",

                "bg": QColor(6, 10, 26), "sidebar_bg": QColor(3, 5, 16)},

    "White": {"accent": QColor(255, 255, 255), "accent_hex": "#ffffff",

            "bg": QColor(14, 14, 16), "sidebar_bg": QColor(7, 7, 9)},

    "Silver": {"accent": QColor(192, 200, 212), "accent_hex": "#c0c8d4",

             "bg": QColor(14, 16, 20), "sidebar_bg": QColor(8, 9, 12)},

    "Red": {"accent": QColor(255, 99, 110), "accent_hex": "#ff636e",

          "bg": QColor(22, 8, 10), "sidebar_bg": QColor(13, 4, 6)},

    "Orange": {"accent": QColor(255, 167, 88), "accent_hex": "#ffa758",

             "bg": QColor(22, 14, 8), "sidebar_bg": QColor(13, 8, 4)},

    "Yellow": {"accent": QColor(255, 224, 102), "accent_hex": "#ffe066",

             "bg": QColor(22, 20, 8), "sidebar_bg": QColor(13, 12, 4)},

    "Teal": {"accent": QColor(64, 224, 208), "accent_hex": "#40e0d0",

           "bg": QColor(6, 20, 20), "sidebar_bg": QColor(3, 12, 12)},

    "Lavender": {"accent": QColor(200, 180, 255), "accent_hex": "#c8b4ff",

               "bg": QColor(16, 12, 24), "sidebar_bg": QColor(9, 7, 15)},

    "Crimson": {"accent": QColor(220, 20, 60), "accent_hex": "#dc143c",

              "bg": QColor(20, 6, 10), "sidebar_bg": QColor(11, 3, 6)},

    "Gold": {"accent": QColor(212, 175, 55), "accent_hex": "#d4af37",

           "bg": QColor(20, 16, 8), "sidebar_bg": QColor(11, 9, 4)},

    "Mint": {"accent": QColor(152, 255, 204), "accent_hex": "#98ffcc",

           "bg": QColor(8, 20, 16), "sidebar_bg": QColor(4, 12, 9)},

}

# Window background alpha presets (0-255)

OPACITY_PRESETS = [("Clear", 70), ("Glass", 110), ("Frosted", 160), ("Solid", 225)]

DEFAULT_ALPHA = 110


# ----------------------------------------------------------------- helpers

def resource_path(relative_path):

    """Return the absolute path to a bundled or development resource."""

    if getattr(sys, "frozen", False):

        base_dir = os.path.dirname(os.path.abspath(sys.executable))

    else:

        base_dir = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_dir, relative_path)


def mono(size=10, bold=False):

    f = QFont()

    f.setFamilies(["JetBrains Mono", "Cascadia Mono", "Consolas", "monospace"])

    f.setPointSize(size)

    f.setBold(bold)

    return f


def make_glow(color, blur=20):

    fx = QGraphicsDropShadowEffect()

    fx.setBlurRadius(blur)

    fx.setColor(color)

    fx.setOffset(0, 0)

    return fx


def fmt_time(seconds):

    h, rem = divmod(int(seconds), 3600)

    m, s = divmod(rem, 60)

    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def scrollbar_qss(hex_color):

    c = QColor(hex_color)

    r, g, b = c.red(), c.green(), c.blue()

    return f"""

        QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px 0; border: none; }}

        QScrollBar::handle:vertical {{

            background: rgba({r},{g},{b},90); min-height: 28px; border-radius: 3px; margin: 0 1px;

        }}

        QScrollBar::handle:vertical:hover {{ background: rgba({r},{g},{b},170); }}

        QScrollBar::handle:vertical:pressed {{ background: {hex_color}; }}

        QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0 2px; border: none; }}

        QScrollBar::handle:horizontal {{

            background: rgba({r},{g},{b},90); min-width: 28px; border-radius: 3px; margin: 1px 0;

        }}

        QScrollBar::handle:horizontal:hover {{ background: rgba({r},{g},{b},170); }}

        QScrollBar::handle:horizontal:pressed {{ background: {hex_color}; }}

        QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; background: none; border: none; }}

        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

        QAbstractScrollArea::corner {{ background: transparent; }}

    """


# ----------------------------------------------------------------- background work

class Bridge(QObject):

    """Lets plain daemon threads hand results to the Qt main thread."""

    playlist_ready = Signal(int, list)

    stream_ready = Signal(int, str)


def fetch_playlist(bridge, req, url):

    tracks = []

    opts = {

        'extract_flat': 'in_playlist', 'skip_download': True, 'quiet': True,

        'no_warnings': True, 'ignoreerrors': True, 'cachedir': False,

        'socket_timeout': 15, 'retries': 3,

    }

    try:

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(url, download=False)

            if info:

                entries = info.get('entries')

                if entries is None:           # single video link

                    entries = [info]

                for e in entries:

                    if not e or not e.get('id'):

                        continue

                    title = e.get('title') or 'Unknown Track'

                    if title in ('[Private video]', '[Deleted video]'):

                        continue

                    dur = e.get('duration') or 0

                    tracks.append({

                        'id': e['id'],

                        'title': title,

                        'duration_str': fmt_time(dur) if dur else '--:--',

                        'url': f"https://www.youtube.com/watch?v={e['id']}",

                    })

    except Exception:

        pass

    bridge.playlist_ready.emit(req, tracks)


def fetch_stream(bridge, req, url):

    opts = {

        'format': 'bestaudio/best', 'quiet': True, 'no_warnings': True,

        'noplaylist': True, 'cachedir': False, 'socket_timeout': 15, 'retries': 3,

    }

    stream = ''

    try:

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(url, download=False)

            stream = (info or {}).get('url', '') or ''

    except Exception:

        pass

    bridge.stream_ready.emit(req, stream)


# ----------------------------------------------------------------- widgets

class SlidingSidebar(QWidget):

    """Outer width is animated; inner panel keeps a fixed width so contents never reflow."""

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedWidth(SIDEBAR_WIDTH)

        self.panel = QWidget(self)

        self.panel.setFixedWidth(SIDEBAR_WIDTH)

        self.panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def resizeEvent(self, event):

        self.panel.setGeometry(0, 0, SIDEBAR_WIDTH, self.height())

        super().resizeEvent(event)

    def get_slide_width(self):

        return self.width()

    def set_slide_width(self, w):

        self.setFixedWidth(max(0, int(w)))

        p = self.parentWidget()

        if p:

            p.update()

    slide_width = Property(int, get_slide_width, set_slide_width)


class VectorButton(QPushButton):

    def __init__(self, icon_type, parent=None):

        super().__init__(parent)

        self.icon_type = icon_type

        self.active = False

        self.accent_color = QColor(255, 182, 193)

        self.setFixedSize(36, 36)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_color(self, color):

        self.accent_color = color

        self.update()

    def set_active(self, active):

        if self.active != active:

            self.active = active

            self.update()

    def set_icon(self, icon_type):

        if self.icon_type != icon_type:

            self.icon_type = icon_type

            self.update()

    def enterEvent(self, e):

        self.update()

        super().enterEvent(e)

    def leaveEvent(self, e):

        self.update()

        super().leaveEvent(e)

    def paintEvent(self, event):

        p = QPainter(self)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        c = self.accent_color

        color = c if (self.active or self.underMouse()) else QColor(c.red(), c.green(), c.blue(), 180)

        p.setPen(Qt.PenStyle.NoPen)

        p.setBrush(QBrush(color))

        cx, cy = self.width() / 2.0, self.height() / 2.0

        if self.icon_type == 'play':

            path = QPainterPath()

            path.moveTo(cx - 5, cy - 8); path.lineTo(cx + 8, cy); path.lineTo(cx - 5, cy + 8)

            path.closeSubpath()

            p.drawPath(path)

        elif self.icon_type == 'pause':

            p.drawRoundedRect(QRectF(cx - 6, cy - 8, 4, 16), 1, 1)

            p.drawRoundedRect(QRectF(cx + 2, cy - 8, 4, 16), 1, 1)

        elif self.icon_type == 'next':

            path = QPainterPath()

            path.moveTo(cx - 7, cy - 7); path.lineTo(cx + 1, cy); path.lineTo(cx - 7, cy + 7)

            path.closeSubpath()

            p.drawPath(path)

            p.drawRoundedRect(QRectF(cx + 2, cy - 7, 3, 14), 1, 1)

        elif self.icon_type == 'prev':

            path = QPainterPath()

            path.moveTo(cx + 7, cy - 7); path.lineTo(cx - 1, cy); path.lineTo(cx + 7, cy + 7)

            path.closeSubpath()

            p.drawPath(path)

            p.drawRoundedRect(QRectF(cx - 5, cy - 7, 3, 14), 1, 1)

        elif self.icon_type == 'repeat':

            p.setPen(QPen(color, 2))

            p.setBrush(Qt.BrushStyle.NoBrush)

            p.drawArc(QRectF(cx - 7, cy - 7, 14, 14), 40 * 16, 280 * 16)

            p.setPen(Qt.PenStyle.NoPen)

            p.setBrush(QBrush(color))

            arrow = QPainterPath()

            arrow.moveTo(cx + 4, cy - 8); arrow.lineTo(cx + 9, cy - 4); arrow.lineTo(cx + 3, cy - 1)

            arrow.closeSubpath()

            p.drawPath(arrow)


class SmoothWaveVisualizer(QWidget):

    WAVES = (

        (0.02, 1.0, 230, 2.2, 0.0),

        (0.035, 0.6, 150, 1.5, 1.2),

        (0.015, 0.4, 90, 1.0, 2.5),

    )

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.is_playing = False

        self.phase = 0.0

        self.amp = 0.05                     # eased amplitude (fraction of height)

        self.accent_color = QColor(255, 182, 193)

        self._env_w = -1

        self._xs = []

        self._env = []

        self.timer = QTimer(self)

        self.timer.timeout.connect(self.animate)

        self.timer.start(33)

    def set_color(self, color):

        self.accent_color = color

    def set_playing(self, playing):

        self.is_playing = playing

    def set_active(self, active):

        if active and not self.timer.isActive():

            self.timer.start(33)

        elif not active:

            self.timer.stop()

    def animate(self):

        target = 0.35 if self.is_playing else 0.05

        self.amp += (target - self.amp) * 0.1          # smooth transition instead of snapping

        self.phase += 0.165 if self.is_playing else 0.04

        self.update()

    def _build_cache(self, w):

        self._env_w = w

        self._xs = list(range(0, w + 1, 3))

        self._env = [math.sin((x / w) * math.pi) for x in self._xs] if w > 0 else []

    def paintEvent(self, event):

        w, h = self.width(), self.height()

        if w <= 0:

            return

        if w != self._env_w:

            self._build_cache(w)

        p = QPainter(self)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        mid = h / 2.0

        base = h * self.amp

        ac = self.accent_color

        for freq, mult, alpha, width, shift in self.WAVES:

            path = QPainterPath()

            path.moveTo(0, mid)

            amp = base * mult

            ph = self.phase + shift

            for x, env in zip(self._xs, self._env):

                path.lineTo(x, mid + math.sin(x * freq + ph) * amp * env)

            p.setPen(QPen(QColor(ac.red(), ac.green(), ac.blue(), alpha), width))

            p.setBrush(Qt.BrushStyle.NoBrush)

            p.drawPath(path)


class ScrollableVolumeWidget(QLabel):

    volume_changed = Signal(float)

    def __init__(self, initial_volume=0.8, parent=None):

        super().__init__(parent)

        self.volume = initial_volume

        self.setFont(mono(10))

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setToolTip("Scroll wheel (or Up/Down keys) to adjust volume")

        self.setFixedWidth(100)

        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.refresh()

    def refresh(self):

        self.setText("VOL MUTE" if self.volume <= 0.01 else f"VOL {int(round(self.volume * 100))}%")

    def set_volume(self, v):

        self.volume = max(0.0, min(1.0, v))

        self.refresh()

    def wheelEvent(self, event):

        step = 0.05 if event.angleDelta().y() > 0 else -0.05

        self.set_volume(self.volume + step)

        self.volume_changed.emit(self.volume)

        event.accept()


class ClickSlider(QSlider):

    """Jump-to-click slider; seeks only on release (avoids spamming a network stream)."""

    def _val_at(self, x):

        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), int(x), max(1, self.width()))

    def mousePressEvent(self, e):

        if e.button() == Qt.MouseButton.LeftButton and self.maximum() > 0:

            self.setSliderDown(True)

            v = self._val_at(e.position().x())

            self.setValue(v)

            self.sliderMoved.emit(v)

            e.accept()

        else:

            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):

        if self.isSliderDown():

            v = self._val_at(e.position().x())

            self.setValue(v)

            self.sliderMoved.emit(v)

            e.accept()

        else:

            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):

        if self.isSliderDown():

            self.setSliderDown(False)

            self.sliderReleased.emit()

            e.accept()

        else:

            super().mouseReleaseEvent(e)


class ClickableLabel(QLabel):

    clicked = Signal()

    def mousePressEvent(self, e):

        if e.button() == Qt.MouseButton.LeftButton:

            self.clicked.emit()

            e.accept()


class CustomDialog(QDialog):

    def __init__(self, title, label_text, theme, parent=None):

        super().__init__(parent)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedSize(360, 160)

        self.accent = theme["accent_hex"]

        self.accent_color = QColor(theme["accent"])

        layout = QVBoxLayout(self)

        layout.setContentsMargins(20, 15, 20, 15)

        title_lbl = QLabel(title)

        title_lbl.setFont(mono(11, True))

        title_lbl.setStyleSheet(f"color: {self.accent}; background: transparent;")

        msg_lbl = QLabel(label_text)

        msg_lbl.setFont(mono(9))

        msg_lbl.setStyleSheet("color: #d0d0d0; background: transparent;")

        self.input_field = QLineEdit()

        self.input_field.setFont(mono(10))

        self.input_field.setStyleSheet(f"""

            QLineEdit {{

                background: rgba(0, 0, 0, 0.6); color: #ffffff;

                border: 1px solid {self.accent}; border-radius: 4px; padding: 4px 8px;

            }}

        """)

        self.input_field.returnPressed.connect(self.accept)

        btn_box = QHBoxLayout()

        btn_ok, btn_cancel = QPushButton("OK"), QPushButton("Cancel")

        for b in (btn_ok, btn_cancel):

            b.setFont(mono(9))

            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            b.setAutoDefault(False)

            b.setStyleSheet(f"""

                QPushButton {{ background: transparent; color: {self.accent};

                    border: 1px solid {self.accent}; border-radius: 4px; padding: 4px 14px; }}

                QPushButton:hover {{ background: {self.accent}; color: #000000; }}

            """)

        btn_ok.clicked.connect(self.accept)

        btn_cancel.clicked.connect(self.reject)

        btn_box.addStretch()

        btn_box.addWidget(btn_ok)

        btn_box.addWidget(btn_cancel)

        layout.addWidget(title_lbl)

        layout.addWidget(msg_lbl)

        layout.addWidget(self.input_field)

        layout.addLayout(btn_box)

        self.input_field.setFocus()

    def paintEvent(self, event):

        p = QPainter(self)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.setBrush(QBrush(QColor(15, 20, 28, 235)))

        c = self.accent_color

        p.setPen(QPen(QColor(c.red(), c.green(), c.blue(), 120), 1))

        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)


class CustomTitleBar(QWidget):

    def __init__(self, theme, parent):

        super().__init__(parent)

        self.parent_window = parent

        self.setFixedHeight(36)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QHBoxLayout(self)

        layout.setContentsMargins(12, 0, 12, 0)

        self.app_icon_label = ClickableLabel()

        self.app_icon_label.setFixedSize(20, 20)

        self.app_icon_label.setScaledContents(True)

        self.app_icon_label.setCursor(Qt.CursorShape.PointingHandCursor)

        self.app_icon_label.setToolTip("Toggle playlists")

        self.app_icon_label.clicked.connect(parent.toggle_sidebar)

        self._set_icon(theme)

        self.title_label = QLabel("Harmony")

        self.title_label.setFont(mono(10, True))

        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_fx = make_glow(theme["accent"], 15)

        self.title_label.setGraphicsEffect(self.title_fx)

        self.btn_min = QPushButton("–")

        self.btn_close = QPushButton("✕")

        for b in (self.btn_min, self.btn_close):

            b.setFont(mono(10))

            b.setFixedSize(28, 24)

            b.setCursor(Qt.CursorShape.PointingHandCursor)

            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.btn_min.clicked.connect(parent.showMinimized)

        self.btn_close.clicked.connect(parent.close)

        layout.addWidget(self.app_icon_label)

        layout.addStretch()

        layout.addWidget(self.title_label)

        layout.addStretch()

        layout.addWidget(self.btn_min)

        layout.addWidget(self.btn_close)

        self.apply_theme(theme)

    def _set_icon(self, theme):

        icon_path = resource_path("harmony.ico")

        if os.path.exists(icon_path):

            self.app_icon_label.setPixmap(QPixmap(icon_path))

            return

        pm = QPixmap(20, 20)

        pm.fill(Qt.GlobalColor.transparent)

        p = QPainter(pm)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.setBrush(theme["accent"])

        p.setPen(Qt.PenStyle.NoPen)

        p.drawEllipse(2, 2, 16, 16)

        p.end()

        self.app_icon_label.setPixmap(pm)

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            handle = self.window().windowHandle()

            if handle:

                handle.startSystemMove()

            event.accept()

    def apply_theme(self, theme):

        hx = theme["accent_hex"]

        self.title_label.setStyleSheet(f"color: {hx}; background: transparent;")

        self.title_fx.setColor(theme["accent"])

        self._set_icon(theme)

        self.btn_min.setStyleSheet(f"""

            QPushButton {{ background: transparent; color: {hx}; border: none; }}

            QPushButton:hover {{ color: #ffffff; background: rgba(255,255,255,0.12); border-radius: 4px; }}

        """)

        self.btn_close.setStyleSheet(f"""

            QPushButton {{ background: transparent; color: {hx}; border: none; }}

            QPushButton:hover {{ color: #ff5555; background: rgba(255,85,85,0.2); border-radius: 4px; }}

        """)


# ----------------------------------------------------------------- main window

class AudioPlayer(QWidget):

    def __init__(self):

        super().__init__()

        self.settings = QSettings("Kiyo_Kumo_Ltd", "Harmony")

        saved_theme = self.settings.value("theme_name", "Pink", type=str)

        self.current_theme_name = saved_theme if saved_theme in THEMES else "Pink"

        self.theme = THEMES[self.current_theme_name]

        self.bg_alpha = self.settings.value("bg_alpha", DEFAULT_ALPHA, type=int)

        self.playlists = self._load_playlists()

        self.current_playlist_name = ""

        self.tracks = []            # tracks shown in the list

        self.queue = []             # tracks actually being played (kept when browsing other playlists)

        self.current_index = -1

        self.is_repeating = False

        self.sidebar_expanded = True

        self._playlist_req = 0

        self._stream_req = 0

        self._resume_ms = 0

        self._retries = 0

        self._last_retry_pos = 0

        self._last_sec = -1

        self._glow_row = -1

        self.bridge = Bridge(self)

        self.bridge.playlist_ready.connect(self.populate_tracks)

        self.bridge.stream_ready.connect(self.start_stream)

        self.media_player = QMediaPlayer(self)

        self.audio_output = QAudioOutput(self)

        self.media_player.setAudioOutput(self.audio_output)

        self.audio_output.setVolume(max(0.0, min(1.0, self.settings.value("volume", 0.8, type=float))))

        self._vol_save_timer = QTimer(self)

        self._vol_save_timer.setSingleShot(True)

        self._vol_save_timer.setInterval(500)

        self._vol_save_timer.timeout.connect(

            lambda: self.settings.setValue("volume", self.audio_output.volume()))

        self.setup_window()

        self.enable_window_blur_and_corners()

        self.setup_ui()

        self.setup_breathing_animation()

        self.setup_shortcuts()

        self.update_sidebar_tree()

    # ---- setup

    def setup_window(self):

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self.setWindowTitle("Harmony")

        self.resize(820, 500)

        self.setMinimumSize(640, 420)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        icon_path = resource_path("harmony.ico")

        if os.path.exists(icon_path):

            self.setWindowIcon(QIcon(icon_path))

    def enable_window_blur_and_corners(self):

        if sys.platform != "win32":

            return

        try:

            hwnd = int(self.winId())

            pref = ctypes.c_int(2)  # DWMWCP_ROUND

            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))

            class ACCENT_POLICY(ctypes.Structure):

                _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),

                            ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]

            class WCAD(ctypes.Structure):

                _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p),

                            ("SizeOfData", ctypes.c_size_t)]

            accent = ACCENT_POLICY()

            accent.AccentState = 3          # blur behind

            accent.GradientColor = 0x00000000

            data = WCAD()

            data.Attribute = 19

            data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)

            data.SizeOfData = ctypes.sizeof(accent)

            ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))

        except Exception:

            pass

    def setup_breathing_animation(self):

        self.glow_anim = QVariantAnimation(self)

        self.glow_anim.setKeyValueAt(0.0, 110)

        self.glow_anim.setKeyValueAt(0.5, 255)

        self.glow_anim.setKeyValueAt(1.0, 110)       # symmetric: no hard jump at loop end

        self.glow_anim.setDuration(2000)

        self.glow_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        self.glow_anim.setLoopCount(-1)

        self.glow_anim.valueChanged.connect(self.update_breathing_light)

    def setup_shortcuts(self):

        def add(seq, fn):

            sc = QShortcut(QKeySequence(seq), self)

            sc.setContext(Qt.ShortcutContext.WindowShortcut)

            sc.activated.connect(fn)

        add(Qt.Key.Key_Space, self.toggle_play)

        add(Qt.Key.Key_Up, lambda: self.adjust_volume(0.05))

        add(Qt.Key.Key_Down, lambda: self.adjust_volume(-0.05))

        add(Qt.Key.Key_Left, lambda: self.seek_by(-10000))

        add(Qt.Key.Key_Right, lambda: self.seek_by(10000))

        add(Qt.Key.Key_Plus, self.add_playlist)

        add(Qt.Key.Key_Equal, self.add_playlist)

    def setup_ui(self):

        main_layout = QVBoxLayout(self)

        main_layout.setContentsMargins(0, 0, 0, 0)

        main_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self.theme, self)

        main_layout.addWidget(self.title_bar)

        body = QHBoxLayout()

        body.setContentsMargins(0, 0, 0, 0)

        body.setSpacing(0)

        # --- sidebar

        self.sidebar = SlidingSidebar()

        sidebar_layout = QVBoxLayout(self.sidebar.panel)

        sidebar_layout.setContentsMargins(12, 10, 12, 12)

        title_box = QHBoxLayout()

        sb_lbl = QLabel("PLAYLISTS")

        sb_lbl.setFont(mono(9, True))

        btn_add = QPushButton("+")

        btn_add.setFont(mono(12, True))

        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_add.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        btn_add.clicked.connect(self.add_playlist)

        title_box.addWidget(sb_lbl)

        title_box.addStretch()

        title_box.addWidget(btn_add)

        self.playlist_tree = QTreeWidget()

        self.playlist_tree.setHeaderHidden(True)

        self.playlist_tree.setFont(mono(9))

        self.playlist_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.playlist_tree.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self.playlist_tree.itemDoubleClicked.connect(self.on_tree_item_double_clicked)

        sidebar_layout.addLayout(title_box)

        sidebar_layout.addWidget(self.playlist_tree)

        self.sidebar_anim = QPropertyAnimation(self.sidebar, b"slide_width", self)

        self.sidebar_anim.setDuration(280)

        self.sidebar_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.sidebar_anim.finished.connect(self._on_sidebar_anim_done)

        # --- workspace

        self.workspace = QWidget()

        self.workspace.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        ws = QVBoxLayout(self.workspace)

        ws.setContentsMargins(20, 10, 20, 15)

        top = QHBoxLayout()

        pl_box = QVBoxLayout()

        self.playlist_label = QLabel("No Playlist Selected")

        self.playlist_label.setFont(mono(14, True))

        self.playlist_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        self.label_fx = make_glow(self.theme["accent"], 18)

        self.playlist_label.setGraphicsEffect(self.label_fx)

        self.now_label = QLabel("")

        self.now_label.setFont(mono(9))

        self.now_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        self.playlist_widget = QListWidget()

        self.playlist_widget.setFont(mono(10))

        self.playlist_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.playlist_widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self.playlist_widget.setTextElideMode(Qt.TextElideMode.ElideRight)

        self.playlist_widget.itemDoubleClicked.connect(self.on_track_selected)

        pl_box.addWidget(self.playlist_label)

        pl_box.addWidget(self.now_label)

        pl_box.addWidget(self.playlist_widget)

        self.visualizer = SmoothWaveVisualizer()

        self.visualizer.setFixedSize(220, 140)

        top.addLayout(pl_box, stretch=3)

        top.addWidget(self.visualizer, stretch=0,

                      alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        progress = QHBoxLayout()

        self.time_current = QLabel("00:00")

        self.time_total = QLabel("00:00")

        for lbl in (self.time_current, self.time_total):

            lbl.setFont(mono(8))

        self.progress_slider = ClickSlider(Qt.Orientation.Horizontal)

        self.progress_slider.setRange(0, 0)

        self.progress_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.progress_slider.sliderMoved.connect(self.on_slider_moved)

        self.progress_slider.sliderReleased.connect(self.on_slider_released)

        progress.addWidget(self.time_current)

        progress.addWidget(self.progress_slider)

        progress.addWidget(self.time_total)

        bottom = QHBoxLayout()

        spacer = QWidget()

        spacer.setFixedWidth(100)

        spacer.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        controls = QHBoxLayout()

        self.btn_repeat = VectorButton('repeat')

        self.btn_prev = VectorButton('prev')

        self.btn_play = VectorButton('play')

        self.btn_next = VectorButton('next')

        self.btn_repeat.clicked.connect(self.toggle_repeat)

        self.btn_prev.clicked.connect(self.play_previous)

        self.btn_play.clicked.connect(self.toggle_play)

        self.btn_next.clicked.connect(self.play_next)

        for i, b in enumerate((self.btn_repeat, self.btn_prev, self.btn_play, self.btn_next)):

            if i:

                controls.addSpacing(10)

            controls.addWidget(b)

        self.volume_widget = ScrollableVolumeWidget(initial_volume=self.audio_output.volume())

        self.volume_widget.volume_changed.connect(self.set_volume)

        self.volume_fx = make_glow(self.theme["accent"], 12)

        self.volume_widget.setGraphicsEffect(self.volume_fx)

        bottom.addWidget(spacer)

        bottom.addStretch()

        bottom.addLayout(controls)

        bottom.addStretch()

        bottom.addWidget(self.volume_widget)

        ws.addLayout(top)

        ws.addSpacing(10)

        ws.addLayout(progress)

        ws.addSpacing(10)

        ws.addLayout(bottom)

        body.addWidget(self.sidebar)

        body.addWidget(self.workspace, 1)

        main_layout.addLayout(body, 1)

        mp = self.media_player

        mp.positionChanged.connect(self.update_position)

        mp.durationChanged.connect(self.update_duration)

        mp.mediaStatusChanged.connect(self.on_media_status)

        mp.playbackStateChanged.connect(self.on_playback_state)

        mp.errorOccurred.connect(self.on_player_error)

        self.apply_theme_ui()

    # ---- window behaviour

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            handle = self.windowHandle()

            if handle:

                handle.startSystemMove()

            event.accept()

    def changeEvent(self, event):

        # Don't burn CPU animating the visualizer while minimized

        if event.type() == QEvent.Type.WindowStateChange:

            self.visualizer.set_active(not self.isMinimized())

        super().changeEvent(event)

    def closeEvent(self, event):

        self.media_player.stop()

        self.settings.setValue("volume", self.audio_output.volume())

        self.settings.sync()

        super().closeEvent(event)

    def paintEvent(self, event):

        p = QPainter(self)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        path = QPainterPath()

        path.addRoundedRect(QRectF(0, 0, w, h), 14, 14)

        bg = QColor(self.theme["bg"])

        bg.setAlpha(self.bg_alpha)

        p.fillPath(path, QBrush(bg))

        sbw = self.sidebar.width()

        if sbw > 0:

            rect = QPainterPath()

            rect.addRect(0, 0, sbw, h)

            sb = QColor(self.theme["sidebar_bg"])

            sb.setAlpha(min(255, int(self.bg_alpha * 0.6) + 25))

            p.fillPath(path.intersected(rect), QBrush(sb))

        ac = self.theme["accent"]

        p.setPen(QPen(QColor(ac.red(), ac.green(), ac.blue(), 45), 1))

        p.setBrush(Qt.BrushStyle.NoBrush)

        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 14, 14)

    # ---- sidebar

    def toggle_sidebar(self):

        self.sidebar_anim.stop()

        self.sidebar_expanded = not self.sidebar_expanded

        if self.sidebar_expanded:

            self.sidebar.show()

        self.sidebar_anim.setStartValue(self.sidebar.width())

        self.sidebar_anim.setEndValue(SIDEBAR_WIDTH if self.sidebar_expanded else 0)

        self.sidebar_anim.start()

    def _on_sidebar_anim_done(self):

        if not self.sidebar_expanded:

            self.sidebar.hide()

    # ---- theme

    def apply_theme_ui(self):

        hx = self.theme["accent_hex"]

        ac = self.theme["accent"]

        sb_qss = scrollbar_qss(hx)

        self.title_bar.apply_theme(self.theme)

        self.visualizer.set_color(ac)

        for b in (self.btn_repeat, self.btn_prev, self.btn_play, self.btn_next):

            b.set_color(ac)

        self.label_fx.setColor(ac)

        self.volume_fx.setColor(ac)

        for w in (self.playlist_label, self.time_current, self.time_total, self.volume_widget):

            w.setStyleSheet(f"color: {hx}; background: transparent;")

        self.now_label.setStyleSheet("color: #a8b8c4; background: transparent;")

        self.sidebar.setStyleSheet(f"""

            QWidget {{ background: transparent; color: {hx}; }}

            QLabel {{ color: {hx}; background: transparent; }}

            QPushButton {{ background: transparent; color: {hx}; border: none; outline: none; }}

            QPushButton:hover {{ color: #ffffff; }}

        """)

        self.playlist_tree.setStyleSheet(f"""

            QTreeWidget {{ background: transparent; border: none; color: #c0d5e5; outline: none; }}

            QTreeWidget::item {{ padding: 4px; }}

            QTreeWidget::item:selected {{

                color: {hx}; background: rgba(255,255,255,0.08); border-radius: 4px;

            }}

            {sb_qss}

        """)

        self.playlist_widget.setStyleSheet(f"""

            QListWidget {{ background: transparent; border: none; color: #c0d5e5; outline: none; }}

            QListWidget::item {{ padding: 5px 0px; border-bottom: 1px solid rgba(255,255,255,0.05); }}

            QListWidget::item:selected {{

                color: {hx}; font-weight: bold; background: rgba(255,255,255,0.08); border-radius: 4px;

            }}

            {sb_qss}

        """)

        self.progress_slider.setStyleSheet(f"""

            QSlider::groove:horizontal {{ height: 4px; background: rgba(255,255,255,0.15); border-radius: 2px; }}

            QSlider::sub-page:horizontal {{ background: {hx}; border-radius: 2px; }}

            QSlider::handle:horizontal {{

                background: {hx}; width: 10px; margin-top: -3px; margin-bottom: -3px; border-radius: 5px;

            }}

        """)

        self.update()

    def change_theme(self, name):

        if name in THEMES:

            self.current_theme_name = name

            self.theme = THEMES[name]

            self.settings.setValue("theme_name", name)

            self.apply_theme_ui()

    def set_transparency(self, alpha):

        self.bg_alpha = alpha

        self.settings.setValue("bg_alpha", alpha)

        self.update()

    def contextMenuEvent(self, event):

        hx = self.theme["accent_hex"]

        menu = QMenu(self)

        menu.setFont(mono(9))

        menu.setStyleSheet(f"""

            QMenu {{ background-color: rgba(12,16,24,225); color: {hx};

                border: 1px solid {hx}; border-radius: 6px; padding: 4px; }}

            QMenu::item {{ padding: 6px 16px; border-radius: 4px; }}

            QMenu::item:selected {{ background-color: rgba(255,255,255,0.15); color: #ffffff; }}

            QMenu::separator {{ height: 1px; background: rgba(255,255,255,0.12); margin: 4px 8px; }}

        """)

        if self.sidebar.width() > 0:

            vp = self.playlist_tree.viewport()

            local = vp.mapFromGlobal(event.globalPos())

            if vp.rect().contains(local):

                item = self.playlist_tree.itemAt(local)

                if item:

                    name = item.data(0, Qt.ItemDataRole.UserRole)

                    act = menu.addAction(f"🗑 Remove '{name}'")

                    act.triggered.connect(lambda c=False, n=name: self.remove_playlist(n))

                    menu.addSeparator()

        theme_menu = menu.addMenu("🎨 Change Theme")

        for t in THEMES:

            theme_menu.addAction(t).triggered.connect(lambda c=False, tn=t: self.change_theme(tn))

        glass_menu = menu.addMenu("🪟 Transparency")

        for label, alpha in OPACITY_PRESETS:

            a = glass_menu.addAction(label)

            a.setCheckable(True)

            a.setChecked(alpha == self.bg_alpha)

            a.triggered.connect(lambda c=False, al=alpha: self.set_transparency(al))

        menu.exec(event.globalPos())

    # ---- playlists

    def _load_playlists(self):

        try:

            data = json.loads(self.settings.value("playlists", "{}", type=str))

            return data if isinstance(data, dict) else {}

        except Exception:

            return {}

    def _save_playlists(self):

        self.settings.setValue("playlists", json.dumps(self.playlists))

    def add_playlist(self):

        d1 = CustomDialog("Playlist Name", "Enter a name for this playlist:", self.theme, self)

        if d1.exec() != QDialog.DialogCode.Accepted:

            return

        name = d1.input_field.text().strip()

        if not name:

            return

        d2 = CustomDialog("YouTube Link", "Paste YouTube Playlist URL:", self.theme, self)

        if d2.exec() != QDialog.DialogCode.Accepted:

            return

        url = d2.input_field.text().strip()

        if not url.lower().startswith(("http://", "https://")):

            return

        self.playlists[name] = url

        self._save_playlists()

        self.update_sidebar_tree()

        self.switch_playlist(name)

    def remove_playlist(self, name):

        if name in self.playlists:

            del self.playlists[name]

            self._save_playlists()

            self.update_sidebar_tree()

            if name == self.current_playlist_name:

                self._playlist_req += 1

                self.current_playlist_name = ""

                self.tracks = []

                self._glow_row = -1

                self.playlist_widget.clear()

                self.playlist_label.setText("No Playlist Selected")

    def update_sidebar_tree(self):

        self.playlist_tree.clear()

        for name in self.playlists:

            item = QTreeWidgetItem(self.playlist_tree, [f"📂 {name}"])

            item.setData(0, Qt.ItemDataRole.UserRole, name)

    def on_tree_item_double_clicked(self, item, column):

        name = item.data(0, Qt.ItemDataRole.UserRole)

        if name:

            self.switch_playlist(name)

    def switch_playlist(self, name):

        if name not in self.playlists:

            return

        self.current_playlist_name = name

        self.playlist_label.setText(name)

        self.tracks = []

        self._glow_row = -1

        self.playlist_widget.clear()

        self.playlist_widget.addItem("Loading tracks...")

        self._playlist_req += 1

        threading.Thread(target=fetch_playlist,

                         args=(self.bridge, self._playlist_req, self.playlists[name]),

                         daemon=True).start()

    def populate_tracks(self, req, tracks):

        if req != self._playlist_req:      # stale result from a previous click

            return

        self.tracks = tracks

        self._glow_row = -1

        self.playlist_widget.setUpdatesEnabled(False)

        self.playlist_widget.clear()

        if not tracks:

            self.playlist_widget.addItem("No tracks found or error loading playlist.")

        else:

            for i, t in enumerate(tracks):

                self.playlist_widget.addItem(QListWidgetItem(f"{i + 1:02d}. {t['title']} [{t['duration_str']}]"))

        self.playlist_widget.setUpdatesEnabled(True)

    def on_track_selected(self, item):

        index = self.playlist_widget.row(item)

        if 0 <= index < len(self.tracks):

            self.queue = self.tracks

            self.play_track(index)

    # ---- playback

    def play_track(self, index, resume_ms=0, retry=False):

        if not (0 <= index < len(self.queue)):

            return

        if not retry:

            self._retries = 0

        self._clear_glow()

        self.current_index = index

        self._resume_ms = resume_ms

        if self.queue is self.tracks:

            self.playlist_widget.setCurrentRow(index)

        track = self.queue[index]

        self.now_label.setText(f"Loading: {track['title']}")

        self._stream_req += 1

        threading.Thread(target=fetch_stream,

                         args=(self.bridge, self._stream_req, track['url']),

                         daemon=True).start()

    def start_stream(self, req, stream_url):

        if req != self._stream_req:

            return

        if not stream_url:

            self._retry_current(self._resume_ms)

            return

        if 0 <= self.current_index < len(self.queue):

            self.now_label.setText(self.queue[self.current_index]['title'])

        self.media_player.setSource(QUrl(stream_url))

        self.media_player.play()

    def _retry_current(self, pos=None):

        """Re-resolve the stream URL (they expire / sockets drop) and resume where we were."""

        if self._retries >= MAX_RETRIES or self.current_index < 0:

            self.now_label.setText("Error: stream unavailable")

            self.media_player.stop()

            return

        self._retries += 1

        if pos is None:

            pos = self.media_player.position()

        self._last_retry_pos = pos

        self.play_track(self.current_index, resume_ms=pos, retry=True)

    def on_player_error(self, error, message=""):

        if error != QMediaPlayer.Error.NoError:

            self._retry_current()

    def on_media_status(self, status):

        MS = QMediaPlayer.MediaStatus

        if status in (MS.LoadedMedia, MS.BufferedMedia) and self._resume_ms > 0:

            self.media_player.setPosition(self._resume_ms)

            self._resume_ms = 0

        elif status == MS.EndOfMedia:

            dur = self.media_player.duration()

            pos = self.media_player.position()

            # Ended far too early => the connection dropped, not a real end of track

            if dur > 0 and pos < dur - 3000 and self._retries < MAX_RETRIES:

                self._retry_current(pos)

                return

            if self.is_repeating and self.current_index >= 0:

                self.media_player.setPosition(0)

                self.media_player.play()

            else:

                self.play_next()

    def on_playback_state(self, state):

        playing = state == QMediaPlayer.PlaybackState.PlayingState

        self.btn_play.set_icon('pause' if playing else 'play')

        self.btn_play.set_active(playing)

        self.visualizer.set_playing(playing)

        if playing:

            if self.glow_anim.state() != QVariantAnimation.State.Running:

                self.glow_anim.start()

        else:

            self.glow_anim.stop()

            self._clear_glow()

    def toggle_play(self):

        state = self.media_player.playbackState()

        if state == QMediaPlayer.PlaybackState.PlayingState:

            self.media_player.pause()

        elif state == QMediaPlayer.PlaybackState.PausedState:

            self.media_player.play()

        elif self.queue and self.current_index >= 0:

            self.play_track(self.current_index)

        elif self.tracks:

            self.queue = self.tracks

            self.play_track(0)

    def play_next(self):

        if self.queue:

            self.play_track((self.current_index + 1) % len(self.queue))

    def play_previous(self):

        if self.queue:

            self.play_track((self.current_index - 1) % len(self.queue))

    def toggle_repeat(self):

        self.is_repeating = not self.is_repeating

        self.btn_repeat.set_active(self.is_repeating)

    # ---- now-playing highlight

    def update_breathing_light(self, val):

        if self.queue is not self.tracks or self.current_index < 0:

            return

        item = self.playlist_widget.item(self.current_index)

        if item:

            c = self.theme["accent"]

            item.setForeground(QColor(c.red(), c.green(), c.blue(), int(val)))

            self._glow_row = self.current_index

    def _clear_glow(self):

        if self._glow_row >= 0:

            item = self.playlist_widget.item(self._glow_row)

            if item:

                item.setData(Qt.ItemDataRole.ForegroundRole, None)

        self._glow_row = -1

    # ---- volume / seeking

    def set_volume(self, vol):

        self.audio_output.setVolume(vol)

        self._vol_save_timer.start()        # debounce disk/registry writes

    def adjust_volume(self, delta):

        v = max(0.0, min(1.0, self.audio_output.volume() + delta))

        self.set_volume(v)

        self.volume_widget.set_volume(v)

    def seek_by(self, ms):

        dur = self.media_player.duration()

        if dur <= 0:

            return

        self.media_player.setPosition(max(0, min(dur, self.media_player.position() + ms)))

    def on_slider_moved(self, value):

        self.time_current.setText(fmt_time(value // 1000))

    def on_slider_released(self):

        self.media_player.setPosition(self.progress_slider.value())

    def update_position(self, position):

        if not self.progress_slider.isSliderDown():

            self.progress_slider.setValue(position)

            sec = position // 1000

            if sec != self._last_sec:

                self._last_sec = sec

                self.time_current.setText(fmt_time(sec))

        # playback has been stable for a while -> forgive earlier retries

        if self._retries and position - self._last_retry_pos > 15000:

            self._retries = 0

    def update_duration(self, duration):

        self.progress_slider.setRange(0, max(0, duration))

        self.time_total.setText(fmt_time(duration // 1000))


if __name__ == "__main__":

    if sys.platform == "win32":

        try:

            myappid = "harmony"

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        except Exception:

            pass

    app = QApplication(sys.argv)

    icon_path = resource_path("harmony.ico")

    if os.path.exists(icon_path):

        app.setWindowIcon(QIcon(icon_path))

    player = AudioPlayer()

    player.show()

    sys.exit(app.exec())