"""Emotion tracker usando DeepFace"""

import time
import cv2
from deepface import DeepFace
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from threading import Thread, Event
import logging

logger = logging.getLogger(__name__)


class EmotionTracker:
    """Detecta emociones faciales usando DeepFace"""

    # 7 emociones básicas que DeepFace detecta
    EMOTIONS = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']

    def __init__(
        self,
        session_id: int,
        on_emotion_callback: Callable,
        sample_rate: float = 2.0,
        camera_id: int = 0,
        detector_backend: str = 'opencv',
        analyze_attributes: bool = True
    ):
        """
        Args:
            session_id: ID de la sesión actual
            on_emotion_callback: Callback llamado cuando se detecta emoción
            sample_rate: Frecuencia de análisis en Hz (2.0 = cada 0.5s)
            camera_id: ID de la cámara (0 = default)
            detector_backend: Backend de detección ('opencv', 'ssd', 'mtcnn', 'retinaface')
            analyze_attributes: Si analizar edad y género además de emociones
        """
        self.session_id = session_id
        self.on_emotion_callback = on_emotion_callback
        self.sample_rate = sample_rate
        self.frame_interval = 1.0 / sample_rate
        self.camera_id = camera_id
        self.detector_backend = detector_backend
        self.analyze_attributes = analyze_attributes

        self.cap: Optional[cv2.VideoCapture] = None
        self.running = False
        self.emotions_captured = 0

        # Thread y event
        self._thread: Optional[Thread] = None
        self._stop_event = Event()

        # Estado
        self.models_loaded = False
        self.last_detection_time = 0

    def start(self):
        """Iniciar detección de emociones"""
        print(f"😊 Emotion tracker starting...")
        print(f"   Sample rate: {self.sample_rate} Hz")
        print(f"   Detector: {self.detector_backend}")
        print(f"   Analyze attributes: {self.analyze_attributes}")

        # Inicializar cámara
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            raise RuntimeError("❌ No se pudo abrir la cámara")

        # Configurar cámara
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        print(f"   Cámara inicializada: {int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
              f"{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

        # Warm up DeepFace (descargar modelos en primera ejecución)
        print(f"   Cargando modelos de DeepFace (puede tomar un momento)...")
        try:
            ret, frame = self.cap.read()
            if ret:
                # Primer análisis para cargar modelos
                actions = ['emotion']
                if self.analyze_attributes:
                    actions.extend(['age', 'gender'])

                _ = DeepFace.analyze(
                    frame,
                    actions=actions,
                    detector_backend=self.detector_backend,
                    enforce_detection=False,
                    silent=True
                )
                self.models_loaded = True
                print(f"✓ Modelos cargados exitosamente")
        except Exception as e:
            print(f"⚠️  Advertencia durante warmup: {e}")

        self.running = True
        print(f"✓ Emotion tracker started")

        # Iniciar thread de captura
        self._thread = Thread(
            target=self._capture_loop,
            daemon=True,
            name="EmotionTracker"
        )
        self._thread.start()

    def _capture_loop(self):
        """Loop principal de captura de emociones"""
        while self.running and not self._stop_event.is_set():
            try:
                # Control de sample rate
                current_time = time.time()
                time_since_last = current_time - self.last_detection_time

                if time_since_last < self.frame_interval:
                    time.sleep(self.frame_interval - time_since_last)
                    continue

                # Capturar frame
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("No se pudo capturar frame de cámara")
                    time.sleep(0.5)
                    continue

                # Analizar emociones
                result = self._analyze_frame(frame)

                if result:
                    # Llamar callback con resultado
                    self.on_emotion_callback(result)
                    self.emotions_captured += 1

                    # Log cada 10 detecciones
                    if self.emotions_captured % 10 == 0:
                        print(f"  😊 {self.emotions_captured} emociones detectadas")

                self.last_detection_time = time.time()

            except Exception as e:
                logger.error(f"Error en capture loop: {e}")
                time.sleep(1.0)  # Backoff en caso de error

    def _analyze_frame(self, frame) -> Optional[Dict[str, Any]]:
        """Analizar un frame para detectar emociones"""
        try:
            timestamp = time.time()

            # Configurar acciones a analizar
            actions = ['emotion']
            if self.analyze_attributes:
                actions.extend(['age', 'gender'])

            # Analizar con DeepFace
            results = DeepFace.analyze(
                frame,
                actions=actions,
                detector_backend=self.detector_backend,
                enforce_detection=False,  # No fallar si no hay cara
                silent=True
            )

            # DeepFace puede retornar lista o dict
            if not results:
                return None

            result = results[0] if isinstance(results, list) else results

            # Extraer emociones
            emotions = result.get('emotion', {})
            if not emotions:
                return None

            # Normalizar valores a 0-1
            emotion_data = {
                'session_id': self.session_id,
                'timestamp': timestamp,
                'angry': emotions.get('angry', 0) / 100.0,
                'disgust': emotions.get('disgust', 0) / 100.0,
                'fear': emotions.get('fear', 0) / 100.0,
                'happy': emotions.get('happy', 0) / 100.0,
                'sad': emotions.get('sad', 0) / 100.0,
                'surprise': emotions.get('surprise', 0) / 100.0,
                'neutral': emotions.get('neutral', 0) / 100.0,
                'dominant_emotion': result.get('dominant_emotion', 'unknown')
            }

            # Añadir atributos opcionales
            if self.analyze_attributes:
                emotion_data['face_confidence'] = result.get('face_confidence', None)
                emotion_data['age'] = result.get('age', None)
                emotion_data['gender'] = result.get('dominant_gender',
                                                    result.get('gender', None))
            else:
                emotion_data['face_confidence'] = None
                emotion_data['age'] = None
                emotion_data['gender'] = None

            return emotion_data

        except Exception as e:
            logger.error(f"Error analizando frame: {e}")
            return None

    def stop(self, timeout: float = 5.0):
        """Detener detección de emociones"""
        self.running = False
        self._stop_event.set()

        # Esperar thread
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

        # Liberar cámara
        if self.cap:
            self.cap.release()
            self.cap = None

        print(f"✓ Emotion tracker stopped ({self.emotions_captured} emotions captured)")

    def get_stats(self):
        """Obtener estadísticas del tracker"""
        return {
            'emotions_captured': self.emotions_captured,
            'sample_rate': self.sample_rate,
            'detector_backend': self.detector_backend,
            'analyze_attributes': self.analyze_attributes,
            'running': self.running
        }


class EmotionTrackerAsync:
    """
    Wrapper async para EmotionTracker

    Proporciona interfaz consistente con otros trackers async
    """

    def __init__(
        self,
        session_id: int,
        on_emotion_callback: Callable,
        sample_rate: float = 2.0,
        camera_id: int = 0,
        detector_backend: str = 'opencv'
    ):
        self.tracker = EmotionTracker(
            session_id=session_id,
            on_emotion_callback=on_emotion_callback,
            sample_rate=sample_rate,
            camera_id=camera_id,
            detector_backend=detector_backend
        )

    def start(self):
        """Start emotion tracking"""
        self.tracker.start()

    def stop(self, timeout: float = 5.0):
        """Stop emotion tracking"""
        self.tracker.stop(timeout=timeout)

    def get_stats(self):
        """Get tracker stats"""
        return self.tracker.get_stats()


def test_emotion_detection():
    """Función de test para verificar que DeepFace funciona"""
    print("🧪 Test de Emotion Detection\n")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ No se pudo abrir la cámara")
        return

    print("📸 Capturando frame de prueba...")
    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("❌ No se pudo capturar frame")
        return

    print("🔍 Analizando con DeepFace...")
    try:
        result = DeepFace.analyze(
            frame,
            actions=['emotion', 'age', 'gender'],
            detector_backend='opencv',
            enforce_detection=False,
            silent=True
        )

        result = result[0] if isinstance(result, list) else result

        print("\n✅ Detección exitosa!\n")
        print("Emociones:")
        for emotion, value in result.get('emotion', {}).items():
            print(f"  {emotion}: {value:.1f}%")

        print(f"\nEmoción dominante: {result.get('dominant_emotion')}")
        print(f"Edad estimada: {result.get('age')}")
        print(f"Género: {result.get('dominant_gender', result.get('gender'))}")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    test_emotion_detection()
