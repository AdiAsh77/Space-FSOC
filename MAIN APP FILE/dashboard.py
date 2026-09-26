"""
dashboard.py

FSOC Vision Stabilization Console - UI only.
The real Unity + YOLO/Kalman tracking lives in backend.py;
this file wires backend.TrackingThread into the Sim View tab.

Run:      python dashboard.py
Requires: backend.py in the same folder (or on the Python path).
"""

# IMPORTANT: import backend BEFORE any PyQt import. backend.py
# loads cv2/ultralytics (torch) first; if PyQt has already
# touched the DLL search path by then, torch's native DLLs can
# fail to load on Windows. See the note at the top of backend.py.
from backend import (
    TrackingThread,
    TRACK_HOST, TRACK_PORT, MODEL_PATH, CONFIDENCE_THRESHOLD,
    YOLO_INTERVAL, INITIALIZATION_DETECTIONS,
    ACQUISITION_ERROR_X, ACQUISITION_ERROR_Y, TRACK_CAMERA_FPS,
    UNITY_EXE,
)

# video_tracking (YOLO/torch) must also be imported before PyQt, for the same DLL reason.
import video_tracking
from video_tracking import BeaconTracker

import sys, os, math, random, tempfile, threading, time
import subprocess
from collections import deque

import numpy as np
import cv2

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, QSize, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QImage, QRadialGradient, QPolygonF, QFont,
    QIcon, QPixmap, QPalette, QPainterPath, QLinearGradient)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QStackedWidget, QSlider, QComboBox, QLineEdit, QCheckBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QHeaderView, QAbstractItemView, QButtonGroup, QScrollArea, QSizePolicy)

import win32gui  # type: ignore
import win32con  # type: ignore
import win32process  # type: ignore
import glob
from config import scener
# Single source of truth for the scenes folder — used by both the Scene-Parameters
# tab (build_scene_params/save_scene_settings write a .txt file here for every Save)
# and the Sim View tab (build_sim/refresh_scene_list reads the .txt file names here
# to populate the "Test case scene" dropdown). Change only this constant to move it.
SCENES_DIR = scener

LIGHT = dict(bg='#f1f4f9', pn='#ffffff', ink='#0f1b2d', mut='#55647c', ln='#dbe2ec', sd='#0f1a2e', bc='#d63b45', ok='#0b8a6a',
             wn='#b26a00', ac='#2454e6', ach='#1a43c2', onac='#ffffff', soft='#eef2f8')
DARK = dict(bg='#0a101d', pn='#131c2f', ink='#eaf0fb', mut='#a3b1cc', ln='#27334c', sd='#060b15', bc='#ff6b74', ok='#34d3a3',
            wn='#f5b942', ac='#7c9cff', ach='#a3b8ff', onac='#0a101d', soft='#1a2540')
T = dict(LIGHT)

def _pen(color, w):
    p = QPen(QColor(color), w); p.setCapStyle(Qt.PenCapStyle.RoundCap); p.setJoinStyle(Qt.PenJoinStyle.RoundJoin); return p

def _pix(size):
    pm = QPixmap(size * 2, size * 2); pm.setDevicePixelRatio(2); pm.fill(Qt.GlobalColor.transparent); return pm

def asset(name, draw, size):
    """Render a small PNG (checkbox tick, combo chevron) so QSS can reference it."""
    pm = _pix(size); q = QPainter(pm); q.setRenderHint(QPainter.RenderHint.Antialiasing); draw(q); q.end()
    p = os.path.join(tempfile.gettempdir(), f"fsoc_{name}.png"); pm.save(p); return p.replace('\\', '/')

def _tick(q):
    q.setPen(_pen(T['onac'], 2.2)); q.drawPolyline(QPolygonF([QPointF(3.5, 8.5), QPointF(6.8, 11.6), QPointF(12.6, 4.8)]))

def _chev(q):
    q.setPen(_pen(T['mut'], 1.8)); q.drawPolyline(QPolygonF([QPointF(3.5, 4.5), QPointF(7, 8), QPointF(10.5, 4.5)]))

def draw_icon(kind, color, size=26):
    pm = _pix(size); q = QPainter(pm); q.setRenderHint(QPainter.RenderHint.Antialiasing)
    q.setPen(_pen(color, 1.9)); q.setBrush(Qt.BrushStyle.NoBrush); c = size / 2; fill = QColor(color)
    if kind == 'sim':        # planet with an orbiting satellite
        q.drawEllipse(QPointF(c, c), 4.2, 4.2); q.save(); q.translate(c, c); q.rotate(-28)
        q.drawEllipse(QPointF(0, 0), 11, 4.6); q.setBrush(fill); q.drawEllipse(QPointF(11, 0), 1.9, 1.9); q.restore()
    elif kind == 'video':    # screen with play triangle
        q.drawRoundedRect(QRectF(3, 6, size - 6, size - 12), 3.5, 3.5); q.setBrush(fill)
        q.drawPolygon(QPolygonF([QPointF(c - 2.4, c - 3.6), QPointF(c - 2.4, c + 3.6), QPointF(c + 3.8, c)]))
    elif kind == 'bench':    # gauge
        q.drawArc(QRectF(3.5, 5, size - 7, size - 7), 200 * 16, -220 * 16)
        q.drawLine(QPointF(c, c + 3), QPointF(c + 4.6, c - 4.4)); q.setBrush(fill); q.drawEllipse(QPointF(c, c + 3), 1.7, 1.7)
    elif kind == 'data':     # clipboard with a check
        q.drawRoundedRect(QRectF(5.5, 5, size - 11, size - 8), 3, 3); q.drawRoundedRect(QRectF(c - 3.4, 3, 6.8, 4.2), 1.6, 1.6)
        q.drawPolyline(QPolygonF([QPointF(c - 3.6, c + 2), QPointF(c - .8, c + 4.8), QPointF(c + 4, c - .6)]))
    elif kind == 'info':     # open book / spec sheet
        q.drawEllipse(QPointF(c, c), 8.5, 8.5); q.setBrush(fill); q.drawEllipse(QPointF(c, c - 4.2), 1.15, 1.15)
        q.drawLine(QPointF(c, c - 1.2), QPointF(c, c + 4.6))
    elif kind == 'scene':    # parameter sliders (three horizontal tracks with knobs)
        for y, kx in ((c - 7, 9), (c, 17), (c + 7, 12)):
            q.drawLine(QPointF(4, y), QPointF(size - 4, y))
            q.setBrush(fill); q.drawEllipse(QPointF(kx, y), 2.6, 2.6); q.setBrush(Qt.BrushStyle.NoBrush)
    elif kind == 'beacon':    # Scene-Parameters "Beacon Settings" heading: signal source + radiating waves
        q.setBrush(fill); q.drawEllipse(QPointF(c, c + c * .44), c * .24, c * .24); q.setBrush(Qt.BrushStyle.NoBrush)
        q.drawArc(QRectF(c - c * .6, c - c * .6, c * 1.2, c * 1.2), 35 * 16, 110 * 16)
        q.drawArc(QRectF(c - c * .94, c - c * .94, c * 1.88, c * 1.88), 35 * 16, 110 * 16)
    elif kind == 'satellite':  # Scene-Parameters "Satellite Settings" heading: body, two panels, antenna
        b = c * .29
        q.drawRect(QRectF(c - b, c - b, 2 * b, 2 * b))
        q.drawRect(QRectF(c - c * .95, c - b * .8, c * .5, b * 1.6)); q.drawRect(QRectF(c + c * .45, c - b * .8, c * .5, b * 1.6))
        q.drawLine(QPointF(c - c * .45, c), QPointF(c - b, c)); q.drawLine(QPointF(c + b, c), QPointF(c + c * .45, c))
        q.drawLine(QPointF(c + b * .6, c - b), QPointF(c + c * .5, c - c * .62))
        q.setBrush(fill); q.drawEllipse(QPointF(c + c * .5, c - c * .62), c * .11, c * .11)
    elif kind == 'disturbance':   # Scene-Parameters "Disturbances" heading: jagged noise wave
        q.drawPolyline(QPolygonF([QPointF(size * .14, c), QPointF(size * .33, c - c * .56), QPointF(size * .5, c + c * .56),
                                   QPointF(size * .67, c - c * .56), QPointF(size * .86, c)]))
    elif kind == 'camera':     # Scene-Parameters "Camera Settings" heading: body, viewfinder bump, lens
        q.drawRoundedRect(QRectF(size * .14, c - c * .44, size * .72, c * .88), c * .24, c * .24)
        q.drawRect(QRectF(c - c * .27, c - c * .71, c * .54, c * .29))
        q.setBrush(Qt.BrushStyle.NoBrush); q.drawEllipse(QPointF(c, c), c * .29, c * .29)
    else:                    # theme: half-filled circle
        q.drawEllipse(QPointF(c, c), 8, 8); q.setBrush(fill); q.drawPie(QRectF(c - 8, c - 8, 16, 16), 90 * 16, 180 * 16)
    q.end(); return pm

def make_icon(kind):
    ic = QIcon()
    ic.addPixmap(draw_icon(kind, '#8fa3c7'), QIcon.Mode.Normal, QIcon.State.Off)
    ic.addPixmap(draw_icon(kind, '#ffffff'), QIcon.Mode.Normal, QIcon.State.On)
    ic.addPixmap(draw_icon(kind, '#ffffff'), QIcon.Mode.Active, QIcon.State.Off)
    return ic

def beacon_logo():
    pm = _pix(30); q = QPainter(pm); q.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QRadialGradient(15, 15, 14); g.setColorAt(0, QColor('#ffffff')); g.setColorAt(.28, QColor('#ff5a5f')); g.setColorAt(1, QColor(255, 90, 95, 0))
    q.setPen(Qt.PenStyle.NoPen); q.setBrush(QBrush(g)); q.drawEllipse(QPointF(15, 15), 14, 14); q.end(); return pm

def qss():
    t = T
    return f"""
    QWidget {{ color:{t['ink']}; }}
    QMainWindow, QStackedWidget, QWidget#page {{ background:{t['bg']}; }}
    QFrame#panel {{ background:{t['pn']}; border:1px solid {t['ln']}; border-radius:12px; }}
    QLabel {{ background:transparent; }}
    QLabel#h1 {{ font-size:22px; font-weight:800; }} QLabel#h3 {{ font-size:14px; font-weight:700; }}
    QLabel#mut {{ color:{t['mut']}; }}
    QFrame#nav {{ background:{t['sd']}; }}
    QPushButton#nb {{ background:transparent; border:0; border-radius:12px; padding:0; }}
    QPushButton#nb:hover {{ background:rgba(255,255,255,.09); }}
    QPushButton#nb:checked {{ background:rgba(255,255,255,.17); }}
    QToolTip {{ background:{t['sd']}; color:#ffffff; border:1px solid {t['ln']}; padding:4px 8px; }}
    QPushButton {{ background:{t['ac']}; color:{t['onac']}; border:0; border-radius:8px; padding:8px 16px; font-weight:700; }}
    QPushButton:hover {{ background:{t['ach']}; }}
    QPushButton[o="true"] {{ background:transparent; color:{t['ink']}; border:1px solid {t['ln']}; }}
    QPushButton[o="true"]:hover {{ background:{t['soft']}; }}
    QLineEdit, QComboBox {{ background:{t['soft']}; border:1px solid {t['ln']}; border-radius:8px; padding:6px 10px; min-height:20px; }}
    QLineEdit:focus, QComboBox:focus {{ border:1px solid {t['ac']}; }}
    QComboBox::drop-down {{ border:0; width:26px; }}
    QComboBox::down-arrow {{ image:url({t['chev']}); width:12px; height:12px; }}
    QComboBox QAbstractItemView {{ background:{t['pn']}; border:1px solid {t['ln']}; selection-background-color:{t['soft']}; selection-color:{t['ink']}; }}
    QTableWidget {{ background:transparent; alternate-background-color:{t['soft']}; border:0; }}
    QTableWidget::item {{ padding:4px 8px; }}
    QHeaderView::section {{ background:transparent; color:{t['mut']}; font-weight:600; border:0; border-bottom:1px solid {t['ln']}; padding:6px 8px; }}
    QListWidget {{ background:transparent; border:0; outline:0; }}
    QListWidget::item {{ padding:10px; border-radius:9px; margin-bottom:2px; }}
    QListWidget::item:selected {{ background:{t['soft']}; color:{t['ink']}; border:1px solid {t['ln']}; }}
    QProgressBar {{ background:{t['soft']}; border:1px solid {t['ln']}; border-radius:8px; min-height:16px; text-align:center; font-weight:700; }}
    QProgressBar::chunk {{ background:{t['ac']}; border-radius:7px; }}
    QSlider::groove:horizontal {{ height:5px; background:{t['ln']}; border-radius:2px; }}
    QSlider::sub-page:horizontal {{ background:{t['ac']}; border-radius:2px; }}
    QSlider::handle:horizontal {{ background:{t['ac']}; width:16px; height:16px; margin:-6px 0; border-radius:8px; border:2px solid {t['pn']}; }}
    QCheckBox {{ spacing:10px; }}
    QCheckBox::indicator {{ width:17px; height:17px; border:1.5px solid {t['mut']}; border-radius:5px; background:{t['pn']}; }}
    QCheckBox::indicator:checked {{ background:{t['ac']}; border-color:{t['ac']}; image:url({t['tick']}); }}
    QScrollBar:vertical {{ background:transparent; width:10px; margin:2px; }}
    QScrollBar::handle:vertical {{ background:{t['ln']}; border-radius:4px; min-height:24px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
    QScrollBar:horizontal {{ background:transparent; height:10px; margin:2px; }}
    QScrollBar::handle:horizontal {{ background:{t['ln']}; border-radius:4px; min-width:24px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
    QScrollArea {{ background:transparent; border:0; }}
    QScrollArea > QWidget > QWidget {{ background:transparent; }}
    """

def gauss():
    return (sum(random.random() for _ in range(4)) - 2) * 1.7

_r = random.Random(7)
STARS = [(_r.random() * 320, _r.random() * 240, .3 + _r.random() * .7) for _ in range(70)]

# --------------------------------------------------------------------------- simulation
class Sim:
    """Stand-in for the closed loop: disturbance -> detector -> Kalman -> pan/tilt controller."""
    def __init__(s):
        s.p = dict(noise=0, blur=0, atm=0, sd=0, jit=0, plat=0)
        s.type, s.running = 'Mixed', True
        s.reset()

    def reset(s):
        s.t = 0.; s.pan = -70.; s.tilt = 45.
        s.kx = s.ky = s.vx = s.vy = s.wx = s.wy = 0.
        s.ox = s.oy = s.mx = s.my = s.dy = 0.
        s.det, s.lock, s.started = True, False, False
        s.fr = s.lk = s.ac = s.loss = 0
        s.err, s.acq, s.events, s.lost_at = [], [], [], 0.

    def log(s, m):
        s.events.insert(0, f"{s.t:.1f}s   {m}"); del s.events[6:]

    def step(s):
        p = s.p; s.t += 1 / 30; t = s.t; a = 40 * p['plat'] + 4
        if s.type == 'Linear':
            dx, dy = a * ((t * .15 % 2) - 1), .2 * a * math.sin(.4 * t)
        elif s.type == 'Orbital':
            dx, dy = a * math.cos(.8 * t), .7 * a * math.sin(.8 * t)
        else:
            dx = .6 * a * math.cos(.8 * t) + .4 * a * math.sin(2.3 * t)
            dy = .5 * a * math.sin(.8 * t) + .3 * a * math.cos(1.7 * t)
        s.wx = s.wx * .97 + gauss() * p['atm'] * 1.5          # atmospheric turbulence
        s.wy = s.wy * .97 + gauss() * p['atm'] * 1.5
        s.dy = dy
        s.ox = dx + s.wx - s.pan + gauss() * p['jit']          # true beacon offset in camera frame
        s.oy = dy + s.wy - s.tilt + gauss() * p['jit']
        sig = p['noise'] * p['sd'] * 3 + .3
        s.det = (random.random() > .004 + p['atm'] * p['noise'] * .06) and abs(s.ox) < 150 and abs(s.oy) < 110
        s.mx, s.my = s.ox + gauss() * sig, s.oy + gauss() * sig  # detector output
        s.kx += s.vx; s.ky += s.vy                               # alpha-beta Kalman
        if s.det:
            rx, ry = s.mx - s.kx, s.my - s.ky
            s.kx += .55 * rx; s.ky += .55 * ry; s.vx += .15 * rx; s.vy += .15 * ry
        s.pan += .4 * s.kx; s.tilt += .4 * s.ky                  # pan/tilt controller
        s.kx *= .6; s.ky *= .6
        e = math.hypot(s.ox, s.oy); lk = e < 60 and s.det
        if lk and not s.lock:
            s.acq.append(t - s.lost_at); s.started = True
            s.log('Lock reacquired' if len(s.acq) > 1 else 'Beacon acquired'); s.lock = True
        elif not lk and s.lock:
            s.lock = False; s.lost_at = t; s.loss += 1; s.log('Lock lost')
        if s.started:
            s.fr += 1; s.lk += lk; s.ac += e < 12
        s.err.append(e); del s.err[:-300]

    retention = property(lambda s: s.lk / s.fr * 100 if s.fr else 0)
    loss_pct = property(lambda s: s.loss / s.fr * 100 if s.fr else 0)
    accuracy = property(lambda s: s.ac / s.fr * 100 if s.fr else 0)
    rmse = property(lambda s: math.sqrt(sum(e * e for e in s.err) / len(s.err)) if s.err else 0)
    acq_avg = property(lambda s: sum(s.acq) / len(s.acq) if s.acq else None)


class Video:
    """State for the imported MP4. The detection itself (YOLO + Kalman, video_tracking.BeaconTracker)
    runs in VideoWorker; this just holds the latest frame / metrics for the Video View widgets."""
    def __init__(s):
        s.worker = None; s.active = False; s.paused = False; s.reset()

    def reset(s):
        s.frame = s.raw = None; s.t = 0.; s.det = False; s.info = {}
        s.err, s.rows, s.n = [], [], 0

    def update(s, img, raw, info):
        s.frame, s.raw, s.info = img, raw, info
        s.t, s.det = info['video_time'], info['detected']
        s.n += 1
        if info['acquisition_complete']:
            s.err.append(info['error']); del s.err[:-300]
        if s.n % 6 == 0:
            bo = info['beacon_offset']
            if not info['acquisition_complete']: state = 'Acquiring' if s.det else 'Searching'
            else: state = 'Tracking' if s.det else 'Target lost'
            s.rows.insert(0, (f"{s.t:.1f}s", f"{bo[0]:.0f}" if bo else '-', f"{bo[1]:.0f}" if bo else '-', state))
            del s.rows[5:]


class VideoWorker(QThread):
    """Reads the MP4 and runs video_tracking.BeaconTracker on every frame, off the GUI thread.
    Pause clears the play event, which stops BOTH the video and the detection; Play resumes both."""
    result = pyqtSignal(object, object, object)   # (annotated QImage, raw QImage, info dict incl. the annotated cv2 frame)
    status = pyqtSignal(str)
    failed = pyqtSignal(str)
    ended = pyqtSignal(str)   # message about the saved tracking CSV

    def __init__(s, path):
        super().__init__(); s.path = path; s.speed = 1.0
        s._play = threading.Event(); s._play.set()
        s._quit = False; s._seek = None

    def play(s): s._play.set()
    def pause(s): s._play.clear()
    def seek_to(s, frac): s._seek = frac
    def stop(s): s._quit = True; s._play.set()

    @staticmethod
    def _qimage(bgr, w, h):
        out = cv2.resize(bgr, (640, int(h * 640 / w)), interpolation=cv2.INTER_AREA) if w > 640 else bgr
        rgb = cv2.cvtColor(out, cv2.COLOR_BGR2RGB)
        return QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.shape[1] * 3, QImage.Format.Format_RGB888).copy()

    def run(s):
        cap = cv2.VideoCapture(s.path)
        if not cap.isOpened():
            s.failed.emit('Could not open the video.'); return
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        if fps <= 0: fps = video_tracking.TRACK_CAMERA_FPS
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        try:
            s.status.emit('Loading YOLO model...')
            tracker = BeaconTracker(w, h, fps)
        except Exception as e:
            cap.release(); s.failed.emit(f'Could not load the detector: {e}'); return
        s.status.emit('Detection running on the imported video (YOLO + Kalman).')
        next_t = time.perf_counter()
        csv_rows = []
        while not s._quit:
            frac, s._seek = s._seek, None
            if frac is not None:
                # Seek: restart tracking from the new position and show one frame even if paused.
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(frac * total) if total > 0 else 0)
                tracker.reset(); csv_rows = []; next_t = time.perf_counter()
            elif not s._play.is_set():
                s._play.wait(0.05); next_t = time.perf_counter(); continue
            ok, frame = cap.read()
            if not ok:
                # End of video: pause, rewind to the start (tracking restarts on the next Play).
                # The tracking CSV is written when the video has played through.
                try: msg = f"Tracking data saved to {video_tracking.write_csv(csv_rows)}"
                except Exception as e: msg = f"Could not save tracking CSV: {e}"
                s._play.clear(); s._seek = 0.0; s.ended.emit(msg); continue
            idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            raw_img = s._qimage(frame, w, h)                 # untouched copy: process() draws on `frame`
            info = tracker.process(frame)
            csv_rows.append(video_tracking.csv_row(info))
            info.update(video_time=idx / fps, frame_index=idx, total=total, pos_frac=idx / total if total > 0 else 0.)
            s.result.emit(s._qimage(frame, w, h), raw_img, info)
            # pace to the video's own frame rate (x speed); if detection is slower, just run flat out
            next_t += 1 / (fps * s.speed); d = next_t - time.perf_counter()
            if d > 0: time.sleep(d)
            elif d < -1: next_t = time.perf_counter()
        cap.release()

# --------------------------------------------------------------------------- custom widgets
def _canvas_bg(q, w, h):
    path = QPainterPath(); path.addRoundedRect(QRectF(0, 0, w, h), 9, 9); q.setClipPath(path); q.fillRect(0, 0, w, h, QColor('#070c18'))

class CamView(QWidget):
    """Video View camera panel. mode 'py': the annotated frame from the video detector (YOLO box,
    Kalman estimate, etc.); mode 'raw': the plain imported mp4. Blank prompt when nothing is imported."""
    def __init__(s, video):
        super().__init__(); s.video = video; s.mode = 'py'; s.setMinimumSize(210, 150)

    def paintEvent(s, _):
        q = QPainter(s); q.setRenderHint(QPainter.RenderHint.Antialiasing); q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = s.width(), s.height(); _canvas_bg(q, w, h); k = min(w / 320, h / 240)
        q.translate((w - 320 * k) / 2, (h - 240 * k) / 2); q.scale(k, k); q.setClipRect(QRectF(0, 0, 320, 240), Qt.ClipOperation.IntersectClip)
        v = s.video
        img = (v.raw if s.mode == 'raw' else v.frame) if v and v.active else None   # 'raw' = plain mp4, nothing drawn on it
        if img is not None:
            iw, ih = img.width(), img.height(); r = min(320 / iw, 240 / ih); dw, dh = iw * r, ih * r
            q.drawImage(QRectF((320 - dw) / 2, (240 - dh) / 2, dw, dh), img)
            return
        q.setPen(QColor('#8fa3c7')); q.drawText(QRectF(0, 0, 320, 240), Qt.AlignmentFlag.AlignCenter,
                                                 'Loading video...' if v and v.active else 'No video imported')


class SatView(QWidget):
    """Unity-style scene: sender camera cone tracking a receiver, laser beam between them."""
    def __init__(s, provider):
        super().__init__(); s.provider = provider; s.setMinimumSize(230, 140)

    def paintEvent(s, _):
        pan, tilt, dy, res = s.provider()
        q = QPainter(s); q.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = s.width(), s.height(); _canvas_bg(q, w, h); k = min(w / 480, h / 270)
        q.translate((w - 480 * k) / 2, (h - 270 * k) / 2); q.scale(k, k); q.setClipRect(QRectF(0, 0, 480, 270), Qt.ClipOperation.IntersectClip)
        sy = 130; ry = sy + dy * .8
        g = QRadialGradient(240, 440, 240); g.setColorAt(.6, QColor('#0e2a55')); g.setColorAt(1, QColor('#1d5fa8'))
        q.setPen(Qt.PenStyle.NoPen); q.setBrush(QBrush(g)); q.drawEllipse(QPointF(240, 440), 230, 230)
        q.setBrush(QColor('#9fb3d9'))
        for sx, sy2, _a in STARS: q.drawRect(QRectF(sx * 1.5, sy2 * 1.1, 1.3, 1.3))
        an = math.atan2(ry - sy, 348) - res * .0025
        cone = QPolygonF([QPointF(66, sy), QPointF(66 + 420 * math.cos(an - .13), sy + 420 * math.sin(an - .13)),
                          QPointF(66 + 420 * math.cos(an + .13), sy + 420 * math.sin(an + .13))])
        q.setBrush(QColor(245, 185, 66, 42)); q.drawPolygon(cone)
        q.setPen(QPen(QColor('#ff5a5f'), 1.5, Qt.PenStyle.DashLine)); q.drawLine(QPointF(414, ry), QPointF(70, sy))
        for cx, cy, c in ((57, sy, '#cfd8ea'), (405, ry, '#8ea0c4')):
            q.setPen(Qt.PenStyle.NoPen); q.setBrush(QColor(c)); q.drawRect(QRectF(cx - 9, cy - 8, 36, 16))
            q.setBrush(QColor('#2f5bea')); q.drawRect(QRectF(cx - 21, cy - 5, 12, 10)); q.drawRect(QRectF(cx + 27, cy - 5, 12, 10))
        q.setPen(QColor('#cfd8ea')); q.setFont(QFont('Sans', 8))
        q.drawText(QPointF(20, sy + 38), 'Sender camera'); q.drawText(QPointF(345, ry - 24), 'Receiver beacon')
        q.drawText(QPointF(14, 256), f"Pan {pan * .05:.1f}°   Tilt {tilt * .05:.1f}°")


class Chart(QWidget):
    def __init__(s, provider, ymax, thresh=0, auto=False):
        super().__init__(); s.provider, s.ymax, s.thresh, s.auto = provider, ymax, thresh, auto; s.setMinimumHeight(110)

    def _ymax(s, a):
        """Fixed ymax, or (auto) the largest value on screen rounded up to a tidy number."""
        if not s.auto or not a: return s.ymax
        m = max(max(a) * 1.15, 5)
        e = 10 ** math.floor(math.log10(m))
        return next(k * e for k in (1, 2, 2.5, 5, 10) if m <= k * e)

    def paintEvent(s, _):
        q = QPainter(s); q.setRenderHint(QPainter.RenderHint.Antialiasing); w, h = s.width(), s.height()
        path = QPainterPath(); path.addRoundedRect(QRectF(0, 0, w, h), 9, 9); q.setClipPath(path); q.fillRect(0, 0, w, h, QColor(T['soft']))
        f = q.font(); f.setPointSize(8); q.setFont(f)
        a = s.provider(); ymax = s._ymax(a); fmt = '.1f' if ymax < 10 else '.0f'
        for i in range(1, 4):
            y = h * i // 4; q.setPen(QPen(QColor(T['ln']), 1)); q.drawLine(0, y, w, y)
            q.setPen(QColor(T['mut'])); q.drawText(QPointF(8, y - 3), f"{ymax * (1 - i / 4):{fmt}}")
        if s.thresh:
            y = h - s.thresh / ymax * h; q.setPen(QPen(QColor(T['wn']), 1, Qt.PenStyle.DashLine)); q.drawLine(QPointF(0, y), QPointF(w, y))
            q.setPen(QColor(T['wn'])); q.drawText(QPointF(w - 64, y - 4), 'lock zone')
        if len(a) > 1:
            pts = [QPointF(i / 299 * w, h - min(v, ymax) / ymax * h) for i, v in enumerate(a)]
            line = QPainterPath(pts[0])
            for p in pts[1:]: line.lineTo(p)
            fill = QPainterPath(line); fill.lineTo(pts[-1].x(), h); fill.lineTo(pts[0].x(), h); fill.closeSubpath()
            g = QLinearGradient(0, 0, 0, h); c1 = QColor(T['ac']); c1.setAlpha(90); c2 = QColor(T['ac']); c2.setAlpha(0); g.setColorAt(0, c1); g.setColorAt(1, c2)
            q.fillPath(fill, QBrush(g)); q.setPen(_pen(T['ac'], 1.8)); q.setBrush(Qt.BrushStyle.NoBrush); q.drawPath(line)

class BarChart(QWidget):
    """Vertical bar chart for comparing a metric across scenarios/runs. Bars are colour-coded
    green/red against a spec threshold when one is supplied (SPEC_THRESH), else drawn in the
    accent colour. `provider` returns (labels, values)."""
    def __init__(s, provider, thresh=None, fmt='{:.1f}'):
        super().__init__(); s.provider, s.thresh, s.fmt = provider, thresh, fmt; s.setMinimumHeight(150)

    def paintEvent(s, _):
        q = QPainter(s); q.setRenderHint(QPainter.RenderHint.Antialiasing); w, h = s.width(), s.height()
        path = QPainterPath(); path.addRoundedRect(QRectF(0, 0, w, h), 9, 9); q.setClipPath(path); q.fillRect(0, 0, w, h, QColor(T['soft']))
        labels, values = s.provider()
        if not values: q.end(); return
        top, bot, lp = 10, 30, 8
        vmax = max(max(values) * 1.15, (s.thresh[0] if s.thresh else 0) * 1.15, 1e-6)
        n = len(values); bw = max((w - 2 * lp) / n * .58, 3); gap = (w - 2 * lp) / n
        f = q.font(); f.setPointSize(7); q.setFont(f)
        if s.thresh:
            lim, lower_better = s.thresh; y = h - bot - lim / vmax * (h - top - bot)
            q.setPen(QPen(QColor(T['wn']), 1, Qt.PenStyle.DashLine)); q.drawLine(QPointF(lp, y), QPointF(w - lp, y))
            q.setPen(QColor(T['wn'])); q.drawText(QPointF(w - lp - 74, y - 4), f"spec limit {lim:g}")
        for i, v in enumerate(values):
            x = lp + gap * i + (gap - bw) / 2; bh = max(v, 0) / vmax * (h - top - bot); y = h - bot - bh
            ok = True
            if s.thresh:
                lim, lower_better = s.thresh; ok = (v <= lim) if lower_better else (v >= lim)
            q.setPen(Qt.PenStyle.NoPen); q.setBrush(QColor(T['ok'] if (s.thresh and ok) else (T['bc'] if s.thresh else T['ac'])))
            q.drawRoundedRect(QRectF(x, y, bw, bh), 3, 3)
            q.setPen(QColor(T['ink'])); q.drawText(QRectF(x - 10, y - 14, bw + 20, 12), Qt.AlignmentFlag.AlignHCenter, s.fmt.format(v))
            q.setPen(QColor(T['mut'])); lab = labels[i] if i < len(labels) else ''
            if len(lab) > 10: lab = lab[:9] + '…'
            q.save(); q.translate(x + bw / 2, h - bot + 4); q.rotate(-40); q.drawText(QPointF(-len(lab) * 3, 8), lab); q.restore()


class WeightBar(QWidget):
    """Horizontal stacked bar showing the SIH evaluation-stage weightages, with a legend."""
    def __init__(s, segments):
        super().__init__(); s.segments = segments; s.setMinimumHeight(74)

    def paintEvent(s, _):
        q = QPainter(s); q.setRenderHint(QPainter.RenderHint.Antialiasing); w = s.width(); bh = 26
        x = 0; total = sum(v for _, v, _, _ in s.segments)
        for name, v, color, _ in s.segments:
            bw = w * v / total; q.setPen(Qt.PenStyle.NoPen); q.setBrush(QColor(color)); q.drawRect(QRectF(x, 0, bw, bh))
            q.setPen(QColor('#ffffff')); f = q.font(); f.setBold(True); f.setPointSize(9); q.setFont(f)
            if bw > 34: q.drawText(QRectF(x, 0, bw, bh), Qt.AlignmentFlag.AlignCenter, f"{v}%")
            x += bw
        y = bh + 14; f = q.font(); f.setBold(False); f.setPointSize(8); q.setFont(f); lx = 0
        for name, v, color, _ in s.segments:
            q.setPen(Qt.PenStyle.NoPen); q.setBrush(QColor(color)); q.drawRoundedRect(QRectF(lx, y, 10, 10), 2, 2)
            q.setPen(QColor(T['ink'])); tw = q.fontMetrics().horizontalAdvance(name) + 24
            q.drawText(QPointF(lx + 14, y + 9), name); lx += tw
            if lx > w - 80: lx = 0; y += 18

# --------------------------------------------------------------------------- data
SC = [('Static beacon, near', 94.2, .15, 2.8, 0, 95, 10.5), ('Moving, far', 81.5, .78, 7.2, 1, 88, 11.4),
      ('Crowded environment', 76.1, 1.12, 11.5, 3, 72, 13.9), ('Occlusion event', 88, .35, 5.1, 2, 90, 11.1),
      ('Low light', 79.3, .95, 9.8, 2, 82, 12.2), ('Multi-beacon', 84.7, .6, 6.5, 1, 78, 12.8),
      ('Varying angle', 90.2, .28, 4, 0, 92, 10.9), ('High speed', 86.8, .52, 8.9, 2, 110, 9.1),
      ('Intermittent signal', 74, 1.45, 14.1, 5, 85, 11.8), ('Complex path', 89.5, .4, 4.8, 1, 80, 12.5)]
CR = ['AP@50-95 (%)', 'Acquisition (s)', 'Tracking error (px)', 'Target loss', 'Speed (FPS)', 'Update (ms)']
FM = [1, 2, 2, 0, 0, 1]
# Pass/fail reference lines pulled from the SIH problem-statement performance table (§16-20).
# None = no hard spec threshold for that column; else (limit, lower_is_better).
SPEC_THRESH = [None, (2.0, True), (10.0, True), (1.0, True), (20.0, False), None]
PARAMS = [('noise', 'Noise level', 100, 100, 0), ('blur', 'Blur Level', 100, 100, 0),
          ('atm', 'Atmospheric disturbance', 100, 100, 0), ('sd', 'Max standard deviation (px)', 50, 10, 0),
          ('jit', 'Max camera jitter (px)', 30, 10, 0), ('plat', 'Platform motion', 100, 100, 0),]

# --------------------------------------------------------------------------- spec reference (from problem statement PDF)
SPEC_CAMERA = [('Screen size (min.)', '2000 x 2000 px', 'User-defined'), ('Camera type', 'Monochrome, focal plane array', 'Colour optional'),
               ('Camera resolution', '640 x 480 px', 'User-defined'), ('Camera FOV', '4° x 3°', 'User-defined'),
               ('Update rate', '30 Hz (min.)', '-'), ('Initial position', 'Centre of screen', '-')]
SPEC_TARGET = [('Target type', 'Beacon spot', '-'), ('Number of targets', '1 (mandatory)', 'Multiple optional'),
               ('Target shape', 'Square (default)', 'User-defined'), ('Target size', '10 x 10 px (default)', '5-20 x 5-20 px'),
               ('Initial location', 'Random (default)', 'User-defined'),
               ('Motion', 'Straight line / Circular / Fig-8 / Random', 'Spiral, sinusoidal optional')]
SPEC_MOTION = [('Max. pan speed', '5°/s (default)', '5-10 °/s'), ('Max. tilt speed', '5°/s (default)', '5-10 °/s'),
               ('Update interval', '≥ 20 Hz', '-')]
SPEC_PERF = [('Acquisition time', '≤ 2 s'), ('Tracking error', '≤ 10 px'), ('Target loss', '< 5 %'),
             ('Re-acquisition time', '≤ 1 s'), ('Processing speed', '≥ 20 FPS')]
SPEC_NOISE = [('Image noise', 'Salt & pepper (~10%), Gaussian, Poisson — user selectable'),
              ('Max. noise std. dev.', '20 px (user-defined)'), ('Max. camera jitter', '± 20 px/frame (user-defined)'),
              ('Atmospheric disturbance', 'Clear, haze, fog, rain, low light — reduces contrast/brightness'),
              ('Platform motion', '± 20 px/frame max. — linear default, circular/random/spiral/fig-8 optional')]
SPEC_EVAL = [('Functional verification', 20, '#2454e6', 'Live demo of all mandatory functions, operational success, GUI'),
             ('Benchmark performance-1', 30, '#0b8a6a', 'In-house scenario suite: centroiding error log + auto-generated performance logs'),
             ('Benchmark performance-2', 30, '#b26a00', 'Supplied 30fps MP4s with noise: bypass PTZ camera, feed video into coarse pointing system'),
             ('Technical evaluation', 20, '#d63b45', 'Architecture, algorithm choice, AI/CV approach, innovation, documentation, Q&A')]

def panel(title, *widgets):
    f = QFrame(); f.setObjectName('panel'); l = QVBoxLayout(f); l.setContentsMargins(16, 14, 16, 16); l.setSpacing(10)
    h = QLabel(title); h.setObjectName('h3'); l.addWidget(h)
    for w in widgets: l.addWidget(w, 1 if w is widgets[-1] else 0)
    return f

def panel_with_header_control(title, control, *widgets):
    """Same as panel(), but with an extra widget (e.g. a QComboBox) pushed to the far
    right of the title row via a stretch, rather than sitting right beside the title."""
    f = QFrame(); f.setObjectName('panel'); l = QVBoxLayout(f); l.setContentsMargins(16, 14, 16, 16); l.setSpacing(10)
    hd = QWidget(); hl = QHBoxLayout(hd); hl.setContentsMargins(0, 0, 0, 0)
    h = QLabel(title); h.setObjectName('h3')
    hl.addWidget(h); hl.addStretch(); hl.addWidget(control)
    l.addWidget(hd)
    for w in widgets: l.addWidget(w, 1 if w is widgets[-1] else 0)
    return f

def header(title, sub, *btns):
    w = QWidget(); l = QHBoxLayout(w); l.setContentsMargins(0, 0, 0, 0); l.setSpacing(12)
    t = QLabel(title); t.setObjectName('h1'); sb = QLabel(sub); sb.setObjectName('mut')
    l.addWidget(t); l.addWidget(sb); l.addStretch()
    for b in btns: l.addWidget(b)
    return w, sb

def btn(text, outline=False, fn=None):
    b = QPushButton(text); b.setProperty('o', outline); b.setCursor(Qt.CursorShape.PointingHandCursor)
    if fn: b.clicked.connect(fn)
    return b

def table(cols, rows=0):
    t = QTableWidget(rows, len(cols)); t.setHorizontalHeaderLabels(cols); t.verticalHeader().hide(); t.setShowGrid(False)
    t.setFrameShape(QFrame.Shape.NoFrame); t.setAlternatingRowColors(True); t.verticalHeader().setDefaultSectionSize(32)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); return t

def scroll_wrap(inner, h_as_needed=True):
    """Wrap a widget in a borderless, theme-transparent QScrollArea. The widget keeps filling
    the viewport (and its layout stretch factors keep working) whenever there's enough room;
    scrollbars only appear once the content genuinely doesn't fit, so nothing gets clipped."""
    sc = QScrollArea(); sc.setWidgetResizable(True); sc.setFrameShape(QFrame.Shape.NoFrame)
    sc.setWidget(inner); sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if h_as_needed else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sc.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    return sc

def page(*items, stretch=None):
    w = QWidget(); w.setObjectName('page'); l = QVBoxLayout(w); l.setContentsMargins(22, 20, 22, 20); l.setSpacing(14)
    for i, x in enumerate(items): l.addWidget(x, stretch[i] if stretch else 0)
    return scroll_wrap(w), l

def row(*ws):
    w = QWidget(); l = QHBoxLayout(w); l.setContentsMargins(0, 0, 0, 0); l.setSpacing(14)
    for x in ws: l.addWidget(x, 1)
    return w

# --------------------------------------------------------------------------- Scene-Parameters builders
# Everything below is used only by build_scene_params() to keep its four panels'
# rows aligned in a single shared grid per panel (rather than one independent
# mini-layout per row, which is what previously let rows drift out of line with
# each other). See the "SCENE-PARAMETERS LAYOUT" block further down for usage.
def panel_top(title, icon_kind, *widgets):
    """Like panel(), but (a) draws a small icon beside the title, and (b) never
    stretches the last widget to fill leftover panel height — instead any extra
    space collects below everything, so rows stay at their natural height and
    evenly spaced instead of one row silently stretching to fill the panel."""
    f = QFrame(); f.setObjectName('panel'); l = QVBoxLayout(f); l.setContentsMargins(16, 14, 16, 16); l.setSpacing(12)
    hd = QWidget(); hl = QHBoxLayout(hd); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(8)
    ic = QLabel(); ic.setPixmap(draw_icon(icon_kind, T['ac'], 18))
    ttl = QLabel(title); ttl.setObjectName('h3')
    hl.addWidget(ic); hl.addWidget(ttl); hl.addStretch()
    l.addWidget(hd)
    for w in widgets: l.addWidget(w, 0)
    l.addStretch(1)
    return f

def scene_grid(paired=False):
    """A QGridLayout-backed container for one panel's rows. With paired=False every
    row is label|control, control filling the full remaining width (Satellite
    Settings, Disturbances). With paired=True the grid has two label|control pairs
    per row (label|control|label|control) so 'Colour'+'Blink' and 'Shape'+'Size'
    line up with each other and with the full-width rows above/below them
    (Beacon Settings)."""
    w = QWidget(); g = QGridLayout(w); g.setContentsMargins(0, 0, 0, 0)
    g.setVerticalSpacing(12); g.setHorizontalSpacing(10); g.setColumnStretch(1, 1)
    if paired: g.setColumnStretch(3, 1)
    return w, g

def grid_full(g, row_i, label, widget):
    """One label + one control, the control filling the entire rest of the row."""
    g.addWidget(QLabel(label), row_i, 0); g.addWidget(widget, row_i, 1, 1, 3)

def grid_half(g, row_i, side, label, widget):
    """Left half (side=0, columns 0-1) or right half (side=1, columns 2-3) of a
    paired row — used only with scene_grid(paired=True)."""
    c0 = 0 if side == 0 else 2
    g.addWidget(QLabel(label), row_i, c0); g.addWidget(widget, row_i, c0 + 1)

def mk_combo(options):
    cb = QComboBox(); cb.addItems(options); return cb

def mk_toggle(default=True):
    """ON/OFF pill button for boolean controls (e.g. Blink)."""
    b = QPushButton('ON' if default else 'OFF'); b.setCheckable(True); b.setChecked(default)
    b.setFixedWidth(64); b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.toggled.connect(lambda v: b.setText('ON' if v else 'OFF'))
    return b

def mk_slider(mn, mx, default, suffix='', divisor=1):
    """Returns (row_widget, slider) — row_widget (slider + live value label) is
    what goes in the grid; slider is what save_scene_settings() reads the value from.
    `divisor` lets the slider's raw integer steps (what QSlider natively works in)
    display as a fraction — e.g. mn=0, mx=100, divisor=100 gives a 0.00-1.00 range
    in 0.01 increments per step, while the slider itself just moves 0-100."""
    row_w = QWidget(); rl = QHBoxLayout(row_w); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(8)
    sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(mn, mx); sl.setValue(default)
    sl.setProperty('divisor', divisor)   # read back by save_scene_settings()'s value_of()
    disp = lambda v: f"{v / divisor:g}{suffix}"
    val = QLabel(disp(default)); val.setFixedWidth(40); val.setAlignment(Qt.AlignmentFlag.AlignRight)
    sl.valueChanged.connect(lambda v: val.setText(disp(v)))
    rl.addWidget(sl, 1); rl.addWidget(val)
    return row_w, sl

# ============================================================

# --------------------------------------------------------------------------- main window
class Main(QMainWindow):
    def __init__(s):
        super().__init__(); s.setWindowTitle('FSOC Vision Stabilization Console')
        s.sim, s.video = Sim(), Video(); s.speed, s.acc, s.vacc = 1.0, 0.0, 0.0
        s.bench = [dict(name='Deck baseline', type='Standard scenario suite', date='From SIH deck', cols=list(range(6)), rows=list(SC))]
        s.sel = 0; s.bt = QTimer(s); s.bt.timeout.connect(s.bench_step)
        root = QWidget(); s.setCentralWidget(root); hl = QHBoxLayout(root); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(0)
        hl.addWidget(s.build_nav()); s.stack = QStackedWidget(); hl.addWidget(s.stack, 1)
        for p in (s.build_sim(), s.build_scene_params(), s.build_video(), s.build_bench(), s.build_data(), s.build_spec()): s.stack.addWidget(p)
        s.sim_rail = s.build_sim_rail(); s.video_rail = s.build_video_rail()
        s.rail_stack = QStackedWidget(); s.rail_stack.setFixedWidth(300)
        s.rail_stack.addWidget(s.sim_rail); s.rail_stack.addWidget(s.video_rail)
        hl.addWidget(s.rail_stack)
        s.go(0); s.apply_theme(False); s.draw_data()
        s.timer = QTimer(s); s.timer.timeout.connect(s.tick); s.timer.start(33)

        # ---- real Unity + YOLO/Kalman tracking (replaces the fake sim in Sim View) ----
        s.real_mode = True
        s.unity_proc = None
        s.unity_hwnd = None
        s._unity_parent = None  # whichever container (Sim View / Video View) currently hosts the Unity window
        s._embed_attempts = 0
        s.rt_events = []  # rolling log fed into the Events panel

        # Rolling window of the real per-frame tracking error (px), used to drive the
        # "Tracking performance" chart in Sim View instead of the fake Sim.err buffer.
        s.rt_err_history = deque(maxlen=300)

        # Latest values reported by backend.TrackingThread.stats_ready, used to fill in
        # the Tracking performance panel's Live column (lock retention, RMSE, acquisition
        # time, target loss count, accuracy) instead of the fake Sim properties.
        s.rt_stats = dict(rmse=None, lock_retention=0.0, acquisition_time=None,
                           target_losses=0, accuracy=0.0)

        s.tracking_thread = TrackingThread()
        s.tracking_thread.frame_ready.connect(s.on_frame_ready)
        s.tracking_thread.status_changed.connect(s.on_status_changed)
        s.tracking_thread.stats_ready.connect(s.on_stats_ready)
        s.tracking_thread.start()
        # Stay paused until "Start Simulation" is pressed on Sim View — Unity launches
        # and connects automatically below, but sends/receives nothing useful until
        # then. pause()/is_paused() are safe to call this early: they just flip a
        # flag the run loop already checks continuously, the same one toggle_sim()
        # uses later while the thread is mid-loop.
        s.tracking_thread.pause()

        # Launch Unity automatically instead of waiting for a button press. The
        # "Start Unity" button still exists (and now starts disabled-after-launch,
        # same as a manual click would leave it) in case Unity needs restarting.
        
        # ........................................................................................
        # QTimer.singleShot(0, s.start_unity)

    # ---- shell
    def build_nav(s):
        f = QFrame(); f.setObjectName('nav'); f.setFixedWidth(76); l = QVBoxLayout(f); l.setContentsMargins(0, 18, 0, 16); l.setSpacing(8)
        logo = QLabel(); logo.setPixmap(beacon_logo()); logo.setAlignment(Qt.AlignmentFlag.AlignCenter); l.addWidget(logo); l.addSpacing(10)
        s.grp = QButtonGroup(s); ctr = Qt.AlignmentFlag.AlignHCenter
        for i, (k, tip) in enumerate((('sim', 'Sim View'), ('scene', 'Scene-Parameters'), ('video', 'Video View'), ('bench', 'Benchmark'), ('data', 'Data-Check'), ('info', 'Spec Reference'))):
            b = QPushButton(); b.setObjectName('nb'); b.setCheckable(True); b.setIcon(make_icon(k)); b.setIconSize(QSize(26, 26))
            b.setFixedSize(52, 48); b.setToolTip(tip); b.setAccessibleName(tip); b.setCursor(Qt.CursorShape.PointingHandCursor)
            s.grp.addButton(b, i); l.addWidget(b, 0, ctr)
        s.grp.idClicked.connect(s.go); l.addStretch()
        th = QPushButton(); th.setObjectName('nb'); th.setIcon(make_icon('theme')); th.setIconSize(QSize(26, 26)); th.setFixedSize(52, 48)
        th.setToolTip('Switch light / dark theme'); th.setAccessibleName('Switch theme'); th.setCursor(Qt.CursorShape.PointingHandCursor)
        th.clicked.connect(lambda: s.apply_theme(True)); l.addWidget(th, 0, ctr); return f

    def go(s, i):
        s.stack.setCurrentIndex(i); s.grp.button(i).setChecked(True)
        if i == 0: s.refresh_scene_list()   # pick up any scene saved since Sim View was last shown
        if hasattr(s, 'rail_stack'):
            show_rail = i in (0, 2)
            s.rail_stack.setVisible(show_rail)
            if show_rail:
                s.rail_stack.setCurrentIndex(0 if i == 0 else 1)
                s._refresh_rail_layout()
        s._reparent_unity_to_tab(i)
        s._apply_view_for_tab(i)

    def _apply_view_for_tab(s, i):
        """Video View (i==2) always uses TrackingThread.second_view(). Sim View (i==0)
        always uses whichever of sat_pov() / second_view() the dropdown currently has
        selected — re-invoked every time Sim View is switched to, not just when the
        dropdown itself changes. No-ops until tracking_thread exists (e.g. during the
        early s.go(0) call in __init__) and on any other tab (Scene-Parameters, etc.)."""
        tt = getattr(s, 'tracking_thread', None)
        if tt is None:
            return
        if i == 2:
            tt.third_view()
        elif i == 0:
            s._invoke_sat_view(getattr(s, 'selected_sat_view', 'Satellite Pov'))

    def _reparent_unity_to_tab(s, i):
        """Sim View (i==0) and Video View (i==2) each have their own native-window
        container for the embedded Unity view (s.unity_container / s.vsat). A Win32
        HWND can only be a child of one parent at a time, so re-parent the real Unity
        window to whichever of the two containers is on screen right now. No-ops until
        Unity has actually been started (unity_hwnd set) and safe to call from go(0)
        during __init__, before the real-mode attributes below even exist yet."""
        if not getattr(s, 'unity_hwnd', None):
            return
        target = s.unity_container if i == 0 else (s.vsat if i == 2 else None)
        if target is None or target is s._unity_parent:
            return
        s._unity_parent = target
        win32gui.SetParent(s.unity_hwnd, int(target.winId()))
        s.resize_unity_window()
        QTimer.singleShot(150, s.nudge_unity_render_loop)

    def _refresh_rail_layout(s):
        """Qt's QHBoxLayout can leave a stale cached size for a fixed-width sibling (the
        rail) and for word-wrapped QLabels inside it after the sibling has been hidden and
        re-shown via a QStackedWidget switch. Re-maximizing the window used to be the only
        thing that forced a fresh resize event and fixed it - do the equivalent here instead.
        Operates on whichever of sim_rail / video_rail is the current page of rail_stack."""
        cur = s.rail_stack.currentWidget()
        inner = getattr(cur, 'rail_inner', cur)
        for lab in inner.findChildren(QLabel):
            if lab.wordWrap(): lab.setWordWrap(False); lab.setWordWrap(True)
        lay = inner.layout()
        if lay: lay.invalidate(); lay.activate()
        inner.updateGeometry(); cur.updateGeometry()
        root_lay = s.centralWidget().layout()
        root_lay.invalidate(); root_lay.activate()
        s.centralWidget().updateGeometry()

    def apply_theme(s, toggle):
        if toggle: T.update(DARK if T['bg'] == LIGHT['bg'] else LIGHT)
        k = T['bg'][1:]; T['tick'] = asset('tick' + k, _tick, 16); T['chev'] = asset('chev' + k, _chev, 12)
        pal = QPalette(); R = QPalette.ColorRole
        for role, key in ((R.Window, 'bg'), (R.WindowText, 'ink'), (R.Base, 'pn'), (R.AlternateBase, 'soft'), (R.Text, 'ink'),
                          (R.Button, 'pn'), (R.ButtonText, 'ink'), (R.Highlight, 'ac'), (R.HighlightedText, 'onac')):
            pal.setColor(role, QColor(T[key]))
        QApplication.instance().setPalette(pal); s.setStyleSheet(qss()); s._lk = None
        for w in s.findChildren(QWidget): w.update()

    def build_sim_rail(s):
        f = QFrame(); l = QVBoxLayout(f); l.setContentsMargins(0, 20, 16, 20); l.setSpacing(14)
        s.r = {k: QLabel('-') for k in ('det', 'pan', 'tilt', 'off', 'time', 'fps')}
        s.ls = QLabel('Searching'); s.ls.setAlignment(Qt.AlignmentFlag.AlignCenter)
        def kv(name, w):
            r = QWidget(); h = QHBoxLayout(r); h.setContentsMargins(0, 0, 0, 0); a = QLabel(name); a.setObjectName('mut')
            w.setStyleSheet('font-weight:700'); h.addWidget(a); h.addStretch(); h.addWidget(w); return r
        s.pdet = QLabel('Waiting...')
        s.pkal = QLabel('Not initialized')
        s.punity = QLabel('Not started')
        l.addWidget(panel('Link status', s.ls, kv('Beacon', s.r['det'])))
        l.addWidget(panel('Gimbal', kv('Pan', s.r['pan']), kv('Tilt', s.r['tilt']), kv('Offset from centre', s.r['off']),
                          kv('Elapsed', s.r['time']), kv('Render rate', s.r['fps'])))
        l.addWidget(panel('Pipeline', kv('Scene (Unity)', s.punity), kv('Detector (YOLO)', s.pdet),
                          kv('Kalman filter', s.pkal), kv('Pan/tilt controller', QLabel('Running'))))
        s.evl = QLabel(''); s.evl.setObjectName('mut'); s.evl.setWordWrap(True); s.evl.setAlignment(Qt.AlignmentFlag.AlignTop); s.evl.setMinimumHeight(120)
        l.addWidget(panel('Events', s.evl)); l.addStretch(); s.fps, s._last = 30.0, 0
        sc = scroll_wrap(f, h_as_needed=False); sc.rail_inner = f; return sc

    def build_video_rail(s):
        """Right-side panel shown on Video View — distinct from Sim View's rail (gimbal
        telemetry / Unity pipeline). This one summarizes the imported video source,
        detector status and playback position instead."""
        f = QFrame(); l = QVBoxLayout(f); l.setContentsMargins(0, 20, 16, 20); l.setSpacing(14)
        s.vr = {k: QLabel('-') for k in ('src', 'state', 'speed', 'det', 'off', 'pan', 'tilt', 'time', 'frame', 'mode', 'rmse', 'lock', 'acc', 'loss')}
        def kv(name, w):
            r = QWidget(); h = QHBoxLayout(r); h.setContentsMargins(0, 0, 0, 0); a = QLabel(name); a.setObjectName('mut')
            w.setStyleSheet('font-weight:700'); h.addWidget(a); h.addStretch(); h.addWidget(w); return r
        for lab in s.vr.values(): lab.setWordWrap(True)
        l.addWidget(panel('Source', kv('File', s.vr['src']), kv('Playback', s.vr['state']), kv('Speed', s.vr['speed'])))
        l.addWidget(panel('Detector', kv('Beacon', s.vr['det']), kv('Offset from centre', s.vr['off']),
                  kv('Pan', s.vr['pan']), kv('Tilt', s.vr['tilt']), kv('Mode', s.vr['mode'])))
        l.addWidget(panel('Tracking performance', kv('RMSE', s.vr['rmse']), kv('Lock retention', s.vr['lock']),
                          kv('Accuracy', s.vr['acc']), kv('Target losses', s.vr['loss'])))
        l.addWidget(panel('Playback position', kv('Elapsed', s.vr['time']), kv('Frame', s.vr['frame'])))
        l.addStretch()
        sc = scroll_wrap(f, h_as_needed=False); sc.rail_inner = f; return sc

    # ---- Sim View
    def build_sim(s):
        s.pz = btn('Start Simulation', True, s.toggle_sim); rs = btn('Reset scenario', False, s.sim.reset)
        s.start_unity_btn = btn('Start Unity', False, s.start_unity)
        hd, _ = header('Live simulation', 'Python tracker driving the Unity gimbal in a closed loop', s.start_unity_btn, s.pz, rs)

        # ---- real live views (replacing the fake CamView/SatView painters) ----
        s.cam = QLabel('Waiting for tracking feed...')
        s.cam.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s.cam.setStyleSheet('background-color:#070c18; color:#8fa3c7; border-radius:9px;')
        s.cam.setMinimumSize(210, 150)
        s.cam.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        s.unity_container = QWidget()
        s.unity_container.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        s.unity_container.setStyleSheet('background-color:#070c18; border-radius:9px;')
        s.unity_container.setMinimumSize(230, 140)
        s.sat = s.unity_container  # keep name `s.sat` so the shared tick() loop still finds it

        cw = QWidget(); g = QGridLayout(cw); g.setContentsMargins(0, 0, 0, 0); g.setVerticalSpacing(12); g.setColumnStretch(1, 1)
        # Test-case scene picker — options are the .txt scene files saved from the
        # Scene-Parameters tab into SCENES_DIR (see the constant near the top of this
        # file and refresh_scene_list()), placed first so a scenario can be picked
        # before touching the other controls. "Load scene" sends the chosen file's
        # name to backend.TrackingThread.parsed() (load_selected_scene()).
        tc_row = QWidget(); tc_l = QHBoxLayout(tc_row); tc_l.setContentsMargins(0, 0, 0, 0); tc_l.setSpacing(8)
        s.test_case = QComboBox(); s.test_case.currentTextChanged.connect(s.on_test_case_changed)
        s.load_scene_btn = QPushButton('Load scene'); s.load_scene_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        s.load_scene_btn.clicked.connect(s.load_selected_scene)
        # Small progress bar that fills over ~2.5s as visual feedback while a scene
        # loads (see _play_load_scene_animation()) — hidden the rest of the time.
        s.load_progress = QProgressBar(); s.load_progress.setRange(0, 100)
        s.load_progress.setFixedWidth(110); s.load_progress.setTextVisible(False); s.load_progress.hide()
        tc_l.addWidget(s.test_case, 1); tc_l.addWidget(s.load_scene_btn); tc_l.addWidget(s.load_progress)
        s.refresh_scene_list()   # populate the combo now that it exists
        g.addWidget(QLabel('Test case scene'), 0, 0); g.addWidget(tc_row, 0, 1, 1, 2)
        s.mt = QComboBox(); s.mt.addItems(['Straight Horizontal', 'Straight Vertical', 'Figure 8', 'Circular', 'Mixed']); s.mt.setCurrentText('Mixed')
        s.mt.currentTextChanged.connect(s.on_movement_changed)
        g.addWidget(QLabel('Satellite movement type'), 1, 0); g.addWidget(s.mt, 1, 1, 1, 2)
        for i, (k, lab, mx, dv, df) in enumerate(PARAMS, 2):
            sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(0, mx); sl.setValue(int(df * dv)); val = QLabel(f"{df:g}")
            sl.valueChanged.connect(lambda v, k=k, dv=dv, val=val: (s.sim.p.__setitem__(k, v / dv), val.setText(f"{v / dv:g}"),s.slide_change(list(s.sim.p.values()))))
            g.addWidget(QLabel(lab), i, 0); g.addWidget(sl, i, 1); g.addWidget(val, i, 2)
        pw = QWidget(); pg = QGridLayout(pw); pg.setContentsMargins(0, 0, 0, 0); pg.setVerticalSpacing(8); pg.setColumnStretch(0, 1); s.k = []
        for j, (n, tg) in enumerate((('Lock retention', '98.2%'), ('Tracking RMSE', '6.1 px'), ('Acquisition time', '0.73 s'),
                                     ('Target loss', '<1.8%'), ('Accuracy (within 12 px)', '-'))):
            lv = QLabel('-'); lv.setStyleSheet('font-weight:700'); s.k.append(lv)
            tl = QLabel(tg); tl.setObjectName('mut'); pg.addWidget(QLabel(n), j + 1, 0); pg.addWidget(lv, j + 1, 1); pg.addWidget(tl, j + 1, 2)
        for c, n in enumerate(('Metric', 'Live', 'Deck target')):
            h = QLabel(n); h.setObjectName('mut'); pg.addWidget(h, 0, c)
        # Feed the chart from the real per-frame error history (backend.py's `e` values,
        # collected in rt_err_history) once real tracking is running; fall back to the
        # fake Sim.err buffer only if real_mode is somehow off.
        s.chart = Chart(lambda: list(s.rt_err_history) if s.real_mode else s.sim.err, 120, 60)
        perf = panel('Tracking performance', pw, QLabel('Graphical view: error over time (px)'), s.chart)
        # View-mode picker for the embedded Unity panel — sits on the right of the panel's
        # title row (not right beside the title text) via panel_with_header_control's stretch.
        s.sat_view = QComboBox(); s.sat_view.addItems(['Satellite Pov', 'Satellite motion view'])
        s.sat_view.setFixedWidth(180)
        s.sat_view.currentTextChanged.connect(s.on_sat_view_changed)
        s.selected_sat_view = s.sat_view.currentText()
        unity_panel = panel_with_header_control('Unity (live, embedded)', s.sat_view, s.sat)
        w, l = page(hd, row(panel('Python-side view (live)', s.cam), unity_panel), row(panel('Scenario controls', cw), perf), stretch=[0, 5, 4]); return w

    def slide_change(s, val):
        print("sluder was changed:!!!!! and the list: ", val, s.sim.running)
        tt = getattr(s, 'tracking_thread', None)
        if tt is None:
            return
        else:
            tt.set_effects(val[:3])

    def toggle_sim(s):
        """First press starts the (already-running, already-connected-to-Unity) tracking
        loop that begins life paused in __init__; every press after that just pauses or
        resumes it same as before. Deliberately does not touch s.sim.running (the fake
        fallback demo) — that belongs to Video View's own Pause button (toggle_video),
        kept fully separate so the two Pause/Resume buttons never affect each other's tab."""
        tt = getattr(s, 'tracking_thread', None)
        if tt is None:
            return
        if tt.is_paused():
            tt.resume()
        else:
            tt.pause()
        s.pz.setText('Pause' if not tt.is_paused() else 'Start Simulation')

    def on_movement_changed(s, name):
        """Satellite movement type combo. Keeps the fake Sim's type/reset as harmless
        housekeeping (unused visually while real_mode is on), and forwards the selected
        option straight to backend.TrackingThread.movement_changed(name)."""
        s.sim.type = name; s.sim.reset()
        tt = getattr(s, 'tracking_thread', None)
        if tt is not None:
            tt.movement_changed(name)
        s.on_status_changed(f"Satellite movement type: {name}")

    def on_test_case_changed(s, name):
        """Selecting a scene here just records the choice and logs it — it does not load
        it into the tracker. The "Load scene" button next to this dropdown is what
        actually sends it to backend.TrackingThread.parsed() (see load_selected_scene())."""
        s.selected_test_case = name
        s.on_status_changed(f"Test case scene selected: {name}")

    def refresh_scene_list(s):
        """Re-reads SCENES_DIR for .txt scene files and repopulates the Sim View
        "Test case scene" dropdown with their names (the file names, without the
        .txt extension). Called when Sim View is first built, again every time
        Save is pressed on the Scene-Parameters tab, and again whenever the user
        navigates to Sim View (see go()), so a newly saved scene shows up without
        restarting the app. Keeps the current selection if it still exists."""
        try:
            names = sorted(os.path.splitext(os.path.basename(p))[0]
                            for p in glob.glob(os.path.join(SCENES_DIR, '*.txt')))
        except OSError:
            names = []
        if not hasattr(s, 'test_case'):
            return
        current = s.test_case.currentText()
        s.test_case.blockSignals(True)
        s.test_case.clear(); s.test_case.addItems(names)
        if current in names: s.test_case.setCurrentText(current)
        s.test_case.blockSignals(False)
        s.selected_test_case = s.test_case.currentText()

    def load_selected_scene(s):
        """"Load scene" button beside the Test case scene dropdown. Passes the
        selected scene's file name (without the .txt extension, exactly as shown
        in the dropdown) to backend.TrackingThread.parsed(), which is expected to
        read that file back out of SCENES_DIR and apply it."""
        name = s.test_case.currentText()
        if not name:
            QMessageBox.warning(s, 'Sim View', f'No scene files found in:\n{SCENES_DIR}')
            return
        try:
            s.tracking_thread.parsed(name)
            s.on_status_changed(f"Loaded scene: {name}")
        except Exception as e:
            QMessageBox.warning(s, 'Sim View', f'Could not load scene "{name}": {e}')
            return
        s._play_load_scene_animation()

    def _play_load_scene_animation(s):
        """~2.5s progress-bar fill next to the Load scene button, purely visual
        feedback that a scene just loaded. The button is disabled for the duration
        so a second click can't stack another animation on top of this one."""
        s.load_scene_btn.setEnabled(False)
        s.load_progress.setValue(0); s.load_progress.show()
        anim = QPropertyAnimation(s.load_progress, b'value', s)
        anim.setDuration(2500); anim.setStartValue(0); anim.setEndValue(100)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def _finish():
            s.load_progress.hide(); s.load_scene_btn.setEnabled(True)

        anim.finished.connect(_finish)
        s._load_scene_anim = anim   # keep a reference — an unparented QPropertyAnimation
        anim.start()                # can get garbage-collected mid-animation otherwise

    def on_sat_view_changed(s, name):
        """Switching between 'Satellite Pov' and 'Satellite motion view' logs the choice
        and calls the matching TrackingThread method right away (this combo only lives on
        Sim View, so the user is necessarily on that tab when it fires)."""
        s.selected_sat_view = name
        s.on_status_changed(f"Unity view mode selected: {name}")
        s._invoke_sat_view(name)

    def _invoke_sat_view(s, name):
        """Calls backend.TrackingThread.sat_pov() for 'Satellite Pov', or .second_view()
        for 'Satellite motion view' (and as the fallback for any other value)."""
        tt = getattr(s, 'tracking_thread', None)
        if tt is None:
            return
        if name == 'Satellite Pov':
            tt.sat_pov()
        else:
            tt.second_view()

    # ============================================================
    # SCENE-PARAMETERS LAYOUT (Figma: Beacon Settings / Satellite Settings /
    # Disturbances / Camera Settings, 2x2 grid of panels).
    #
    # Every panel's rows live in ONE scene_grid() per panel (builders defined
    # near panel()/row(), under "Scene-Parameters builders") so labels and
    # controls line up down the whole panel instead of each row picking its own
    # spacing. To add/remove/rename a control, edit the grid_full(...)/
    # grid_half(...) calls below; each one also registers its widget in
    # s.scene_widgets so Save picks up new controls automatically. Camera
    # Settings has no controls yet per spec — its panel is just a placeholder.
    # ============================================================
    def build_scene_params(s):
        save_btn = btn('Save', False, s.save_scene_settings)
        s.scene_filename = QLineEdit(); s.scene_filename.setPlaceholderText('File name')
        s.scene_filename.setText('scene_settings1'); s.scene_filename.setFixedWidth(160)
        hd, _ = header('Scene parameters', 'Configure the simulated scene before running Sim View.',
                       s.scene_filename, save_btn)

        s.scene_widgets = {}   # {panel title: {control label: widget}} — read back by save_scene_settings()
        def reg(group, label, widget):
            s.scene_widgets.setdefault(group, {})[label] = widget
            return widget

        # ---- Beacon Settings: paired grid (label|control|label|control) so the
        # two half-width rows (Colour+Blink, Shape+Size) line up with each other
        # and with the two full-width rows (Start Position, Movement Type).
        G = 'Beacon Settings'
        bw, bg = scene_grid(paired=True)
        grid_full(bg, 0, 'Start Position', reg(G, 'Start Position',
            mk_combo(['Random', 'Center', 'Top-Left', 'Top-Right', 'Bottom-Left', 'Bottom-Right', 'Custom'])))
        grid_half(bg, 1, 0, 'Colour', reg(G, 'Colour', mk_combo(['Red', 'Green', 'Blue', 'White', 'Yellow', 'Orange'])))
        grid_half(bg, 1, 1, 'Blink', reg(G, 'Blink', mk_toggle(True)))
        grid_half(bg, 2, 0, 'Shape', reg(G, 'Shape', mk_combo(['Circle', 'Square', 'Triangle', 'Cross'])))
        grid_half(bg, 2, 1, 'Size', reg(G, 'Size', mk_combo(['2px', '4px', '6px', '8px', '10px', '12px'])))
        grid_full(bg, 3, 'Movement Type', reg(G, 'Movement Type', mk_combo(['Straight Horizontal', 'Straight Vertical', 'Figure 8', 'Circular', 'Mixed', 'Random'])))
        beacon_panel = panel_top('Beacon Settings', 'beacon', bw)

        # ---- Satellite Settings: single-column grid, every control fills the
        # full remaining row width.
        G = 'Satellite Settings'
        sw, sg = scene_grid()
        dist_row, dist_sl = mk_slider(0, 300, 100)
        grid_full(sg, 0, 'Distance from beacon', dist_row); reg(G, 'Distance from beacon', dist_sl)
        grid_full(sg, 1, 'No. Of Beacons', reg(G, 'No. Of Beacons', mk_combo(['1', '2', '3', '4', '5'])))
        grid_full(sg, 2, 'Extra Beacon Position', reg(G, 'Extra Beacon Position', mk_combo(['Random', 'Fixed'])))
        grid_full(sg, 3, 'Satellite Position', reg(G, 'Satellite Position', mk_combo(['Random', 'Fixed'])))
        grid_full(sg, 4, 'Satellite Rotation', reg(G, 'Satellite Rotation', mk_combo(['Random', 'Fixed'])))
        satellite_panel = panel_top('Satellite Settings', 'satellite', sw)

        # ---- Disturbances: single-column grid of slider rows, all the same
        # height, so they sit evenly spaced instead of one row stretching to
        # fill whatever height the panel ends up with.
        G = 'Disturbances'
        dw, dg = scene_grid()
        # Noise/Blur/Atmospheric Disturbance: raw slider steps 0-100 with divisor=100
        # display as 0.00-1.00 in 0.01 increments (one slider step = 0.01), matching
        # the same 0-100/divisor-100/default-0 pattern Sim View's own Scenario controls
        # sliders already use for these same three (see PARAMS near the top of this file).
        for i, (label, mn, mx, default_raw, dv) in enumerate((
            ('Noise Level', 0, 100, 0, 100), ('Blur Level', 0, 100, 0, 100), ('Atmospheric Disturbance', 0, 100, 0, 100),
            ('Max Standard Deviation (px)', 0, 20, 5, 1), ('Max Camera Jitter (px)', 0, 20, 3, 1), ('Platform Motion', 0, 10, 1, 1),
        )):
            row_w, sl = mk_slider(mn, mx, default_raw, divisor=dv)
            grid_full(dg, i, label, row_w); reg(G, label, sl)
        disturbances_panel = panel_top('Disturbances', 'disturbance', dw)

        # ---- Camera Settings (not decided yet — left empty per spec)
        cam_placeholder = QLabel('Not decided yet.'); cam_placeholder.setObjectName('mut')
        cam_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        camera_panel = panel_top('Camera Settings', 'camera', cam_placeholder)
        s.scene_widgets.setdefault('Camera Settings', {})   # empty group, still appears in the saved file

        w, l = page(hd, row(beacon_panel, satellite_panel), row(disturbances_panel, camera_panel), stretch=[0, 1, 1])
        return w

    def save_scene_settings(s):
        """Save button on the Scene-Parameters tab. Reads every control currently
        registered in s.scene_widgets (built in build_scene_params(), grouped by
        panel) and writes them to <file name field>.txt inside SCENES_DIR (see the
        constant near the top of this file), one 'Label: value' line per control
        under its panel's name. The file name comes from the text field beside
        Save (defaults to 'scene_settings1' if left blank); '.txt' is appended
        automatically if not typed. Overwrites the file on every click. Also
        refreshes the Sim View "Test case scene" dropdown so a newly saved scene
        shows up there immediately."""
        def value_of(w):
            if isinstance(w, QComboBox): return w.currentText()
            if isinstance(w, QSlider):
                dv = w.property('divisor') or 1
                return f"{w.value() / dv:g}"
            if isinstance(w, QPushButton) and w.isCheckable(): return 'ON' if w.isChecked() else 'OFF'
            return ''
        lines = []
        for group, fields in s.scene_widgets.items():
            lines.append(f"{group}:")
            if not fields:
                lines.append("  (not configured yet)")
            for label, widget in fields.items():
                lines.append(f"  {label}: {value_of(widget)}")
            lines.append("")
        name = s.scene_filename.text().strip() or 'scene_settings1'
        if not name.lower().endswith('.txt'): name += '.txt'
        path = os.path.join(SCENES_DIR, name)
        try:
            os.makedirs(SCENES_DIR, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines).rstrip() + '\n')
            s.refresh_scene_list()
            QMessageBox.information(s, 'Scene parameters', f'Saved to {path}')
        except Exception as e:
            QMessageBox.warning(s, 'Scene parameters', f'Could not save settings: {e}')

    # ---- Video View
    def build_video(s):
        hd, s.vsub = header('Video view', 'Import an MP4 to run beacon detection on your own footage.')
        v = s.video; s.vcam = CamView(v)
        # Real Unity view container (replaces the old painted SatView fake scene). This is
        # a plain native-window widget, exactly like s.unity_container on Sim View — the
        # real Unity HWND gets re-parented into whichever of the two is visible, via
        # _reparent_unity_to_tab(), so switching tabs moves the live embedded view with it.
        s.vsat = QWidget()
        s.vsat.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        s.vsat.setStyleSheet('background-color:#070c18; border-radius:9px;')
        s.vsat.setMinimumSize(230, 140)
        s.path = QLineEdit(); s.path.setReadOnly(True); s.path.setPlaceholderText('File location')
        top = QWidget(); tl = QHBoxLayout(top); tl.setContentsMargins(0, 0, 0, 0); tl.addWidget(btn('Import MP4', False, s.import_video)); tl.addWidget(s.path)
        s.vp = btn('Pause', False, s.toggle_video); s.vp.setEnabled(False); s.scrub = QSlider(Qt.Orientation.Horizontal); s.scrub.setRange(0, 1000)
        s.scrub.sliderMoved.connect(s.seek); s.tm = QLabel('0s'); s.spd = QComboBox(); s.spd.addItems(['0.25x', '0.5x', '1x', '2x', '4x']); s.spd.setCurrentIndex(2)
        s.spd.currentIndexChanged.connect(s.on_speed_changed)
        ctl = QWidget(); cl = QHBoxLayout(ctl); cl.setContentsMargins(0, 0, 0, 0)
        for x in (s.vp, s.scrub, s.tm, s.spd): cl.addWidget(x)
        src = QWidget(); sl = QVBoxLayout(src); sl.setContentsMargins(0, 0, 0, 0); sl.addWidget(top); sl.addWidget(QLabel('Video controls')); sl.addWidget(ctl)
        s.dt = table(['Time', 'X offset', 'Y offset', 'State'], 5); s.vchart = Chart(lambda: v.err, 150, auto=True)
        s.vview = QComboBox(); s.vview.addItems(['Python side view', 'Video View']); s.vview.currentIndexChanged.connect(s.on_vview_changed)
        w, l = page(hd, row(panel_with_header_control('Python-side overview', s.vview, s.vcam), panel('3D camera pan/tilt', s.vsat)),
                    row(panel('Source', src), panel('Latest detections', s.dt)), panel('Beacon offset from centre (px)', s.vchart), stretch=[0, 5, 3, 2]); return w

    def import_video(s):
        p, _ = QFileDialog.getOpenFileName(s, 'Import video', '', 'Video (*.mp4 *.avi *.mov *.mkv)')
        if not p: return
        probe = cv2.VideoCapture(p); ok = probe.isOpened(); probe.release()
        if not ok: return QMessageBox.warning(s, 'Import video', 'Could not open that video file.')
        s.stop_video()
        v = s.video; v.reset(); v.active = True; v.paused = False
        w = VideoWorker(p); w.speed = s.speed
        w.result.connect(s.on_video_result); w.status.connect(s.on_video_status)
        w.failed.connect(s.on_video_failed); w.ended.connect(s.on_video_ended)
        v.worker = w; w.start()
        s.path.setText(p); s.vsub.setText('Loading YOLO model...'); s.vp.setText('Pause'); s.vp.setEnabled(True); s.scrub.setValue(0)

    def stop_video(s):
        """Stop the video + detection thread and close the OpenCV preview window."""
        v = s.video; w = v.worker
        if w is not None:
            w.stop(); w.wait(); v.worker = None
        v.active = False

    def toggle_video(s):
        """Pause/resume Video View ONLY. Pause stops both the MP4 playback and the beacon
        detection; Play resumes both. Deliberately does not touch tracking_thread — that
        belongs to Sim View's own Pause button (toggle_sim), kept fully separate."""
        v = s.video
        if not v.active or v.worker is None: return
        v.paused = not v.paused
        if v.paused: v.worker.pause()
        else: v.worker.play()
        s.vp.setText('Play' if v.paused else 'Pause')

    def seek(s, val):
        # detection restarts (re-acquires) from the new position
        if s.video.worker is not None: s.video.worker.seek_to(val / 1000)

    def on_vview_changed(s, i):
        s.vcam.mode = 'raw' if i == 1 else 'py'; s.vcam.update()

    def on_speed_changed(s, i):
        s.speed = (.25, .5, 1, 2, 4)[i]
        # VideoWorker.run() paces frames with `next_t += 1 / (fps * s.speed)` (see near
        # the top of this file), so this actually changes how fast the video plays and
        # is detected — it is not just a label change in the UI.
        if s.video.worker is not None: s.video.worker.speed = s.speed

    def on_video_result(s, img, raw, info):
        v = s.video
        if s.sender() is not v.worker: return            # late frame from a replaced worker
        v.update(img, raw, info)
        # Feed the Video View's own pan/tilt (from BeaconTracker, independent of Sim View's
        # TrackingThread loop) into backend.TrackingThread for as long as this video plays.
        tt = getattr(s, 'tracking_thread', None)
        if tt is not None and hasattr(tt, 'placehold'):
            tt.placehold([float(info['pan']), float(info['tilt'])])
        if not s.scrub.isSliderDown():
            s.scrub.blockSignals(True); s.scrub.setValue(int(1000 * info['pos_frac'])); s.scrub.blockSignals(False)

    def on_video_status(s, text):
        if s.sender() is s.video.worker: s.vsub.setText(text)

    def on_video_failed(s, text):
        if s.sender() is not s.video.worker: return
        s.stop_video(); s.video.reset(); s.vp.setEnabled(False); s.vp.setText('Pause'); s.path.clear()
        s.vsub.setText('Import an MP4 to run beacon detection on your own footage.')
        QMessageBox.warning(s, 'Video detection', text)

    def on_video_ended(s, msg):
        if s.sender() is not s.video.worker: return
        s.video.paused = True; s.vp.setText('Play'); s.vsub.setText(f'Video finished. {msg}. Press Play to run it again.')
        print(msg)

    # ---- Benchmark
    def build_bench(s):
        hd, _ = header('Benchmark', 'Run a scenario suite and save the results to Data-Check')
        s.bname = QLineEdit('Run 2'); s.btype = QComboBox()
        s.btype.addItems(['Benchmark Performance-1 (scenario suite)', 'Benchmark Performance-2 (video-based)', 'Disturbance sweep', 'Custom'])
        det = QWidget(); dl = QGridLayout(det); dl.setContentsMargins(0, 0, 0, 0)
        dl.addWidget(QLabel('Name'), 0, 0); dl.addWidget(s.bname, 1, 0); dl.addWidget(QLabel('Benchmark type'), 0, 1); dl.addWidget(s.btype, 1, 1)
        spec = QLabel('Pass targets from the problem statement — Acquisition ≤ 2 s · Tracking error ≤ 10 px · '
                       'Target loss < 5% · Re-acquisition ≤ 1 s · Processing ≥ 20 FPS')
        spec.setObjectName('mut'); spec.setWordWrap(True)
        s.crit = [QCheckBox(c) for c in CR]; cw = QWidget(); cl = QVBoxLayout(cw); cl.setContentsMargins(0, 0, 0, 0)
        for c in s.crit: c.setChecked(True); cl.addWidget(c)
        s.go_b = btn('Run benchmark', False, s.run_bench); cl.addWidget(s.go_b); cl.addStretch()
        s.bar = QProgressBar(); s.bar.setRange(0, 20); s.bar.setFormat('%v/20'); s.blog = table(['Run', 'Scenario', 'Result'])
        s.blog.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0); rl.addWidget(panel('Progress', s.bar)); rl.addWidget(panel('Progress log', s.blog), 1)
        body = row(panel('Criteria', cw), right); body.layout().setStretch(1, 1); body.layout().itemAt(0).widget().setFixedWidth(270)
        w, l = page(hd, panel('Benchmark details', det, spec), body, stretch=[0, 0, 1]); return w

    def run_bench(s):
        if s.bt.isActive(): return
        s.bcols = [i for i, c in enumerate(s.crit) if c.isChecked()] or list(range(6)); s.bk, s.brows = 0, []
        s.blog.setRowCount(0); s.bar.setValue(0); s.go_b.setText('Running'); s.bt.start(280)

    def bench_step(s):
        sc = SC[s.bk % 10]; r = [sc[0]]
        for j, v in enumerate(sc[1:], 1):
            x = v * (1 + .06 * math.sin(s.bk * 12.9 + j * 3.1)); r.append(round(x, FM[j - 1]) if FM[j - 1] else int(round(x)))
        s.brows.append(tuple(r)); s.bk += 1; s.bar.setValue(s.bk); s.blog.insertRow(0)
        for c, t in enumerate((str(s.bk), r[0], f"{r[2]} s, {r[3]} px, {r[4]} lost")): s.blog.setItem(0, c, QTableWidgetItem(t))
        if s.bk == 20:
            s.bt.stop(); from datetime import datetime
            s.bench.insert(0, dict(name=s.bname.text() or 'Untitled', type=s.btype.currentText(), date=datetime.now().strftime('%d %b %Y, %H:%M'), cols=s.bcols, rows=s.brows))
            s.sel = 0; s.go_b.setText('Run benchmark'); s.bname.setText(f"Run {len(s.bench) + 1}"); s.draw_data()
            s.blog.insertRow(0); s.blog.setItem(0, 1, QTableWidgetItem('Saved to Data-Check.'))

    # ---- Data-Check
    def build_data(s):
        hd, _ = header('Data-Check', 'Saved benchmarks, spec compliance and trends across runs')
        s.bl = QListWidget(); s.bl.currentRowChanged.connect(lambda i: i >= 0 and (setattr(s, 'sel', i), s.draw_details()))
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0); ll.addWidget(btn('Add benchmark', False, lambda: s.go(3))); ll.addWidget(s.bl)
        s.dn = QLabel(); s.dn.setObjectName('h3'); s.dmeta = QLabel(); s.dmeta.setObjectName('mut'); s.kpi = QLabel(); s.kpi.setTextFormat(Qt.TextFormat.RichText)
        s.dtab = table(['Scenario'])
        vb = btn('View in Video tab', True, lambda: (s.go(2), s.vsub.setText(f"Reviewing benchmark: {s.bench[s.sel]['name']}. Import its MP4 to replay.")))
        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0); tr = QHBoxLayout(); tr.addWidget(s.dn); tr.addStretch(); tr.addWidget(vb)
        rl.addLayout(tr); rl.addWidget(s.dmeta); rl.addWidget(s.kpi); rl.addWidget(s.dtab, 1)
        # criterion picker + per-scenario bar chart (this benchmark) + trend chart (across all saved benchmarks)
        s.dcrit = QComboBox(); s.dcrit.addItems(CR); s.dcrit.setCurrentIndex(2)
        s.dcrit.currentIndexChanged.connect(lambda _: s.draw_details())
        s.dbar = BarChart(lambda: s._bar_data(), fmt='{:.1f}')
        s.dtrend = BarChart(lambda: s._trend_data(), fmt='{:.1f}')
        choose = QWidget(); chl = QHBoxLayout(choose); chl.setContentsMargins(0, 0, 0, 0)
        chl.addWidget(QLabel('Criterion')); chl.addWidget(s.dcrit); chl.addStretch()
        charts = row(panel('By scenario (this benchmark)', s.dbar), panel('By run (all saved benchmarks)', s.dtrend))
        body = row(panel('Benchmark list', left), panel('Details', right)); body.layout().setStretch(1, 1); body.layout().itemAt(0).widget().setFixedWidth(270)
        w, l = page(hd, body, panel('Compliance charts', choose, charts), stretch=[0, 3, 2]); return w

    def draw_data(s):
        s.bl.blockSignals(True); s.bl.clear()
        for b in s.bench: s.bl.addItem(QListWidgetItem(f"{b['name']}\n{b['type']}, {len(b['rows'])} runs"))
        s.bl.setCurrentRow(s.sel); s.bl.blockSignals(False); s.draw_details()

    def _bar_data(s):
        b = s.bench[s.sel]; j = s.dcrit.currentIndex()
        return [r[0] for r in b['rows']], [r[j + 1] for r in b['rows']]

    def _trend_data(s):
        j = s.dcrit.currentIndex()
        labels = [b['name'] for b in s.bench][::-1]
        values = [sum(r[j + 1] for r in b['rows']) / len(b['rows']) for b in s.bench][::-1]
        return labels, values

    def draw_details(s):
        b = s.bench[s.sel]; cols = b['cols']; s.dn.setText(b['name']); s.dmeta.setText(f"{b['type']}  ·  {b['date']}")
        avg = lambda j: sum(r[j + 1] for r in b['rows']) / len(b['rows'])
        def badge(j):
            th = SPEC_THRESH[j]
            if not th: return ''
            lim, lower = th; v = avg(j); ok = (v <= lim) if lower else (v >= lim)
            return f" <span style='background:{T['ok'] if ok else T['bc']};color:{T['onac']};border-radius:6px;padding:1px 6px;font-size:10px;font-weight:800'>{'PASS' if ok else 'FAIL'}</span>"
        s.kpi.setText(''.join(f"<span style='font-size:17px;font-weight:800'>{avg(j):.{FM[j] or 1}f}</span> "
                               f"<span style='color:{T['mut']}'>avg {CR[j]}</span>{badge(j)}&nbsp;&nbsp;&nbsp;&nbsp;" for j in cols))
        s.dtab.setColumnCount(len(cols) + 1); s.dtab.setHorizontalHeaderLabels(['Scenario'] + [CR[j] for j in cols]); s.dtab.setRowCount(len(b['rows']))
        for i, r in enumerate(b['rows']):
            s.dtab.setItem(i, 0, QTableWidgetItem(r[0]))
            for c, j in enumerate(cols):
                it = QTableWidgetItem(f"{r[j + 1]:.{FM[j]}f}"); th = SPEC_THRESH[j]
                if th:
                    lim, lower = th; ok = (r[j + 1] <= lim) if lower else (r[j + 1] >= lim)
                    it.setForeground(QColor(T['ok'] if ok else T['bc']))
                s.dtab.setItem(i, c + 1, it)
        if hasattr(s, 'dbar') and s.dcrit.currentIndex() not in cols: s.dcrit.setCurrentIndex(cols[0])
        if hasattr(s, 'dbar'): s.dbar.thresh = s.dtrend.thresh = SPEC_THRESH[s.dcrit.currentIndex()]; s.dbar.update(); s.dtrend.update()

    # ---- Spec Reference
    def build_spec(s):
        hd, _ = header('Spec reference', 'Background and parameters from the SIH problem statement (PS #26169)')
        brief = QLabel(
            "Free-space optical links use a highly directional laser beam, so pointing, acquisition and tracking "
            "(PAT) happens in two stages. <b>Coarse alignment</b> — what this console simulates — must observe the "
            "scene, acquire the remote beacon within the camera field of view, estimate its position, and keep "
            "adjusting pointing to hold it in view. Only once the beacon is reliably centred does fine pointing take "
            "over. Building this in software (instead of on real cameras and pan-tilt hardware) makes the tracking "
            "algorithms cheap to develop, test and demonstrate.")
        brief.setWordWrap(True); brief.setTextFormat(Qt.TextFormat.RichText)

        def spec_table(rows, headers=('Parameter', 'Suggested value', 'Remarks')):
            t = QTableWidget(len(rows), len(headers)); t.setHorizontalHeaderLabels(headers); t.verticalHeader().hide()
            t.setShowGrid(False); t.setFrameShape(QFrame.Shape.NoFrame); t.setAlternatingRowColors(True)
            t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
            t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); t.verticalHeader().setDefaultSectionSize(30)
            for r, vals in enumerate(rows):
                for c, val in enumerate(vals): t.setItem(r, c, QTableWidgetItem(str(val)))
            t.setMinimumHeight(30 * len(rows) + 34); return t

        perf = QWidget(); pg = QGridLayout(perf); pg.setContentsMargins(0, 0, 0, 0); pg.setHorizontalSpacing(18); pg.setVerticalSpacing(6)
        for i, (name, tgt) in enumerate(SPEC_PERF):
            n = QLabel(name); n.setObjectName('mut'); v = QLabel(tgt); v.setStyleSheet('font-weight:800;font-size:14px')
            pg.addWidget(n, i, 0); pg.addWidget(v, i, 1)
        weight = WeightBar(SPEC_EVAL)
        wl = QLabel('  ·  '.join(f"<b>{n}</b> {v}% — {d}" for n, v, _, d in SPEC_EVAL)); wl.setWordWrap(True); wl.setObjectName('mut')

        top = row(panel('Mission brief', brief), panel('Performance targets (pass/fail reference)', perf))
        mid = row(panel('Camera parameters', spec_table(SPEC_CAMERA)), panel('Target parameters', spec_table(SPEC_TARGET)),
                  panel('Camera motion constraints', spec_table(SPEC_MOTION)))
        noise = panel('Disturbances & noise the sliders on Sim View control', spec_table(SPEC_NOISE, ('Source', 'Spec')))
        evalp = panel('Evaluation weightage', weight, wl)
        w, l = page(hd, top, mid, noise, evalp, stretch=[0, 3, 3, 2, 2]); return w

    # ---- main loop
    def tick(s):
        m, v = s.sim, s.video
        if m.running:
            s.acc += s.speed
            while s.acc >= 1: m.step(); s.acc -= 1
        i = s.stack.currentIndex()
        if i not in (0, 2): return
        for w in (s.cam, s.sat, s.chart) if i == 0 else (s.vcam, s.vsat, s.vchart): w.update()
        if i == 0:
            if s.real_mode:
                # Live values come from backend.TrackingThread via on_stats_ready();
                # this just makes sure the panel repaints even between signal emissions.
                s.update_perf_labels()
            else:
                acq = m.acq_avg
                for lab, txt in zip(s.k, (f"{m.retention:.1f}%", f"{m.rmse:.1f} px", f"{acq:.2f} s" if acq is not None else '-', f"{m.loss_pct:.1f}%", f"{m.accuracy:.1f}%")): lab.setText(txt)
        else:
            s.tm.setText(f"{v.t:.0f}s")
            rows = v.rows
            s.dt.setRowCount(len(rows))
            for r, vals in enumerate(rows):
                for c, t in enumerate(vals): s.dt.setItem(r, c, QTableWidgetItem(t))
            s.update_video_rail()
        if not s.real_mode:
            if s._lk != m.lock:
                s._lk = m.lock; s.ls.setText('LOCKED' if m.lock else 'SEARCHING')
                s.ls.setStyleSheet(f"background:{T['ok'] if m.lock else T['bc']};color:{T['onac']};border-radius:10px;padding:10px;font-size:16px;font-weight:800")
            s.r['det'].setText('Detected' if m.det else 'Not found'); s.r['pan'].setText(f"{m.pan * .05:.2f}°"); s.r['tilt'].setText(f"{m.tilt * .05:.2f}°")
            s.r['off'].setText(f"{math.hypot(m.ox, m.oy):.1f} px"); s.r['time'].setText(f"{m.t:.1f} s")
            import time; n = time.perf_counter(); s.fps += (1 / max(n - s._last, 1e-3) - s.fps) * .05; s._last = n; s.r['fps'].setText(f"{s.fps:.0f} fps")
            s.evl.setText('\n'.join(m.events))

    # ============================================================
    # REAL TRACKING SIGNAL HANDLERS (Sim View, real_mode)
    # ============================================================

    def update_perf_labels(s):
        """Push the latest backend.TrackingThread metrics (in s.rt_stats) into the five
        'Tracking performance' labels on Sim View — the real-data replacement for the
        fake Sim.retention / Sim.rmse / Sim.acq_avg / Sim.loss_pct / Sim.accuracy values."""
        rs = s.rt_stats
        rmse = rs.get('rmse')
        acq = rs.get('acquisition_time')
        lk = rs.get('lock_retention') or 0.0
        losses = rs.get('target_losses', 0)
        acc = rs.get('accuracy') or 0.0
        vals = (
            f"{lk:.1f}%",
            f"{rmse:.1f} px" if rmse is not None else '-',
            f"{acq:.2f} s" if acq is not None else '-',
            str(losses),
            f"{acc:.1f}%",
        )
        for lab, txt in zip(s.k, vals): lab.setText(txt)

    def update_video_rail(s):
        """Fills the Video View side panel (s.vr labels) from the imported MP4's detector output."""
        v, i = s.video, s.video.info
        vals = dict.fromkeys(('state', 'det', 'off', 'pan', 'tilt', 'time', 'frame', 'mode', 'rmse', 'lock', 'acc', 'loss'), '-')
        vals['src'] = 'No video imported'
        if v.active:
            vals['src'] = s.path.text() or '-'
            vals['state'] = 'Paused' if v.paused else 'Playing'
            if i:
                bo = i['beacon_offset']
                vals.update(det='Detected' if v.det else 'Not found', off=f"{bo[0]:.1f}, {bo[1]:.1f}" if bo else '-',
                            pan=f"{i['pan']:.2f}°", tilt=f"{i['tilt']:.2f}°",
                            time=f"{v.t:.1f} s", frame=f"{i['frame_index']}/{i['total']}" if i['total'] else f"{i['frame_index']}",
                            mode=i['status'].title(), rmse=f"{i['rmse']:.1f} px", lock=f"{i['lock_retention']:.1f}%",
                            acc=f"{i['accuracy']:.1f}%", loss=str(i['target_loss_count']))
        for k, t in vals.items(): s.vr[k].setText(t)
        s.vr['speed'].setText(f"{s.speed:g}x")

    def on_frame_ready(s, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg).scaled(
            s.cam.width(), s.cam.height(),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        s.cam.setPixmap(pixmap)

    def on_status_changed(s, text):
        s.rt_events.insert(0, text)
        del s.rt_events[6:]
        s.evl.setText('\n'.join(s.rt_events))

        if 'connected' in text.lower():
            s.punity.setText('Connected')
        if 'tracking' in text.lower():
            s.ls.setText('LOCKED'); s.ls.setStyleSheet(f"background:{T['ok']};color:{T['onac']};border-radius:10px;padding:10px;font-size:16px;font-weight:800")
        elif 'acquiring' in text.lower():
            s.ls.setText('SEARCHING'); s.ls.setStyleSheet(f"background:{T['bc']};color:{T['onac']};border-radius:10px;padding:10px;font-size:16px;font-weight:800")

    def on_stats_ready(s, stats):
        fps = stats.get('fps', 0.0)
        yolo = stats.get('yolo')
        kalman = stats.get('kalman')
        elapsed = stats.get('elapsed', 0.0)
        pan = stats.get("pan")
        tilt = stats.get("tilt")
        offs_x = stats.get("offset_x")
        offs_y = stats.get("offset_y")
        losses_pct = stats.get('target_loss_pct', 0.0)


        s.r['fps'].setText(f"{fps:.1f} fps")
        s.r['time'].setText(f"{elapsed:.1f} s")
        s.r['det'].setText('Detected' if yolo is not None else 'Not found')
        s.r["pan"].setText(f"{pan:7.2f}")
        s.r['tilt'].setText(f"{tilt:7.2f}")
        s.r['off'].setText(f"{offs_x}, {offs_y}")

        s.pdet.setText(f"({yolo[0]:.0f}, {yolo[1]:.0f})" if yolo is not None else 'No detection')
        s.pkal.setText(f"({kalman[0]:.0f}, {kalman[1]:.0f})" if kalman is not None else 'Not initialized')

        # ---- Tracking performance panel (RMSE, lock retention, acquisition time,
        # target loss, accuracy) — sourced straight from backend.py's stats dict,
        # which computes them from the real YOLO detections + Kalman filter output.
        s.rt_stats['rmse'] = stats.get('rmse')
        s.rt_stats['lock_retention'] = stats.get('lock_retention', s.rt_stats['lock_retention'])
        s.rt_stats['acquisition_time'] = stats.get('acquisition_time')
        # s.rt_stats['target_losses'] = stats.get('target_losses', s.rt_stats['target_losses'])
        s.rt_stats['target_losses'] = f"{stats.get('target_loss_pct', 0.0):.1f}%"
        s.rt_stats['accuracy'] = stats.get('accuracy', s.rt_stats['accuracy'])

        # Per-frame Euclidean error (hypot(ox, oy)) feeds the chart's rolling window.
        # Only present once Kalman tracking has started (not during initial acquisition).
        err = stats.get('error')
        if err is not None:
            s.rt_err_history.append(err)

        s.update_perf_labels()

    # ============================================================
    # UNITY LAUNCH + EMBED (from App.py, unchanged win32 logic)
    # ============================================================

    def start_unity(s):
        if s.unity_proc is not None:
            return
        s.start_unity_btn.setEnabled(False)
        s.start_unity_btn.setText('Starting Unity...')
        s.punity.setText('Starting...')

        try:
            s.unity_proc = subprocess.Popen(
                [UNITY_EXE, "-popupwindow", "-screen-fullscreen", "0"]
            )
        except OSError as e:
            # e.g. FileNotFoundError when UNITY_EXE doesn't point to a real file —
            # fail loudly in the UI instead of raising out of a QTimer callback,
            # which would otherwise leave the button stuck disabled/mid-text.
            s.unity_proc = None
            s.start_unity_btn.setEnabled(True)
            s.start_unity_btn.setText('Start Unity')
            s.punity.setText('Not found')
            s.on_status_changed(f"Could not launch Unity: {e}")
            QMessageBox.warning(s, 'Start Unity',
                                 f"Could not launch Unity at:\n{UNITY_EXE}\n\n{e}")
            return

        QTimer.singleShot(800, s.find_and_embed_unity)

    def find_unity_hwnd_by_pid(s, pid):
        found = []

        def enum_handler(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
            if found_pid == pid:
                rect = win32gui.GetWindowRect(hwnd)
                w = rect[2] - rect[0]
                h = rect[3] - rect[1]
                if w > 50 and h > 50:
                    found.append(hwnd)

        win32gui.EnumWindows(enum_handler, None)
        return found[0] if found else 0

    def find_and_embed_unity(s):
        hwnd = s.find_unity_hwnd_by_pid(s.unity_proc.pid)

        if hwnd == 0:
            s._embed_attempts += 1
            if s._embed_attempts > 40:
                s.start_unity_btn.setText('Could not find Unity window')
                s.punity.setText('Not found')
                return
            QTimer.singleShot(500, s.find_and_embed_unity)
            return

        s.unity_hwnd = hwnd

        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        style &= ~(win32con.WS_POPUP | win32con.WS_CAPTION | win32con.WS_THICKFRAME |
                   win32con.WS_SYSMENU | win32con.WS_MINIMIZEBOX | win32con.WS_MAXIMIZEBOX)
        style |= win32con.WS_CHILD | win32con.WS_VISIBLE
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)

        # Unity always starts life embedded in whichever tab is currently on screen
        # (normally Sim View, since that's where the Start Unity button lives).
        s._unity_parent = s.unity_container if s.stack.currentIndex() == 0 else s.vsat
        win32gui.SetParent(hwnd, int(s._unity_parent.winId()))

        s.resize_unity_window()
        QTimer.singleShot(300, s.nudge_unity_render_loop)

        s.start_unity_btn.setText('Unity Running')
        s.punity.setText('Running (waiting for connection)')

    def _unity_container_size(s):
        """Native client-area size of the container, in the same physical-pixel
        units Win32 resize calls expect. Using Qt's width()/height() directly
        can under-size the embedded window on displays with scaling enabled
        (125%/150%/etc.), since Qt reports logical pixels while SetWindowPos/
        MoveWindow work in physical pixels — that mismatch is what causes the
        Unity window to sit small in the top-left corner instead of filling
        the panel."""
        parent = s._unity_parent or s.unity_container
        left, top, right, bottom = win32gui.GetClientRect(int(parent.winId()))
        return right - left, bottom - top

    def resize_unity_window(s):
        if not s.unity_hwnd:
            return
        w, h = s._unity_container_size()
        if w <= 0 or h <= 0:
            return
        win32gui.SetWindowPos(
            s.unity_hwnd, 0, 0, 0, w, h,
            win32con.SWP_FRAMECHANGED | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
        )
        win32gui.MoveWindow(s.unity_hwnd, 0, 0, w, h, True)

    def nudge_unity_render_loop(s):
        if not s.unity_hwnd:
            return
        w, h = s._unity_container_size()
        if w <= 0 or h <= 0:
            return
        win32gui.MoveWindow(s.unity_hwnd, 0, 0, max(w - 1, 1), h, True)
        win32gui.MoveWindow(s.unity_hwnd, 0, 0, w, h, True)
        win32gui.SendMessage(s.unity_hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
        win32gui.SendMessage(s.unity_hwnd, win32con.WM_SETFOCUS, 0, 0)
        try:
            win32gui.SetFocus(s.unity_hwnd)
        except Exception:
            pass

    def resizeEvent(s, event):
        super().resizeEvent(event)
        s.resize_unity_window()

    def closeEvent(s, event):
        s.stop_video()
        s.tracking_thread.stop()
        s.tracking_thread.wait(2000)
        if s.unity_proc:
            s.unity_proc.terminate()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv); app.setStyle('Fusion'); fnt = QFont(); fnt.setFamilies(['Inter', 'Segoe UI', 'SF Pro Text', 'Helvetica Neue', 'Arial']); fnt.setPointSize(10); app.setFont(fnt); win = Main(); win.resize(1400, 880); win.showMaximized(); sys.exit(app.exec())