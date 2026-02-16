"""Eye tracker usando MediaPipe Face Mesh"""

import time
import cv2
import numpy as np
import mediapipe as mp
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Tuple, List
from threading import Thread, Event
from sklearn.linear_model import Ridge
import logging

logger = logging.getLogger(__name__)


class EyeTracker:
    """Seguimiento ocular usando MediaPipe Face Mesh"""

    # Índices de landmarks de MediaPipe para ojos
    # https://github.com/google/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png
    LEFT_EYE_INDICES = [33, 133, 160, 159, 158, 157, 173, 144]
    RIGHT_EYE_INDICES = [362, 263, 387, 386, 385, 384, 398, 373]
    LEFT_IRIS_INDICES = [468, 469, 470, 471, 472]
    RIGHT_IRIS_INDICES = [473, 474, 475, 476, 477]

    def __init__(
        self,
        session_id: int,
        on_gaze_callback: Callable,
        sample_rate: float = 30.0,
        camera_id: int = 0,
        screen_width: int = 1920,
        screen_height: int = 1080,
        enable_calibration: bool = True
    ):
        """
        Args:
            session_id: ID de la sesión actual
            on_gaze_callback: Callback llamado cuando se detecta gaze
            sample_rate: Frecuencia de captura en Hz
            camera_id: ID de la cámara
            screen_width: Ancho de pantalla en pixels
            screen_height: Alto de pantalla en pixels
            enable_calibration: Si habilitar sistema de calibración
        """
        self.session_id = session_id
        self.on_gaze_callback = on_gaze_callback
        self.sample_rate = sample_rate
        self.frame_interval = 1.0 / sample_rate
        self.camera_id = camera_id
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.enable_calibration = enable_calibration

        # MediaPipe
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh: Optional[Any] = None
        self.cap: Optional[cv2.VideoCapture] = None

        # Estado
        self.running = False
        self.gazes_captured = 0
        self.is_calibrated = False

        # Calibración
        self.calibration_points: List[Tuple[int, int]] = []
        self.calibration_data: List[Dict[str, Any]] = []
        self.gaze_model_x: Optional[Ridge] = None
        self.gaze_model_y: Optional[Ridge] = None

        # Thread
        self._thread: Optional[Thread] = None
        self._stop_event = Event()
        self.last_capture_time = 0

    def start(self):
        """Iniciar eye tracking"""
        print(f"👁️  Eye tracker starting...")
        print(f"   Sample rate: {self.sample_rate} Hz")
        print(f"   Screen: {self.screen_width}x{self.screen_height}")
        print(f"   Calibration: {'enabled' if self.enable_calibration else 'disabled'}")

        # Inicializar cámara
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            raise RuntimeError("❌ No se pudo abrir la cámara")

        # Configurar cámara
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        # Inicializar MediaPipe Face Mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,  # Incluye iris landmarks
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        print(f"✓ Eye tracker started")

        if self.enable_calibration:
            print(f"   ⚠️  Calibración requerida para mejor precisión")
            print(f"   Usa calibrate() antes de tracking")

        self.running = True

        # Iniciar thread de captura
        self._thread = Thread(
            target=self._capture_loop,
            daemon=True,
            name="EyeTracker"
        )
        self._thread.start()

    def _capture_loop(self):
        """Loop principal de captura de gaze"""
        while self.running and not self._stop_event.is_set():
            try:
                # Control de sample rate
                current_time = time.time()
                time_since_last = current_time - self.last_capture_time

                if time_since_last < self.frame_interval:
                    time.sleep(self.frame_interval - time_since_last)
                    continue

                # Capturar y procesar frame
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("No se pudo capturar frame")
                    time.sleep(0.1)
                    continue

                # Procesar frame
                gaze_data = self._process_frame(frame)

                if gaze_data:
                    # Llamar callback
                    self.on_gaze_callback(gaze_data)
                    self.gazes_captured += 1

                    # Log cada 100 gazes
                    if self.gazes_captured % 100 == 0:
                        print(f"  👁️  {self.gazes_captured} gaze points captured")

                self.last_capture_time = time.time()

            except Exception as e:
                logger.error(f"Error en capture loop: {e}")
                time.sleep(0.5)

    def _process_frame(self, frame) -> Optional[Dict[str, Any]]:
        """Procesar un frame para extraer gaze data"""
        try:
            timestamp = time.time()

            # Convertir a RGB (MediaPipe usa RGB)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame.shape[:2]

            # Procesar con MediaPipe
            results = self.face_mesh.process(rgb_frame)

            if not results.multi_face_landmarks:
                return None

            face_landmarks = results.multi_face_landmarks[0]

            # Extraer landmarks de iris (centro de pupila)
            left_iris = self._get_iris_center(face_landmarks, self.LEFT_IRIS_INDICES, w, h)
            right_iris = self._get_iris_center(face_landmarks, self.RIGHT_IRIS_INDICES, w, h)

            if left_iris is None or right_iris is None:
                return None

            # Calcular centro promedio (gaze point en coordenadas de cámara)
            iris_center_cam = (
                (left_iris[0] + right_iris[0]) / 2,
                (left_iris[1] + right_iris[1]) / 2
            )

            # Estimar gaze en coordenadas de pantalla
            if self.is_calibrated and self.gaze_model_x and self.gaze_model_y:
                # Usar modelo calibrado
                features = self._extract_gaze_features(face_landmarks, w, h)
                gaze_x = self.gaze_model_x.predict([features])[0]
                gaze_y = self.gaze_model_y.predict([features])[0]

                # Limitar a bounds de pantalla
                gaze_x = np.clip(gaze_x, 0, self.screen_width)
                gaze_y = np.clip(gaze_y, 0, self.screen_height)
            else:
                # Sin calibración: mapeo simple (menos preciso)
                gaze_x = iris_center_cam[0] * (self.screen_width / w)
                gaze_y = iris_center_cam[1] * (self.screen_height / h)

            # Calcular eye openness (ratio de aspecto de ojo)
            left_eye_open = self._calculate_eye_openness(
                face_landmarks, self.LEFT_EYE_INDICES, h
            )
            right_eye_open = self._calculate_eye_openness(
                face_landmarks, self.RIGHT_EYE_INDICES, h
            )

            # Calcular head pose (rotación de cabeza)
            head_pose = self._estimate_head_pose(face_landmarks)

            # Construir datos de gaze
            gaze_data = {
                'session_id': self.session_id,
                'timestamp': timestamp,
                'left_pupil_x': float(left_iris[0]),
                'left_pupil_y': float(left_iris[1]),
                'right_pupil_x': float(right_iris[0]),
                'right_pupil_y': float(right_iris[1]),
                'gaze_x': float(gaze_x),
                'gaze_y': float(gaze_y),
                'left_eye_open': bool(left_eye_open > 0.02),
                'right_eye_open': bool(right_eye_open > 0.02),
                'head_pose_x': float(head_pose[0]),
                'head_pose_y': float(head_pose[1]),
                'head_pose_z': float(head_pose[2]),
                'is_calibrated': self.is_calibrated
            }

            return gaze_data

        except Exception as e:
            logger.error(f"Error procesando frame: {e}")
            return None

    def _get_iris_center(self, landmarks, iris_indices: List[int], w: int, h: int) -> Optional[Tuple[float, float]]:
        """Obtener centro del iris"""
        try:
            iris_points = [
                (landmarks.landmark[i].x * w, landmarks.landmark[i].y * h)
                for i in iris_indices
            ]
            # Centro es el primer punto del iris
            return iris_points[0]
        except Exception as e:
            logger.error(f"Error obteniendo iris center: {e}")
            return None

    def _calculate_eye_openness(self, landmarks, eye_indices: List[int], h: int) -> float:
        """Calcular qué tan abierto está el ojo (Eye Aspect Ratio)"""
        try:
            # Puntos verticales del ojo
            top = (landmarks.landmark[eye_indices[1]].y + landmarks.landmark[eye_indices[2]].y) / 2
            bottom = (landmarks.landmark[eye_indices[5]].y + landmarks.landmark[eye_indices[6]].y) / 2

            # Puntos horizontales
            left = landmarks.landmark[eye_indices[0]].x
            right = landmarks.landmark[eye_indices[4]].x

            # Eye Aspect Ratio
            vertical = abs(top - bottom)
            horizontal = abs(right - left)

            if horizontal > 0:
                return vertical / horizontal
            return 0.0

        except Exception as e:
            logger.error(f"Error calculando eye openness: {e}")
            return 0.0

    def _estimate_head_pose(self, landmarks) -> Tuple[float, float, float]:
        """Estimar pose de cabeza (pitch, yaw, roll)"""
        try:
            # Usar punto de nariz como referencia
            nose_tip = landmarks.landmark[1]
            return (
                nose_tip.x - 0.5,  # Yaw (izq/der)
                nose_tip.y - 0.5,  # Pitch (arriba/abajo)
                nose_tip.z  # Roll (profundidad)
            )
        except:
            return (0.0, 0.0, 0.0)

    def _extract_gaze_features(self, landmarks, w: int, h: int) -> np.ndarray:
        """Extraer features para modelo de calibración"""
        try:
            # Características: posiciones de iris + landmarks clave
            left_iris = self._get_iris_center(landmarks, self.LEFT_IRIS_INDICES, w, h)
            right_iris = self._get_iris_center(landmarks, self.RIGHT_IRIS_INDICES, w, h)

            # Normalizar a [0, 1]
            features = [
                left_iris[0] / w,
                left_iris[1] / h,
                right_iris[0] / w,
                right_iris[1] / h,
                landmarks.landmark[1].x,  # Nariz
                landmarks.landmark[1].y,
                landmarks.landmark[1].z
            ]

            return np.array(features)

        except Exception as e:
            logger.error(f"Error extrayendo features: {e}")
            return np.zeros(7)

    def calibrate(self, calibration_points: List[Tuple[int, int]] = None, samples_per_point: int = 30):
        """
        Ejecutar calibración del eye tracker

        Args:
            calibration_points: Lista de puntos (x, y) de pantalla para calibrar
                               Si None, usa grid de 9 puntos
            samples_per_point: Número de muestras a capturar por punto
        """
        if calibration_points is None:
            # Grid 3x3 de puntos de calibración
            margin = 200
            calibration_points = [
                (margin, margin),  # Top-left
                (self.screen_width // 2, margin),  # Top-center
                (self.screen_width - margin, margin),  # Top-right
                (margin, self.screen_height // 2),  # Middle-left
                (self.screen_width // 2, self.screen_height // 2),  # Center
                (self.screen_width - margin, self.screen_height // 2),  # Middle-right
                (margin, self.screen_height - margin),  # Bottom-left
                (self.screen_width // 2, self.screen_height - margin),  # Bottom-center
                (self.screen_width - margin, self.screen_height - margin)  # Bottom-right
            ]

        print(f"\n📍 Iniciando calibración de eye tracking...")
        print(f"   Puntos de calibración: {len(calibration_points)}")
        print(f"   Muestras por punto: {samples_per_point}")
        print(f"\n   INSTRUCCIONES:")
        print(f"   - Mira fijamente cada punto cuando aparezca")
        print(f"   - Mantén la cabeza quieta")
        print(f"   - Parpadea normalmente")
        print()

        self.calibration_data = []

        for i, (target_x, target_y) in enumerate(calibration_points):
            print(f"   [{i+1}/{len(calibration_points)}] Mira el punto en ({target_x}, {target_y})...")

            # Simular mostrar punto (en app real, mostrarías un punto visual)
            # Por ahora, solo esperamos
            time.sleep(1.0)

            # Capturar muestras
            point_samples = []
            for _ in range(samples_per_point):
                ret, frame = self.cap.read()
                if not ret:
                    continue

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = frame.shape[:2]

                results = self.face_mesh.process(rgb_frame)
                if not results.multi_face_landmarks:
                    continue

                face_landmarks = results.multi_face_landmarks[0]
                features = self._extract_gaze_features(face_landmarks, w, h)

                point_samples.append({
                    'features': features,
                    'target_x': target_x,
                    'target_y': target_y
                })

                time.sleep(0.033)  # ~30 fps

            if point_samples:
                self.calibration_data.extend(point_samples)
                print(f"       ✓ {len(point_samples)} muestras capturadas")

        # Entrenar modelo de mapeo gaze
        if len(self.calibration_data) > 10:
            self._train_gaze_model()
            self.is_calibrated = True
            print(f"\n✅ Calibración completada exitosamente!")
            print(f"   Total de muestras: {len(self.calibration_data)}")
        else:
            print(f"\n⚠️  Calibración falló: muestras insuficientes")

    def _train_gaze_model(self):
        """Entrenar modelo de regresión para mapeo de gaze"""
        try:
            # Preparar datos
            X = np.array([sample['features'] for sample in self.calibration_data])
            y_x = np.array([sample['target_x'] for sample in self.calibration_data])
            y_y = np.array([sample['target_y'] for sample in self.calibration_data])

            # Entrenar modelos Ridge Regression (uno para X, otro para Y)
            self.gaze_model_x = Ridge(alpha=1.0)
            self.gaze_model_y = Ridge(alpha=1.0)

            self.gaze_model_x.fit(X, y_x)
            self.gaze_model_y.fit(X, y_y)

            # Calcular precisión (error medio)
            pred_x = self.gaze_model_x.predict(X)
            pred_y = self.gaze_model_y.predict(X)

            error_x = np.mean(np.abs(pred_x - y_x))
            error_y = np.mean(np.abs(pred_y - y_y))

            print(f"   Precisión de calibración:")
            print(f"     Error X: {error_x:.1f} pixels")
            print(f"     Error Y: {error_y:.1f} pixels")

        except Exception as e:
            logger.error(f"Error entrenando modelo de gaze: {e}")
            self.is_calibrated = False

    def stop(self, timeout: float = 5.0):
        """Detener eye tracking"""
        self.running = False
        self._stop_event.set()

        # Esperar thread
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

        # Liberar recursos
        if self.face_mesh:
            self.face_mesh.close()
            self.face_mesh = None

        if self.cap:
            self.cap.release()
            self.cap = None

        print(f"✓ Eye tracker stopped ({self.gazes_captured} gaze points captured)")

    def get_stats(self):
        """Obtener estadísticas del tracker"""
        return {
            'gazes_captured': self.gazes_captured,
            'sample_rate': self.sample_rate,
            'is_calibrated': self.is_calibrated,
            'screen_size': (self.screen_width, self.screen_height),
            'running': self.running
        }


class EyeTrackerAsync:
    """Wrapper async para EyeTracker"""

    def __init__(
        self,
        session_id: int,
        on_gaze_callback: Callable,
        sample_rate: float = 30.0,
        camera_id: int = 0,
        screen_width: int = 1920,
        screen_height: int = 1080
    ):
        self.tracker = EyeTracker(
            session_id=session_id,
            on_gaze_callback=on_gaze_callback,
            sample_rate=sample_rate,
            camera_id=camera_id,
            screen_width=screen_width,
            screen_height=screen_height
        )

    def start(self):
        """Start eye tracking"""
        self.tracker.start()

    def calibrate(self, calibration_points: List[Tuple[int, int]] = None):
        """Run calibration"""
        self.tracker.calibrate(calibration_points)

    def stop(self, timeout: float = 5.0):
        """Stop eye tracking"""
        self.tracker.stop(timeout=timeout)

    def get_stats(self):
        """Get tracker stats"""
        return self.tracker.get_stats()


if __name__ == "__main__":
    # Test rápido
    print("🧪 Test de Eye Tracking con MediaPipe\n")

    def callback(data):
        print(f"Gaze: ({data['gaze_x']:.0f}, {data['gaze_y']:.0f})")

    tracker = EyeTracker(
        session_id=1,
        on_gaze_callback=callback,
        sample_rate=10.0,
        enable_calibration=False
    )

    try:
        tracker.start()
        print("\nCapturando durante 5 segundos...")
        time.sleep(5)
    finally:
        tracker.stop()
