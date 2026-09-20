import socket
import struct
import threading
import time
import math
from collections import deque

import numpy as np
import cv2  # type: ignore
from ultralytics import YOLO  # type: ignore
from PyQt6.QtCore import QThread, pyqtSignal


# ============================================================
# CONFIGURATION
# ============================================================

TRACK_HOST = "127.0.0.1"
TRACK_PORT = 5000

MODEL_PATH = "best.pt"
CONFIDENCE_THRESHOLD = 0.35

YOLO_INTERVAL = 3
INITIALIZATION_DETECTIONS = 20

ACQUISITION_ERROR_X = 40.0
ACQUISITION_ERROR_Y = 40.0

TRACK_CAMERA_FPS = 30.0

# Professor's RMSE definition:
# RMSE of hypot(ox, oy) over the last 300 frames
RMSE_WINDOW = 300

# Professor's lock definition
LOCK_ERROR_THRESHOLD = 60.0

# Accuracy definition
ACCURACY_THRESHOLD = 12.0

UNITY_EXE = r"c:\Users\Aditya Bose\Desktop\lets keep it here\first build\Test_run.exe"


# ============================================================
# KALMAN FILTER
# ============================================================

class BeaconKalmanFilter:

    def __init__(self):

        self.kalman = cv2.KalmanFilter(4, 2)

        self.kalman.measurementMatrix = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ], dtype=np.float32)

        self.kalman.measurementNoiseCov = np.array([
            [1.5, 0],
            [0, 1.5]
        ], dtype=np.float32)

        self.kalman.processNoiseCov = np.array([
            [1e-2, 0,    0,    0],
            [0,    1e-2, 0,    0],
            [0,    0,    1e-1, 0],
            [0,    0,    0,    1e-1]
        ], dtype=np.float32)

        self.initialized = False

    def predict(self, dt):

        self.kalman.transitionMatrix = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1,  0],
            [0, 0, 0,  1]
        ], dtype=np.float32)

        prediction = self.kalman.predict()

        return (
            float(prediction[0, 0]),
            float(prediction[1, 0])
        )

    def update(self, x, y):

        measurement = np.array([
            [np.float32(x)],
            [np.float32(y)]
        ])

        corrected = self.kalman.correct(measurement)

        return (
            float(corrected[0, 0]),
            float(corrected[1, 0])
        )

    def initialize(self, x, y, vx, vy):

        self.kalman.statePost = np.array([
            [np.float32(x)],
            [np.float32(y)],
            [np.float32(vx)],
            [np.float32(vy)]
        ], dtype=np.float32)

        self.kalman.statePre = self.kalman.statePost.copy()

        self.kalman.errorCovPost = np.eye(
            4,
            dtype=np.float32
        )

        self.initialized = True


# ============================================================
# REAL TRACKING THREAD
# ============================================================

class TrackingThread(QThread):

    frame_ready = pyqtSignal(np.ndarray)
    status_changed = pyqtSignal(str)
    stats_ready = pyqtSignal(dict)

    def __init__(self):

        super().__init__()

        self._running = True

        self.server = None
        self.conn = None

        # Latest pan/tilt received from Unity
        self.current_pan = 0.0
        self.current_tilt = 0.0

        self.pan_lock = threading.Lock()

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    def stop(self):

        self._running = False

        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass

        try:
            if self.server:
                self.server.close()
        except Exception:
            pass

    # --------------------------------------------------------
    # SEND COORDINATES TO UNITY
    # --------------------------------------------------------

    def send_coordinates(self, x, y):

        if self.conn is None:
            return

        message = f"{x},{y},{x},{y}\n"

        try:
            self.conn.sendall(
                message.encode()
            )
        except Exception as e:
            print("Coordinate send error:", e)

    # --------------------------------------------------------
    # RECEIVE DATA FROM UNITY
    #
    # Message type:
    #
    # 1 byte = 1 -> image
    # 1 byte = 2 -> pan/tilt
    #
    # IMAGE:
    #   [1][4-byte frame ID][4-byte image size][JPEG]
    #
    # PANTILT:
    #   [2][ASCII line]
    # --------------------------------------------------------

    def _receive_exactly(self, sock, size):

        data = b""

        while len(data) < size:

            chunk = sock.recv(
                size - len(data)
            )

            if not chunk:
                return None

            data += chunk

        return data

    def _receiver_loop(self, conn, shared):

        while self._running:

            try:

                # First byte tells us what kind of
                # message Unity sent.

                message_type = self._receive_exactly(
                    conn,
                    1
                )

                if message_type is None:
                    self._running = False
                    break

                message_type = message_type[0]

                # ------------------------------------------------
                # TYPE 1 = IMAGE FRAME
                # ------------------------------------------------

                if message_type == 1:

                    header = self._receive_exactly(
                        conn,
                        8
                    )

                    if header is None:
                        self._running = False
                        break

                    frame_id = struct.unpack(
                        "<I",
                        header[0:4]
                    )[0]

                    image_size = struct.unpack(
                        "<I",
                        header[4:8]
                    )[0]

                    jpeg_data = self._receive_exactly(
                        conn,
                        image_size
                    )

                    if jpeg_data is None:
                        self._running = False
                        break

                    with shared["lock"]:

                        shared["latest_frame"] = jpeg_data

                        shared["latest_frame_id"] = frame_id

                # ------------------------------------------------
                # TYPE 2 = PAN/TILT
                # ------------------------------------------------

                elif message_type == 2:

                    data = b""

                    while True:

                        chunk = conn.recv(1)

                        if not chunk:
                            self._running = False
                            break

                        if chunk == b"\n":
                            break

                        data += chunk

                    if not self._running:
                        break

                    message = data.decode(
                        "utf-8",
                        errors="ignore"
                    ).strip()

                    self._process_pan_tilt(
                        message
                    )

                else:

                    print(
                        "Unknown Unity message type:",
                        message_type
                    )

            except Exception as e:

                print(
                    "Receiver error:",
                    e
                )

                self._running = False
                break

    # --------------------------------------------------------
    # PROCESS PAN/TILT
    # --------------------------------------------------------

    def _process_pan_tilt(self, message):

        try:

            parts = message.split(",")

            if len(parts) != 3:
                return

            if parts[0] != "PANTILT":
                return

            pan = float(parts[1])
            tilt = float(parts[2])

            with self.pan_lock:

                self.current_pan = pan
                self.current_tilt = tilt

        except Exception as e:

            print(
                "Pan/tilt parsing error:",
                e
            )

    # --------------------------------------------------------
    # GET CURRENT PAN/TILT
    # --------------------------------------------------------

    def get_pan_tilt(self):

        with self.pan_lock:

            return (
                self.current_pan,
                self.current_tilt
            )

    # ========================================================
    # MAIN TRACKING LOOP
    # ========================================================

    def run(self):

        print("Loading YOLO model...")

        model = YOLO(
            MODEL_PATH
        )

        print("YOLO model loaded.")

        kalman_filter = BeaconKalmanFilter()

        shared = {
            "latest_frame": None,
            "latest_frame_id": None,
            "lock": threading.Lock()
        }

        # ----------------------------------------------------
        # METRIC VARIABLES
        # ----------------------------------------------------

        # RMSE history
        error_history = deque(
            maxlen=RMSE_WINDOW
        )

        # Error-over-time history
        error_over_time = []

        # Acquisition
        acquisition_start_time = None
        acquisition_time = None
        acquisition_complete = False

        # Lock retention
        frames_since_acquisition = 0
        locked_frames = 0

        # Target loss
        target_loss_count = 0
        target_currently_lost = False

        # Accuracy
        accuracy_total_frames = 0
        accuracy_within_12 = 0

        # ----------------------------------------------------
        # SERVER
        # ----------------------------------------------------

        self.server = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.server.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        self.server.bind(
            (
                TRACK_HOST,
                TRACK_PORT
            )
        )

        self.server.listen(1)

        self.status_changed.emit(
            f"Waiting for Unity on "
            f"{TRACK_HOST}:{TRACK_PORT}..."
        )

        print(
            f"Waiting for Unity on "
            f"{TRACK_HOST}:{TRACK_PORT}..."
        )

        try:

            self.conn, addr = self.server.accept()

        except OSError:

            return

        print(
            "Unity connected:",
            addr
        )

        self.status_changed.emit(
            "Unity connected — tracking active"
        )

        self.conn.setsockopt(
            socket.IPPROTO_TCP,
            socket.TCP_NODELAY,
            1
        )

        # ----------------------------------------------------
        # START RECEIVER THREAD
        # ----------------------------------------------------

        receiver = threading.Thread(
            target=self._receiver_loop,
            args=(
                self.conn,
                shared
            ),
            daemon=True
        )

        receiver.start()

        # ----------------------------------------------------
        # FRAME VARIABLES
        # ----------------------------------------------------

        frame_count = 0

        previous_frame_id = None

        last_processed_frame_id = None

        initialization_points = []

        initialization_times = []

        start_time = time.time()

        last_frame_time = time.perf_counter()

        fps = 0.0

        # ====================================================
        # MAIN LOOP
        # ====================================================

        try:

            while self._running:

                # --------------------------------------------
                # GET LATEST FRAME
                # --------------------------------------------

                with shared["lock"]:

                    jpeg_data = shared["latest_frame"]

                    current_frame_id = (
                        shared["latest_frame_id"]
                    )

                    shared["latest_frame"] = None

                    shared["latest_frame_id"] = None

                if jpeg_data is None:

                    time.sleep(0.001)

                    continue

                if current_frame_id == last_processed_frame_id:

                    continue

                last_processed_frame_id = current_frame_id

                # --------------------------------------------
                # DT
                # --------------------------------------------

                if previous_frame_id is None:

                    frame_delta = 1

                else:

                    frame_delta = (
                        current_frame_id
                        - previous_frame_id
                    )

                previous_frame_id = current_frame_id

                dt = (
                    frame_delta
                    / TRACK_CAMERA_FPS
                )

                if dt <= 0:

                    dt = (
                        1.0
                        / TRACK_CAMERA_FPS
                    )

                # --------------------------------------------
                # DECODE JPEG
                # --------------------------------------------

                image_array = np.frombuffer(
                    jpeg_data,
                    dtype=np.uint8
                )

                frame = cv2.imdecode(
                    image_array,
                    cv2.IMREAD_COLOR
                )

                if frame is None:

                    continue

                # --------------------------------------------
                # FPS
                # --------------------------------------------

                now = time.perf_counter()

                frame_interval = (
                    now
                    - last_frame_time
                )

                last_frame_time = now

                if frame_interval > 0:

                    instant_fps = (
                        1.0
                        / frame_interval
                    )

                    if fps == 0:

                        fps = instant_fps

                    else:

                        fps = (
                            fps * 0.9
                            + instant_fps * 0.1
                        )

                # --------------------------------------------
                # CAMERA CENTRE
                # --------------------------------------------

                height, width = frame.shape[:2]

                camera_center_x = (
                    width / 2.0
                )

                camera_center_y = (
                    height / 2.0
                )

                yolo_xy = None
                kalman_xy = None

                # =================================================
                # INITIAL ACQUISITION
                # =================================================

                if not kalman_filter.initialized:

                    results = model.predict(
                        frame,
                        conf=CONFIDENCE_THRESHOLD,
                        verbose=False
                    )

                    best_detection = None
                    best_confidence = 0.0

                    for result in results:

                        if result.boxes is None:
                            continue

                        for box in result.boxes:

                            cls = int(
                                box.cls[0]
                            )

                            confidence = float(
                                box.conf[0]
                            )

                            if (
                                cls == 0
                                and confidence
                                > best_confidence
                            ):

                                best_confidence = confidence

                                best_detection = box

                    if best_detection is not None:

                        x1, y1, x2, y2 = (
                            best_detection
                            .xyxy[0]
                            .cpu()
                            .numpy()
                        )

                        beacon_x = (
                            x1 + x2
                        ) / 2.0

                        beacon_y = (
                            y1 + y2
                        ) / 2.0

                        yolo_xy = (
                            beacon_x,
                            beacon_y
                        )

                        error_x = (
                            beacon_x
                            - camera_center_x
                        )

                        error_y = (
                            beacon_y
                            - camera_center_y
                        )

                        initialization_points.append(
                            (
                                beacon_x,
                                beacon_y
                            )
                        )

                        initialization_times.append(
                            current_frame_id
                            / TRACK_CAMERA_FPS
                        )

                        initialization_count = len(
                            initialization_points
                        )

                        # Send coordinates to Unity
                        self.send_coordinates(
                            beacon_x,
                            beacon_y
                        )

                        self.status_changed.emit(
                            f"ACQUIRING "
                            f"{initialization_count}/"
                            f"{INITIALIZATION_DETECTIONS} "
                            f"| conf "
                            f"{best_confidence:.2f}"
                        )

                        x1_i = int(x1)
                        y1_i = int(y1)
                        x2_i = int(x2)
                        y2_i = int(y2)

                        cv2.rectangle(
                            frame,
                            (x1_i, y1_i),
                            (x2_i, y2_i),
                            (0, 255, 0),
                            2
                        )

                        cv2.putText(
                            frame,
                            f"Beacon "
                            f"{best_confidence:.2f}",
                            (
                                x1_i,
                                max(
                                    20,
                                    y1_i - 10
                                )
                            ),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 255, 0),
                            2
                        )

                        cv2.circle(
                            frame,
                            (
                                int(beacon_x),
                                int(beacon_y)
                            ),
                            6,
                            (0, 255, 0),
                            -1
                        )

                        beacon_acquired = (

                            abs(error_x)
                            <= ACQUISITION_ERROR_X

                            and

                            abs(error_y)
                            <= ACQUISITION_ERROR_Y

                            and

                            initialization_count
                            >= INITIALIZATION_DETECTIONS
                        )

                        if beacon_acquired:

                            first_x, first_y = (
                                initialization_points[0]
                            )

                            last_x, last_y = (
                                initialization_points[-1]
                            )

                            first_time = (
                                initialization_times[0]
                            )

                            last_time = (
                                initialization_times[-1]
                            )

                            elapsed_time = (
                                last_time
                                - first_time
                            )

                            if elapsed_time > 0:

                                velocity_x = (
                                    last_x
                                    - first_x
                                ) / elapsed_time

                                velocity_y = (
                                    last_y
                                    - first_y
                                ) / elapsed_time

                            else:

                                velocity_x = 0.0
                                velocity_y = 0.0

                            kalman_filter.initialize(
                                last_x,
                                last_y,
                                velocity_x,
                                velocity_y
                            )

                            # Acquisition metric
                            acquisition_time = (
                                time.time()
                                - start_time
                            )

                            acquisition_start_time = (
                                time.time()
                            )

                            acquisition_complete = True

                            print(
                                "BEACON ACQUIRED — "
                                "switching to Kalman tracking"
                            )

                            print(
                                f"Acquisition time: "
                                f"{acquisition_time:.3f} s"
                            )

                            self.status_changed.emit(
                                "BEACON ACQUIRED — "
                                "tracking (Kalman)"
                            )

                    else:

                        self.status_changed.emit(
                            f"ACQUIRING "
                            f"{len(initialization_points)}/"
                            f"{INITIALIZATION_DETECTIONS} "
                            f"| no beacon detected"
                        )

                    cv2.putText(
                        frame,
                        f"ACQUIRING "
                        f"{len(initialization_points)}/"
                        f"{INITIALIZATION_DETECTIONS}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 255),
                        2
                    )

                    cv2.putText(
                        frame,
                        "YOLO -> CAMERA",
                        (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 255),
                        2
                    )

                    pan, tilt = self.get_pan_tilt()

                    self.stats_ready.emit({

                        "fps": fps,

                        "yolo": yolo_xy,

                        "kalman": None,

                        "elapsed":
                            time.time()
                            - start_time,

                        "pan": pan,

                        "tilt": tilt,

                        "acquisition_time":
                            acquisition_time,

                        "rmse": None,

                        "lock_retention": 0.0,

                        "target_losses":
                            target_loss_count,

                        "accuracy":
                            0.0
                    })

                    self.frame_ready.emit(
                        frame
                    )

                    frame_count += 1

                    continue

                # =================================================
                # KALMAN PREDICTION
                # =================================================

                predicted_x, predicted_y = (
                    kalman_filter.predict(dt)
                )

                run_yolo = (
                    current_frame_id
                    % YOLO_INTERVAL
                    == 0
                )

                detection_fired = False
                target_detected = False

                # =================================================
                # YOLO
                # =================================================

                if run_yolo:

                    detection_fired = True

                    results = model.predict(
                        frame,
                        conf=CONFIDENCE_THRESHOLD,
                        verbose=False
                    )

                    best_detection = None
                    best_confidence = 0.0

                    for result in results:

                        if result.boxes is None:
                            continue

                        for box in result.boxes:

                            cls = int(
                                box.cls[0]
                            )

                            confidence = float(
                                box.conf[0]
                            )

                            if (
                                cls == 0
                                and confidence
                                > best_confidence
                            ):

                                best_confidence = (
                                    confidence
                                )

                                best_detection = box

                    if best_detection is not None:

                        target_detected = True

                        x1, y1, x2, y2 = (
                            best_detection
                            .xyxy[0]
                            .cpu()
                            .numpy()
                        )

                        beacon_x = (
                            x1 + x2
                        ) / 2.0

                        beacon_y = (
                            y1 + y2
                        ) / 2.0

                        yolo_xy = (
                            beacon_x,
                            beacon_y
                        )

                        filtered_x, filtered_y = (
                            kalman_filter.update(
                                beacon_x,
                                beacon_y
                            )
                        )

                        self.send_coordinates(
                            filtered_x,
                            filtered_y
                        )

                        x1_i = int(x1)
                        y1_i = int(y1)
                        x2_i = int(x2)
                        y2_i = int(y2)

                        cv2.rectangle(
                            frame,
                            (x1_i, y1_i),
                            (x2_i, y2_i),
                            (0, 255, 0),
                            2
                        )

                        cv2.putText(
                            frame,
                            f"Beacon "
                            f"{best_confidence:.2f}",
                            (
                                x1_i,
                                max(
                                    20,
                                    y1_i - 10
                                )
                            ),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 255, 0),
                            2
                        )

                        self.status_changed.emit(
                            f"TRACKING | conf "
                            f"{best_confidence:.2f}"
                        )

                    else:

                        filtered_x = predicted_x
                        filtered_y = predicted_y

                        self.send_coordinates(
                            filtered_x,
                            filtered_y
                        )

                        self.status_changed.emit(
                            "TRACKING | YOLO missed, "
                            "using Kalman prediction"
                        )

                # =================================================
                # NO YOLO THIS FRAME
                # =================================================

                else:

                    filtered_x = predicted_x
                    filtered_y = predicted_y

                    self.send_coordinates(
                        filtered_x,
                        filtered_y
                    )

                # =================================================
                # CALCULATE ERROR
                #
                # ox / oy are based on the Kalman point that is
                # actually being sent to Unity.
                # =================================================

                ox = (
                    filtered_x
                    - camera_center_x
                )

                oy = (
                    filtered_y
                    - camera_center_y
                )

                # Euclidean centre error
                e = math.hypot(
                    ox,
                    oy
                )

                # =================================================
                # RMSE
                #
                # Professor definition:
                #
                # RMSE = RMS of hypot(ox, oy)
                # over last 300 frames.
                # =================================================

                error_history.append(e)

                if len(error_history) > 0:

                    rmse = math.sqrt(
                        sum(
                            value * value
                            for value in error_history
                        )
                        / len(error_history)
                    )

                else:

                    rmse = 0.0

                # =================================================
                # ERROR OVER TIME
                # =================================================

                elapsed = (
                    time.time()
                    - start_time
                )

                error_over_time.append(
                    (
                        elapsed,
                        ox,
                        oy,
                        e
                    )
                )

                # =================================================
                # ACQUISITION / LOCK METRICS
                # =================================================

                if acquisition_complete:

                    frames_since_acquisition += 1

                    # Professor's definition:
                    #
                    # lock = e < 60 AND detector fired
                    #
                    # For the real YOLO system, detector fired
                    # means a YOLO detection occurred on this
                    # frame.

                    lock_this_frame = (
                        e < LOCK_ERROR_THRESHOLD
                        and detection_fired
                        and target_detected
                    )

                    if lock_this_frame:

                        locked_frames += 1

                    # --------------------------------------------
                    # Target loss
                    # --------------------------------------------

                    if detection_fired:

                        if not target_detected:

                            if not target_currently_lost:

                                target_loss_count += 1

                            target_currently_lost = True

                        else:

                            target_currently_lost = False

                    # --------------------------------------------
                    # Lock retention
                    # --------------------------------------------

                    if frames_since_acquisition > 0:

                        lock_retention = (
                            locked_frames
                            / frames_since_acquisition
                        ) * 100.0

                    else:

                        lock_retention = 0.0

                else:

                    lock_retention = 0.0

                # =================================================
                # ACCURACY WITHIN 12 PIXELS
                # =================================================

                if e <= ACCURACY_THRESHOLD:

                    accuracy_within_12 += 1

                accuracy_total_frames += 1

                if accuracy_total_frames > 0:

                    accuracy = (
                        accuracy_within_12
                        / accuracy_total_frames
                    ) * 100.0

                else:

                    accuracy = 0.0

                # =================================================
                # PAN / TILT FROM UNITY
                # =================================================

                pan, tilt = self.get_pan_tilt()

                # =================================================
                # DRAW KALMAN
                # =================================================

                kalman_xy = (
                    filtered_x,
                    filtered_y
                )

                cv2.circle(
                    frame,
                    (
                        int(filtered_x),
                        int(filtered_y)
                    ),
                    3,
                    (0, 0, 255),
                    -1
                )

                cv2.putText(
                    frame,
                    "Kalman",
                    (
                        int(filtered_x) + 10,
                        int(filtered_y) + 10
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    1
                )

                cv2.putText(
                    frame,
                    "TRACKING",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2
                )

                # =================================================
                # STATS
                # =================================================

                self.stats_ready.emit({

                    "fps": fps,

                    "yolo": yolo_xy,

                    "kalman": kalman_xy,

                    "elapsed": elapsed,

                    "pan": pan,

                    "tilt": tilt,

                    "offset_x": f"{ox:7.2f}",

                    "offset_y": f"{oy:7.2f}",

                    "error": e,

                    "rmse": rmse,

                    "lock_retention":
                        lock_retention,

                    "acquisition_time":
                        acquisition_time,

                    "target_losses":
                        target_loss_count,

                    "target_loss_pct": (target_loss_count / frames_since_acquisition * 100) if frames_since_acquisition else 0.0,

                    "accuracy":
                        accuracy
                })

                # =================================================
                # CONSOLE METRICS
                # =================================================

                print(
                    f"\r"
                    f"Frame {current_frame_id} | "
                    f"Pan {pan:7.2f}° | "
                    f"Tilt {tilt:7.2f}° | "
                    f"Offset "
                    f"({ox:7.2f}, {oy:7.2f}) px | "
                    f"Error {e:6.2f} px | "
                    f"RMSE {rmse:6.2f} px | "
                    f"Lock {lock_retention:6.2f}% | "
                    f"Acc {accuracy:6.2f}% | "
                    f"Loss {target_loss_count}",
                    end="",
                    flush=True
                )

                self.frame_ready.emit(
                    frame
                )

                frame_count += 1

        finally:

            try:

                self.conn.close()

            except Exception:

                pass

            try:

                self.server.close()

            except Exception:

                pass

            print()
            print()
            print(
                "========== TRACKING RESULTS =========="
            )

            print(
                f"Acquisition time: "
                f"{acquisition_time:.3f} s"
                if acquisition_time is not None
                else
                "Acquisition time: N/A"
            )

            print(
                f"Lock retention: "
                f"{lock_retention:.2f}%"
            )

            print(
                f"Tracking RMSE: "
                f"{rmse:.2f} px"
            )

            print(
                f"Accuracy (within "
                f"{ACCURACY_THRESHOLD:.0f} px): "
                f"{accuracy:.2f}%"
            )

            print(
                f"Target losses: "
                f"{target_loss_count}"
            )

            pan, tilt = self.get_pan_tilt()

            print(
                f"Final Pan: "
                f"{pan:.2f}°"
            )

            print(
                f"Final Tilt: "
                f"{tilt:.2f}°"
            )

            print(
                "======================================="
            )

            print(
                "Tracking thread stopped."
            )

            self.status_changed.emit(
                "Stopped"
            )