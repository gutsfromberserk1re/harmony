import sys
import os

os.environ["YTDLP_NO_LAZY_EXTRACTORS"] = "1"    # must be set before yt_dlp is imported
os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.*=false")

import gc
import json
import math
import time
import random
import ctypes
import functools
import importlib
import subprocess
import threading

from PySide6.QtCore import (
    Qt, QObject, QEvent, Signal, QUrl, QTimer, QRectF, QPointF, QPoint, QSize,
    QPropertyAnimation, QEasingCurve, Property, QSettings,
    QAbstractListModel, QModelIndex
)
from PySide6.QtGui import (
    QFont, QPainter, QColor, QPen, QBrush, QPainterPath, QPixmap,
    QShortcut, QKeySequence, QIcon, QPolygonF, QRadialGradient
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListView,
    QPushButton, QLabel, QMenu, QDialog, QLineEdit, QSlider, QTreeWidget,
    QTreeWidgetItem, QGraphicsDropShadowEffect, QStyle, QSizePolicy, QAbstractItemView
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

SIDEBAR_WIDTH = 210
MAX_RETRIES = 3
RAINBOW_CYCLE_SEC = 60          # time for the Rainbow theme to go around the whole color wheel
RAINBOW_STYLE_EVERY = 8         # re-apply stylesheets every N rainbow ticks (200 ms each)

TRIM_EXTRACTORS = True          # load only the YouTube extractors (big RAM saver); False = stock yt-dlp
USE_YTDLP_EXE = False           # True = run a bundled yt-dlp.exe as a subprocess (lowest RAM, slower track start)


# ----------------------------------------------------------------- themes

def _theme(accent, bg, sidebar_bg):
    a = QColor(*accent)
    return {"accent": a, "accent_hex": a.name(),
            "bg": QColor(*bg), "sidebar_bg": QColor(*sidebar_bg)}


def _rainbow_theme(h):
    """Theme for hue h in [0, 1). Accent, background and sidebar all share the hue."""
    a = QColor.fromHslF(h, 0.90, 0.70)
    return {"accent": a, "accent_hex": a.name(),
            "bg": QColor.fromHslF(h, 0.50, 0.055),
            "sidebar_bg": QColor.fromHslF(h, 0.50, 0.03)}


THEMES = {
    "Pink":      _theme((255, 182, 193), (18, 10, 14), (10, 5, 8)),
    "Blue":      _theme((135, 206, 235), (10, 14, 20), (5, 8, 12)),
    "Green":     _theme((144, 238, 144), (10, 18, 12), (5, 10, 7)),
    "Black":     _theme((220, 220, 220), (12, 12, 12), (6, 6, 6)),
    "Purple":    _theme((187, 134, 252), (16, 10, 24), (9, 5, 15)),
    "Deep Blue": _theme((77, 124, 255),  (6, 10, 26),  (3, 5, 16)),
    "White":     _theme((255, 255, 255), (14, 14, 16), (7, 7, 9)),
    "Silver":    _theme((192, 200, 212), (14, 16, 20), (8, 9, 12)),
    "Red":       _theme((255, 99, 110),  (22, 8, 10),  (13, 4, 6)),
    "Orange":    _theme((255, 167, 88),  (22, 14, 8),  (13, 8, 4)),
    "Yellow":    _theme((255, 224, 102), (22, 20, 8),  (13, 12, 4)),
    "Teal":      _theme((64, 224, 208),  (6, 20, 20),  (3, 12, 12)),
    "Lavender":  _theme((200, 180, 255), (16, 12, 24), (9, 7, 15)),
    "Crimson":   _theme((220, 20, 60),   (20, 6, 10),  (11, 3, 6)),
    "Gold":      _theme((212, 175, 55),  (20, 16, 8),  (11, 9, 4)),
    "Mint":      _theme((152, 255, 204), (8, 20, 16),  (4, 12, 9)),
    "Rainbow":   _rainbow_theme(0.0),       # dynamic: replaced on every tick while selected
}

# Window background alpha presets (0-255)
OPACITY_PRESETS = [("Clear", 70), ("Glass", 110), ("Frosted", 160), ("Solid", 225)]
DEFAULT_ALPHA = 110


# ----------------------------------------------------------------- helpers

def resource_path(relative_path):
    """Absolute path to a bundled resource (Nuitka onefile / PyInstaller / dev)."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


ICON_PATH = resource_path("harmony.ico")
HAS_ICON = os.path.exists(ICON_PATH)
YTDLP_EXE = resource_path("yt-dlp.exe")
USE_EXE = USE_YTDLP_EXE and os.path.exists(YTDLP_EXE)

_icon_cache = []


def app_icon():
    """One shared QIcon (created lazily, after QApplication exists)."""
    if not _icon_cache:
        _icon_cache.append(QIcon(ICON_PATH) if HAS_ICON else None)
    return _icon_cache[0]


@functools.lru_cache(maxsize=None)
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


_ws_ready = False


def trim_memory():
    """Collect garbage and hand unused pages back to Windows (lowers the Task Manager figure)."""
    gc.collect()
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.kernel32.SetProcessWorkingSetSize(
            ctypes.c_void_p(-1), ctypes.c_size_t(-1), ctypes.c_size_t(-1))
    except Exception:
        pass


def menu_qss(hx):
    return f"""
        QMenu {{ background-color: rgba(12,16,24,225); color: {hx};
            border: 1px solid {hx}; border-radius: 6px; padding: 4px; }}
        QMenu::item {{ padding: 6px 16px; border-radius: 4px; }}
        QMenu::item:selected {{ background-color: rgba(255,255,255,0.15); color: #ffffff; }}
        QMenu::separator {{ height: 1px; background: rgba(255,255,255,0.12); margin: 4px 8px; }}
    """


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


# ----------------------------------------------------------------- yt-dlp access

class Bridge(QObject):
    """Hands results from worker threads to the Qt main thread.
    playlist_req / stream_req hold the newest request ids so workers can skip stale work."""
    playlist_ready = Signal(int, list)
    stream_ready = Signal(int, str)
    playlist_req = 0
    stream_req = 0


_COMMON_OPTS = {
    'quiet': True, 'no_warnings': True, 'cachedir': False,
    'socket_timeout': 15, 'retries': 3,
    'extractor_args': {'youtube': {'skip': ['translated_subs']}},
}
PLAYLIST_OPTS = dict(_COMMON_OPTS, extract_flat='in_playlist', skip_download=True, ignoreerrors=True)
STREAM_OPTS = dict(_COMMON_OPTS, format='bestaudio/best', noplaylist=True)

_import_lock = threading.Lock()
_stream_lock = threading.Lock()
_yt_module = None
_stream_ydl = None


def _make_slim_finder():
    """Meta-path hook: replaces yt-dlp's 1000-extractor registry with just the YouTube extractors."""
    import importlib.abc
    import importlib.machinery

    class _Loader(importlib.abc.Loader):
        def create_module(self, spec):
            return None

        def exec_module(self, module):
            from yt_dlp.extractor import youtube as yt
            from yt_dlp.extractor.common import InfoExtractor
            found = [(k, v) for k, v in vars(yt).items()
                     if k.endswith("IE") and not k.startswith("_")
                     and isinstance(v, type) and issubclass(v, InfoExtractor)]
            found.sort(key=lambda kv: kv[0] != "YoutubeIE")
            for k, v in found:
                setattr(module, k, v)

            class GenericIE(InfoExtractor):         # yt-dlp expects one; this never matches anything
                IE_NAME = "generic"
                _VALID_URL = r"(?!)"

            module.GenericIE = GenericIE

    class _Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name in ("yt_dlp.extractor._extractors", "yt_dlp.extractor.extractors"):
                return importlib.machinery.ModuleSpec(name, _Loader())
            return None

    return _Finder()


def get_ytdlp():
    """Import yt_dlp once (thread-safe), optionally with only the YouTube extractors."""
    global _yt_module
    if _yt_module is not None:
        return _yt_module
    with _import_lock:
        if _yt_module is not None:
            return _yt_module
        if TRIM_EXTRACTORS:
            finder = _make_slim_finder()
            sys.meta_path.insert(0, finder)
            try:
                _yt_module = importlib.import_module("yt_dlp")
                return _yt_module
            except Exception:
                for m in [m for m in sys.modules if m == "yt_dlp" or m.startswith("yt_dlp.")]:
                    del sys.modules[m]          # undo the half-imported package, then import normally
            finally:
                try:
                    sys.meta_path.remove(finder)
                except ValueError:
                    pass
        _yt_module = importlib.import_module("yt_dlp")
        return _yt_module


def prewarm_ytdlp():
    """Import yt_dlp off the UI thread so startup stays fast."""
    if USE_EXE:
        return
    try:
        get_ytdlp()
        gc.freeze()         # long-lived yt-dlp objects no longer get scanned by the collector
    except Exception:
        pass


def _run_exe(args, timeout):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    flags = 0x08000000 if sys.platform == "win32" else 0        # CREATE_NO_WINDOW
    r = subprocess.run([YTDLP_EXE, *args], stdin=subprocess.DEVNULL, capture_output=True,
                       timeout=timeout, env=env, creationflags=flags)
    return r.stdout.decode("utf-8", "replace")


def _make_track(vid, title, dur):
    return (vid, title or 'Unknown Track', fmt_time(dur) if dur else '--:--')


def _playlist_exe(url):
    out = _run_exe(["--flat-playlist", "--ignore-errors", "--no-warnings", "--no-cache-dir",
                    "--socket-timeout", "15", "--print", "%(id)s|%(duration)s|%(title)s", url], 180)
    tracks = []
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3 or not parts[0]:
            continue
        vid, dur, title = parts
        if title in ('[Private video]', '[Deleted video]'):
            continue
        try:
            d = int(float(dur))
        except ValueError:
            d = 0
        tracks.append(_make_track(vid, title, d))
    return tracks


def _playlist_inproc(url):
    yt = get_ytdlp()
    tracks = []
    with yt.YoutubeDL(dict(PLAYLIST_OPTS)) as ydl:
        info = ydl.extract_info(url, download=False)
    if info:
        entries = info.get('entries')
        if entries is None:                   # single video link
            entries = [info]
        for e in entries:
            if not e or not e.get('id'):
                continue
            title = e.get('title') or 'Unknown Track'
            if title in ('[Private video]', '[Deleted video]'):
                continue
            tracks.append(_make_track(e['id'], title, e.get('duration') or 0))
    return tracks


def _stream_exe(url):
    out = _run_exe(["-f", "bestaudio/best", "--no-playlist", "--no-warnings", "--no-cache-dir",
                    "--socket-timeout", "15", "-g", url], 90)
    lines = out.splitlines()
    return lines[0].strip() if lines else ''


def _stream_inproc(url):
    global _stream_ydl
    try:
        if _stream_ydl is None:
            _stream_ydl = get_ytdlp().YoutubeDL(dict(STREAM_OPTS))
        info = _stream_ydl.extract_info(url, download=False)
        return (info or {}).get('url', '') or ''
    except Exception:
        _stream_ydl = None                    # rebuild on next attempt
        raise


def fetch_playlist(bridge, req, url):
    tracks = []
    if req == bridge.playlist_req:            # skip if the user already clicked something else
        try:
            tracks = _playlist_exe(url) if USE_EXE else _playlist_inproc(url)
        except Exception:
            tracks = []
    bridge.playlist_ready.emit(req, tracks)
    gc.collect()


def fetch_stream(bridge, req, url):
    stream = ''
    try:
        with _stream_lock:                    # one resolve at a time; re-check after waiting
            if req == bridge.stream_req:
                stream = _stream_exe(url) if USE_EXE else _stream_inproc(url)
    except Exception:
        stream = ''
    bridge.stream_ready.emit(req, stream)


# ----------------------------------------------------------------- track list model

class TrackModel(QAbstractListModel):
    """Rows are generated on demand, so a huge playlist costs almost no per-item memory."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tracks = []            # (video_id, title, duration_str)
        self.message = ""
        self.hl_row = -1
        self.hl_brush = None

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.tracks) if self.tracks else (1 if self.message else 0)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        r = index.row()
        if role == Qt.ItemDataRole.DisplayRole:
            if self.tracks:
                _vid, title, dur = self.tracks[r]
                return f"{r + 1:02d}. {title} [{dur}]"
            return self.message
        if role == Qt.ItemDataRole.ForegroundRole and r == self.hl_row and self.hl_brush is not None:
            return self.hl_brush
        return None

    def set_tracks(self, tracks, message=""):
        self.beginResetModel()
        self.tracks = tracks
        self.message = message
        self.hl_row = -1
        self.hl_brush = None
        self.endResetModel()

    def set_highlight(self, row, brush):
        old = self.hl_row
        self.hl_row = row
        self.hl_brush = brush
        roles = [Qt.ItemDataRole.ForegroundRole]
        for r in {old, row}:
            if 0 <= r < len(self.tracks):
                i = self.index(r, 0)
                self.dataChanged.emit(i, i, roles)


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
    TOGGLES = ('repeat', 'shuffle')     # strong on/off look and a glow when on

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
        r, g, b = c.red(), c.green(), c.blue()
        cx, cy = self.width() / 2.0, self.height() / 2.0
        t = self.icon_type
        hovered = self.underMouse()

        if t in self.TOGGLES:
            if self.active:
                color = c
                grad = QRadialGradient(cx, cy, 18)
                grad.setColorAt(0.0, QColor(r, g, b, 140))
                grad.setColorAt(0.55, QColor(r, g, b, 70))
                grad.setColorAt(1.0, QColor(r, g, b, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(grad))
                p.drawEllipse(QPointF(cx, cy), 18, 18)
                p.setPen(QPen(QColor(r, g, b, 170), 1.2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), 14.5, 14.5)
            else:
                color = QColor(r, g, b, 170 if hovered else 85)
        else:
            color = c if (self.active or hovered) else QColor(r, g, b, 180)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(color))

        if t == 'play':
            path = QPainterPath()
            path.moveTo(cx - 5, cy - 8); path.lineTo(cx + 8, cy); path.lineTo(cx - 5, cy + 8)
            path.closeSubpath()
            p.drawPath(path)
        elif t == 'pause':
            p.drawRoundedRect(QRectF(cx - 6, cy - 8, 4, 16), 1, 1)
            p.drawRoundedRect(QRectF(cx + 2, cy - 8, 4, 16), 1, 1)
        elif t == 'next':
            path = QPainterPath()
            path.moveTo(cx - 7, cy - 7); path.lineTo(cx + 1, cy); path.lineTo(cx - 7, cy + 7)
            path.closeSubpath()
            p.drawPath(path)
            p.drawRoundedRect(QRectF(cx + 2, cy - 7, 3, 14), 1, 1)
        elif t == 'prev':
            path = QPainterPath()
            path.moveTo(cx + 7, cy - 7); path.lineTo(cx - 1, cy); path.lineTo(cx + 7, cy + 7)
            path.closeSubpath()
            p.drawPath(path)
            p.drawRoundedRect(QRectF(cx - 5, cy - 7, 3, 14), 1, 1)
        elif t == 'repeat':
            p.setPen(QPen(color, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(cx - 7, cy - 7, 14, 14), 40 * 16, 280 * 16)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            arrow = QPainterPath()
            arrow.moveTo(cx + 4, cy - 8); arrow.lineTo(cx + 9, cy - 4); arrow.lineTo(cx + 3, cy - 1)
            arrow.closeSubpath()
            p.drawPath(arrow)
        elif t == 'shuffle':
            p.setPen(QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                          Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            a = QPainterPath()
            a.moveTo(cx - 9, cy - 5)
            a.cubicTo(cx - 1, cy - 5, cx - 2, cy + 5, cx + 5, cy + 5)
            bpath = QPainterPath()
            bpath.moveTo(cx - 9, cy + 5)
            bpath.cubicTo(cx - 1, cy + 5, cx - 2, cy - 5, cx + 5, cy - 5)
            p.drawPath(a)
            p.drawPath(bpath)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            for y in (cy - 5, cy + 5):
                head = QPainterPath()
                head.moveTo(cx + 4, y - 3.5); head.lineTo(cx + 9.5, y); head.lineTo(cx + 4, y + 3.5)
                head.closeSubpath()
                p.drawPath(head)


class SmoothWaveVisualizer(QWidget):
    # (frequency, amplitude multiplier, alpha, pen width, phase shift)
    WAVES = (
        (0.02, 1.0, 230, 2.2, 0.0),
        (0.035, 0.6, 150, 1.5, 1.2),
        (0.015, 0.4, 90, 1.0, 2.5),
    )
    STEP = 4                                # px between wave samples

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.is_playing = False
        self.phase = 0.0
        self.amp = 0.05
        self._env_w = -1
        self._xs = []
        self._env = []
        self._pens = []
        self.set_color(QColor(255, 182, 193))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(self._interval())

    def _interval(self):
        return 33 if self.is_playing else 83     # ~30 fps playing, ~12 fps idle

    def set_color(self, color):
        r, g, b = color.red(), color.green(), color.blue()
        self._pens = [QPen(QColor(r, g, b, a), w) for _, _, a, w, _ in self.WAVES]
        self.update()

    def set_playing(self, playing):
        self.is_playing = playing
        if self.timer.isActive():
            self.timer.setInterval(self._interval())

    def set_active(self, active):
        if active:
            if not self.timer.isActive():
                self.timer.start(self._interval())
        else:
            self.timer.stop()

    def animate(self):
        if self.is_playing:
            self.amp += (0.35 - self.amp) * 0.1
            self.phase += 0.165
        else:
            self.amp += (0.05 - self.amp) * 0.18
            self.phase += 0.1
        self.update()

    def _build_cache(self, w):
        self._env_w = w
        self._xs = list(range(0, w + 1, self.STEP))
        self._env = [math.sin((x / w) * math.pi) for x in self._xs]

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        if w <= 0:
            return
        if w != self._env_w:
            self._build_cache(w)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(Qt.BrushStyle.NoBrush)
        mid = h / 2.0
        base = h * self.amp
        sin = math.sin
        for (freq, mult, _a, _w, shift), pen in zip(self.WAVES, self._pens):
            amp = base * mult
            ph = self.phase + shift
            poly = QPolygonF([QPointF(x, mid + sin(x * freq + ph) * amp * env)
                              for x, env in zip(self._xs, self._env)])
            p.setPen(pen)
            p.drawPolyline(poly)


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
            self.setSliderDown(False)       # Qt emits sliderReleased itself (emitting again double-seeks)
            e.accept()
        else:
            super().mouseReleaseEvent(e)


class ClickableLabel(QLabel):
    clicked = Signal()
    right_clicked = Signal(QPoint)          # global position of the click

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        elif e.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit(e.globalPosition().toPoint())
        else:
            super().mousePressEvent(e)
            return
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
        btn_qss = f"""
            QPushButton {{ background: transparent; color: {self.accent};
                border: 1px solid {self.accent}; border-radius: 4px; padding: 4px 14px; }}
            QPushButton:hover {{ background: {self.accent}; color: #000000; }}
        """
        for b in (btn_ok, btn_cancel):
            b.setFont(mono(9))
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setAutoDefault(False)
            b.setStyleSheet(btn_qss)
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

        # Small pixmap: the raw 256px .ico would sit in RAM for the whole session
        ic = app_icon()
        pm = ic.pixmap(QSize(40, 40)) if ic is not None else None
        self._file_pm = pm if (pm is not None and not pm.isNull()) else None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)

        self.app_icon_label = ClickableLabel()
        self.app_icon_label.setFixedSize(20, 20)
        self.app_icon_label.setScaledContents(True)
        self.app_icon_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.app_icon_label.setToolTip("Click: toggle playlists  |  Right-click: themes & transparency")
        self.app_icon_label.clicked.connect(parent.toggle_sidebar)
        self.app_icon_label.right_clicked.connect(parent.show_main_menu)
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
        if self._file_pm is not None:
            self.app_icon_label.setPixmap(self._file_pm)
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
        if self._file_pm is None:           # only the fallback dot depends on the theme
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
        self.tracks = []            # tracks shown in the list: (id, title, duration_str)
        self.queue = []             # tracks actually being played (kept when browsing other playlists)
        self.current_index = -1
        self.is_repeating = self.settings.value("repeat", False, type=bool)
        self.is_shuffling = self.settings.value("shuffle", False, type=bool)
        self._shuffle_bag = []
        self._shuffle_history = []
        self.sidebar_expanded = True
        self._resume_ms = 0
        self._retries = 0
        self._last_retry_pos = 0
        self._last_sec = -1
        self._rainbow_ticks = 0
        self._bg_path = QPainterPath()      # rebuilt only on resize

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

        self.rainbow_timer = QTimer(self)
        self.rainbow_timer.setInterval(200)
        self.rainbow_timer.timeout.connect(self._rainbow_tick)

        self.setup_window()
        self.enable_window_blur_and_corners()
        self.setup_ui()
        self.setup_breathing_animation()
        self.setup_shortcuts()
        self.update_sidebar_tree()
        self._sync_rainbow_timer()

    # ---- setup

    def setup_window(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setWindowTitle("Harmony")
        self.resize(820, 500)
        self.setMinimumSize(640, 420)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if app_icon() is not None:
            self.setWindowIcon(app_icon())

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
        self.glow_timer = QTimer(self)
        self.glow_timer.setInterval(80)         # ~12 Hz is plenty for a slow 2 s pulse
        self.glow_timer.timeout.connect(self.update_breathing_light)

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
        add(Qt.Key.Key_S, self.toggle_shuffle)
        add(Qt.Key.Key_R, self.toggle_repeat)

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
        self.playlist_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_tree.customContextMenuRequested.connect(self.on_tree_context_menu)

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

        # Model/view list: no per-track widget items
        self.track_model = TrackModel(self)
        self.playlist_widget = QListView()
        self.playlist_widget.setModel(self.track_model)
        self.playlist_widget.setFont(mono(10))
        self.playlist_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.playlist_widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.playlist_widget.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.playlist_widget.setUniformItemSizes(True)
        self.playlist_widget.setWordWrap(False)
        self.playlist_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.playlist_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.playlist_widget.doubleClicked.connect(self.on_track_selected)

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
        self.btn_shuffle = VectorButton('shuffle')
        self.btn_prev = VectorButton('prev')
        self.btn_play = VectorButton('play')
        self.btn_next = VectorButton('next')
        self.btn_repeat = VectorButton('repeat')
        self.btn_shuffle.setToolTip("Shuffle (S)")
        self.btn_repeat.setToolTip("Repeat track (R)")
        self.btn_shuffle.set_active(self.is_shuffling)
        self.btn_repeat.set_active(self.is_repeating)
        self.btn_shuffle.clicked.connect(self.toggle_shuffle)
        self.btn_prev.clicked.connect(self.play_previous)
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next.clicked.connect(self.play_next)
        self.btn_repeat.clicked.connect(self.toggle_repeat)
        self.control_buttons = (self.btn_shuffle, self.btn_prev, self.btn_play,
                                self.btn_next, self.btn_repeat)
        for i, b in enumerate(self.control_buttons):
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
        # Don't burn CPU animating while minimized, and give memory back
        if event.type() == QEvent.Type.WindowStateChange:
            minimized = self.isMinimized()
            self.visualizer.set_active(not minimized)
            self._sync_rainbow_timer()
            if minimized:
                QTimer.singleShot(300, trim_memory)
        super().changeEvent(event)

    def resizeEvent(self, event):
        self._bg_path = QPainterPath()
        self._bg_path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 14, 14)
        super().resizeEvent(event)

    def closeEvent(self, event):
        self.media_player.stop()
        self.settings.setValue("volume", self.audio_output.volume())
        self.settings.sync()
        super().closeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        bg = QColor(self.theme["bg"])
        bg.setAlpha(self.bg_alpha)
        p.fillPath(self._bg_path, QBrush(bg))

        sbw = self.sidebar.width()
        if sbw > 0:
            sb = QColor(self.theme["sidebar_bg"])
            sb.setAlpha(min(255, int(self.bg_alpha * 0.6) + 25))
            p.save()
            p.setClipPath(self._bg_path)
            p.fillRect(0, 0, sbw, h, sb)
            p.restore()

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

    def _apply_accent_light(self):
        """Cheap part of a theme change: painted widgets and glow effects only (no stylesheets)."""
        ac = self.theme["accent"]
        self.visualizer.set_color(ac)
        for b in self.control_buttons:
            b.set_color(ac)
        self.label_fx.setColor(ac)
        self.volume_fx.setColor(ac)
        self.title_bar.title_fx.setColor(ac)
        self.update()

    def apply_theme_ui(self):
        """Full theme application, including every stylesheet."""
        hx = self.theme["accent_hex"]
        sb_qss = scrollbar_qss(hx)

        self.title_bar.apply_theme(self.theme)
        self._apply_accent_light()

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
            QListView {{ background: transparent; border: none; color: #c0d5e5; outline: none; }}
            QListView::item {{ padding: 5px 0px; border-bottom: 1px solid rgba(255,255,255,0.05); }}
            QListView::item:selected {{
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
            self._sync_rainbow_timer()
            self.apply_theme_ui()

    # ---- rainbow theme

    def _sync_rainbow_timer(self):
        if self.current_theme_name == "Rainbow" and not self.isMinimized():
            if not self.rainbow_timer.isActive():
                self.rainbow_timer.start()
        else:
            self.rainbow_timer.stop()

    def _rainbow_tick(self):
        hue = (time.monotonic() / RAINBOW_CYCLE_SEC) % 1.0
        self.theme = _rainbow_theme(hue)
        THEMES["Rainbow"] = self.theme
        self._rainbow_ticks += 1
        if self._rainbow_ticks % RAINBOW_STYLE_EVERY == 0:
            self.apply_theme_ui()           # stylesheets are the expensive part, so they update less often
        else:
            self._apply_accent_light()

    def set_transparency(self, alpha):
        self.bg_alpha = alpha
        self.settings.setValue("bg_alpha", alpha)
        self.update()

    # ---- menus

    def show_main_menu(self, global_pos):
        """Theme / transparency menu. Only opened by right-clicking the title-bar icon."""
        menu = QMenu(self)
        menu.setFont(mono(9))
        menu.setStyleSheet(menu_qss(self.theme["accent_hex"]))

        theme_menu = menu.addMenu("🎨 Change Theme")
        for t in THEMES:
            a = theme_menu.addAction(t)
            a.setCheckable(True)
            a.setChecked(t == self.current_theme_name)
            a.triggered.connect(lambda c=False, tn=t: self.change_theme(tn))

        glass_menu = menu.addMenu("🪟 Transparency")
        for label, alpha in OPACITY_PRESETS:
            a = glass_menu.addAction(label)
            a.setCheckable(True)
            a.setChecked(alpha == self.bg_alpha)
            a.triggered.connect(lambda c=False, al=alpha: self.set_transparency(al))

        menu.exec(global_pos)
        menu.deleteLater()                  # parented menus are otherwise never freed

    def on_tree_context_menu(self, pos):
        """Right-click on a playlist in the sidebar: remove only."""
        item = self.playlist_tree.itemAt(pos)
        if not item:
            return
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if not name:
            return
        menu = QMenu(self)
        menu.setFont(mono(9))
        menu.setStyleSheet(menu_qss(self.theme["accent_hex"]))
        act = menu.addAction(f"🗑 Remove '{name}'")
        act.triggered.connect(lambda c=False, n=name: self.remove_playlist(n))
        menu.exec(self.playlist_tree.viewport().mapToGlobal(pos))
        menu.deleteLater()

    # ---- playlists

    def _load_playlists(self):
        try:
            data = json.loads(self.settings.value("playlists", "{}", type=str))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_playlists(self):
        self.settings.setValue("playlists", json.dumps(self.playlists))

    def _ask(self, title, label):
        """Show a prompt and free it afterwards. Returns the text, or None if cancelled."""
        d = CustomDialog(title, label, self.theme, self)
        ok = d.exec() == QDialog.DialogCode.Accepted
        text = d.input_field.text().strip() if ok else None
        d.deleteLater()
        return text

    def add_playlist(self):
        name = self._ask("Playlist Name", "Enter a name for this playlist:")
        if not name:
            return
        url = self._ask("YouTube Link", "Paste YouTube Playlist URL:")
        if not url or not url.lower().startswith(("http://", "https://")):
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
                self.bridge.playlist_req += 1
                self.current_playlist_name = ""
                self.tracks = []
                self.track_model.set_tracks(self.tracks)
                self.playlist_label.setText("No Playlist Selected")
                QTimer.singleShot(500, trim_memory)

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
        self.track_model.set_tracks(self.tracks, "Loading tracks...")
        self.bridge.playlist_req += 1
        threading.Thread(target=fetch_playlist,
                         args=(self.bridge, self.bridge.playlist_req, self.playlists[name]),
                         daemon=True).start()

    def populate_tracks(self, req, tracks):
        if req != self.bridge.playlist_req:      # stale result from a previous click
            return
        self.tracks = tracks
        self.track_model.set_tracks(
            tracks, "" if tracks else "No tracks found or error loading playlist.")
        QTimer.singleShot(800, trim_memory)

    def on_track_selected(self, index):
        row = index.row()
        if self.tracks and 0 <= row < len(self.tracks):
            self.queue = self.tracks
            self._reset_shuffle()
            self.play_track(row)

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
            self.playlist_widget.setCurrentIndex(self.track_model.index(index, 0))
        vid, title, _dur = self.queue[index]
        self.now_label.setText(f"Loading: {title}")
        self.bridge.stream_req += 1
        threading.Thread(target=fetch_stream,
                         args=(self.bridge, self.bridge.stream_req,
                               f"https://www.youtube.com/watch?v={vid}"),
                         daemon=True).start()

    def start_stream(self, req, stream_url):
        if req != self.bridge.stream_req:
            return
        if not stream_url:
            self._retry_current(self._resume_ms)
            return
        if 0 <= self.current_index < len(self.queue):
            self.now_label.setText(self.queue[self.current_index][1])
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
            if not self.glow_timer.isActive():
                self.glow_timer.start()
        else:
            self.glow_timer.stop()
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
            self._reset_shuffle()
            self.play_track(0)

    # ---- next / previous / shuffle / repeat

    def _reset_shuffle(self):
        self._shuffle_bag = []
        self._shuffle_history = []

    def _next_shuffle_index(self):
        """Every track plays once per round, in random order, before the bag is refilled."""
        n = len(self.queue)
        if n <= 1:
            return 0
        if not self._shuffle_bag:
            self._shuffle_bag = [i for i in range(n) if i != self.current_index]
            random.shuffle(self._shuffle_bag)
        return self._shuffle_bag.pop()

    def play_next(self):
        if not self.queue:
            return
        if self.is_shuffling:
            if self.current_index >= 0:
                self._shuffle_history.append(self.current_index)
                del self._shuffle_history[:-200]        # cap history length
            self.play_track(self._next_shuffle_index())
        else:
            self.play_track((self.current_index + 1) % len(self.queue))

    def play_previous(self):
        if not self.queue:
            return
        if self.is_shuffling and self._shuffle_history:
            self.play_track(self._shuffle_history.pop())
        else:
            self.play_track((self.current_index - 1) % len(self.queue))

    def toggle_repeat(self):
        self.is_repeating = not self.is_repeating
        self.settings.setValue("repeat", self.is_repeating)
        self.btn_repeat.set_active(self.is_repeating)

    def toggle_shuffle(self):
        self.is_shuffling = not self.is_shuffling
        self.settings.setValue("shuffle", self.is_shuffling)
        self._reset_shuffle()
        self.btn_shuffle.set_active(self.is_shuffling)

    # ---- now-playing highlight

    def update_breathing_light(self):
        if self.queue is not self.tracks or self.current_index < 0:
            return
        # 110 -> 255 -> 110 alpha, 2 second period
        val = int(182 - 72 * math.cos(time.monotonic() * math.pi))
        c = self.theme["accent"]
        self.track_model.set_highlight(
            self.current_index, QBrush(QColor(c.red(), c.green(), c.blue(), val)))

    def _clear_glow(self):
        if self.track_model.hl_row >= 0:
            self.track_model.set_highlight(-1, None)

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
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("harmony")
        except Exception:
            pass

    gc.collect()
    gc.freeze()             # startup objects never need to be scanned again

    # Start importing yt_dlp in the background while the UI builds
    threading.Thread(target=prewarm_ytdlp, daemon=True).start()

    app = QApplication(sys.argv)
    if app_icon() is not None:
        app.setWindowIcon(app_icon())

    player = AudioPlayer()
    player.show()
    QTimer.singleShot(4000, trim_memory)        # after startup + yt_dlp import have settled
    sys.exit(app.exec())
