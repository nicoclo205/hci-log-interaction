#!/usr/bin/env python3
"""
Demo ULTIMATE: TODOS LOS 5 TRACKERS HCI

🖱️  Mouse Tracking
📸 Screenshot Capture
🎤 Audio Recording
😊 Emotion Detection
👁️  Eye Tracking

¡Sistema HCI completo y funcional!

Uso:
    python demo_ultimate.py [duración]

Ejemplo:
    python demo_ultimate.py 180  # 3 minutos de tracking completo
"""

import sys
import time
import uuid
import signal
from pathlib import Path
from datetime import datetime

# Añadir el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from hci_logger.storage.database import Database
from hci_logger.trackers.mouse_tracker import MouseTracker
from hci_logger.trackers.screenshot_tracker import ScreenshotTrackerAsync
from hci_logger.trackers.audio_tracker import AudioTrackerAsync
from hci_logger.trackers.emotion_tracker import EmotionTrackerAsync
from hci_logger.trackers.eye_tracker import EyeTrackerAsync
from hci_logger.processing.heatmap import HeatmapGenerator


class UltimateHCIDemo:
    """Demo ULTIMATE con los 5 trackers HCI"""

    def __init__(self, duration: int = 180):
        self.duration = duration

        self.db = Database()
        self.session_id = None
        self.session_uuid = None

        # Trackers
        self.mouse_tracker = None
        self.screenshot_tracker = None
        self.audio_tracker = None
        self.emotion_tracker = None
        self.eye_tracker = None

        self.running = False

        # Buffer de eventos de mouse
        self.event_buffer = []
        self.buffer_size = 50

        # Manejo de señales
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Manejo de Ctrl+C"""
        print("\n\n⚠️  Deteniendo TODOS los trackers...")
        self.stop()
        sys.exit(0)

    def _on_mouse_event(self, event: dict):
        """Callback para eventos de mouse"""
        self.event_buffer.append((
            event['session_id'],
            event['timestamp'],
            event['event_type'],
            event['x'],
            event['y'],
            event['button'],
            event['pressed'],
            event['scroll_dx'],
            event['scroll_dy']
        ))

        if len(self.event_buffer) >= self.buffer_size:
            self._flush_mouse_buffer()

    def _on_screenshot_captured(self, screenshot_info: dict):
        """Callback para screenshots"""
        self.db.insert_screenshot(
            session_id=screenshot_info['session_id'],
            timestamp=screenshot_info['timestamp'],
            file_path=screenshot_info['file_path'],
            file_size=screenshot_info['file_size'],
            width=screenshot_info['width'],
            height=screenshot_info['height'],
            format=screenshot_info['format']
        )

    def _on_audio_segment(self, segment_info: dict):
        """Callback para segmentos de audio"""
        self.db.insert_audio_segment(
            session_id=segment_info['session_id'],
            start_timestamp=segment_info['start_timestamp'],
            end_timestamp=segment_info['end_timestamp'],
            duration=segment_info['duration'],
            file_path=segment_info['file_path'],
            sample_rate=segment_info['sample_rate'],
            channels=segment_info['channels'],
            file_size=segment_info['file_size']
        )

    def _on_emotion_detected(self, emotion_data: dict):
        """Callback para emociones detectadas"""
        self.db.insert_emotion_event(
            session_id=emotion_data['session_id'],
            timestamp=emotion_data['timestamp'],
            angry=emotion_data['angry'],
            disgust=emotion_data['disgust'],
            fear=emotion_data['fear'],
            happy=emotion_data['happy'],
            sad=emotion_data['sad'],
            surprise=emotion_data['surprise'],
            neutral=emotion_data['neutral'],
            dominant_emotion=emotion_data['dominant_emotion'],
            face_confidence=emotion_data.get('face_confidence'),
            age=emotion_data.get('age'),
            gender=emotion_data.get('gender')
        )

    def _on_gaze_detected(self, gaze_data: dict):
        """Callback para eye tracking"""
        self.db.insert_eye_event(
            session_id=gaze_data['session_id'],
            timestamp=gaze_data['timestamp'],
            left_pupil_x=gaze_data.get('left_pupil_x'),
            left_pupil_y=gaze_data.get('left_pupil_y'),
            right_pupil_x=gaze_data.get('right_pupil_x'),
            right_pupil_y=gaze_data.get('right_pupil_y'),
            gaze_x=gaze_data.get('gaze_x'),
            gaze_y=gaze_data.get('gaze_y'),
            left_eye_open=gaze_data.get('left_eye_open'),
            right_eye_open=gaze_data.get('right_eye_open'),
            head_pose_x=gaze_data.get('head_pose_x'),
            head_pose_y=gaze_data.get('head_pose_y'),
            head_pose_z=gaze_data.get('head_pose_z'),
            is_calibrated=gaze_data.get('is_calibrated', False)
        )

    def _flush_mouse_buffer(self):
        """Escribir buffer de mouse a base de datos"""
        if self.event_buffer:
            self.db.insert_mouse_events_batch(self.event_buffer)
            self.event_buffer.clear()

    def start(self):
        """Iniciar tracking ULTIMATE"""
        print("=" * 85)
        print("🚀 HCI LOGGER - DEMO ULTIMATE: ¡TODOS LOS 5 TRACKERS!")
        print("=" * 85)
        print()
        print("  Sistema HCI Completo:")
        print("    🖱️  Mouse Tracking       - Movimientos, clicks, scroll")
        print("    📸 Screenshot Capture   - Capturas cada 10s")
        print("    🎤 Audio Recording      - Segmentos de 60s")
        print("    😊 Emotion Detection    - Análisis cada 2s (7 emociones)")
        print("    👁️  Eye Tracking         - Gaze tracking @ 30 Hz")
        print()

        # Inicializar base de datos
        print("📊 Inicializando base de datos...")
        self.db.initialize()

        # Crear sesión
        self.session_uuid = str(uuid.uuid4())
        self.session_id = self.db.create_session(
            session_uuid=self.session_uuid,
            participant_id="demo_user",
            experiment_id="ultimate_hci_demo",
            target_url="facebook.com",
            screen_width=1920,
            screen_height=1080
        )

        print(f"✓ Sesión creada: {self.session_uuid}")
        print(f"  ID: {self.session_id}")
        print()

        # Configurar directorios
        session_data_dir = Path("data/sessions") / self.session_uuid
        screenshot_dir = session_data_dir / "screenshots"
        audio_dir = session_data_dir / "audio"

        screenshot_dir.mkdir(parents=True, exist_ok=True)
        audio_dir.mkdir(parents=True, exist_ok=True)

        # Iniciar trackers
        print("🚀 Iniciando TODOS los trackers...")
        print()

        # 1. Mouse Tracker
        self.mouse_tracker = MouseTracker(
            session_id=self.session_id,
            on_event_callback=self._on_mouse_event,
            movement_threshold=5
        )
        self.mouse_tracker.start()

        # 2. Screenshot Tracker
        self.screenshot_tracker = ScreenshotTrackerAsync(
            session_id=self.session_id,
            on_screenshot_callback=self._on_screenshot_captured,
            output_dir=screenshot_dir,
            interval=10,
            format='png'
        )
        self.screenshot_tracker.start()

        # 3. Audio Tracker
        try:
            self.audio_tracker = AudioTrackerAsync(
                session_id=self.session_id,
                on_segment_callback=self._on_audio_segment,
                output_dir=audio_dir,
                segment_duration=60,
                sample_rate=44100,
                channels=1
            )
            self.audio_tracker.start()
        except Exception as e:
            print(f"⚠️  Audio tracker falló: {e}")
            self.audio_tracker = None

        # 4. Emotion Tracker
        try:
            self.emotion_tracker = EmotionTrackerAsync(
                session_id=self.session_id,
                on_emotion_callback=self._on_emotion_detected,
                sample_rate=2.0,
                camera_id=0,
                detector_backend='opencv'
            )
            self.emotion_tracker.start()
        except Exception as e:
            print(f"⚠️  Emotion tracker falló: {e}")
            self.emotion_tracker = None

        # 5. Eye Tracker
        try:
            self.eye_tracker = EyeTrackerAsync(
                session_id=self.session_id,
                on_gaze_callback=self._on_gaze_detected,
                sample_rate=30.0,
                camera_id=0,
                screen_width=1920,
                screen_height=1080
            )
            self.eye_tracker.start()

            # Preguntar si hacer calibración
            print()
            print("👁️  Eye Tracker iniciado")
            do_calibration = input("   ¿Deseas calibrar el eye tracker? (s/n): ").lower().strip()
            if do_calibration == 's':
                print()
                self.eye_tracker.calibrate()
            else:
                print("   Continuando sin calibración (precisión reducida)")

        except Exception as e:
            print(f"⚠️  Eye tracker falló: {e}")
            self.eye_tracker = None

        print()
        print(f"⏱️  Tracking iniciado por {self.duration} segundos...")
        print(f"   ¡Interactúa normalmente con el computador!")
        print(f"   Presiona Ctrl+C para detener antes")
        print()

        self.running = True

        # Contador de progreso
        start_time = time.time()
        last_update = start_time
        last_counts = {
            'screenshot': 0,
            'audio': 0,
            'emotion': 0,
            'eye': 0
        }

        while self.running and (time.time() - start_time) < self.duration:
            time.sleep(0.5)

            # Actualizar progreso cada segundo
            if time.time() - last_update >= 1.0:
                elapsed = int(time.time() - start_time)

                # Obtener contadores
                mouse_count = self.db.get_event_count(self.session_id)
                screenshot_count = self.db.get_screenshot_count(self.session_id)
                audio_count = self.db.get_audio_segment_count(self.session_id)
                emotion_count = self.db.get_emotion_event_count(self.session_id)
                eye_count = self.db.get_eye_event_count(self.session_id)

                # Barra de progreso
                progress = elapsed / self.duration
                bar_length = 30
                filled = int(bar_length * progress)
                bar = "█" * filled + "░" * (bar_length - filled)

                # Indicadores
                indicators = ""
                if screenshot_count > last_counts['screenshot']:
                    indicators += " 📸"
                    last_counts['screenshot'] = screenshot_count
                if audio_count > last_counts['audio']:
                    indicators += " 🎤"
                    last_counts['audio'] = audio_count
                if emotion_count > last_counts['emotion'] and emotion_count % 5 == 0:
                    indicators += " 😊"
                    last_counts['emotion'] = emotion_count
                if eye_count > last_counts['eye'] and eye_count % 100 == 0:
                    indicators += " 👁️"
                    last_counts['eye'] = eye_count

                print(f"\r  [{bar}] {elapsed}/{self.duration}s | "
                      f"🖱️{mouse_count} 📸{screenshot_count} 🎤{audio_count} "
                      f"😊{emotion_count} 👁️{eye_count}"
                      f"{indicators}",
                      end="", flush=True)

                last_update = time.time()

        print("\n")
        self.stop()

    def stop(self):
        """Detener TODOS los trackers"""
        self.running = False

        print()
        print("⏹️  Deteniendo todos los trackers...")

        if self.mouse_tracker:
            self.mouse_tracker.stop()

        if self.screenshot_tracker:
            self.screenshot_tracker.stop()

        if self.audio_tracker:
            self.audio_tracker.stop()

        if self.emotion_tracker:
            self.emotion_tracker.stop()

        if self.eye_tracker:
            self.eye_tracker.stop()

        # Flush buffer final
        self._flush_mouse_buffer()

        # Finalizar sesión
        if self.session_id:
            self.db.end_session(self.session_id)

        # Generar reporte ULTIMATE
        self._generate_ultimate_report()

        # Cerrar base de datos
        self.db.close()

    def _generate_ultimate_report(self):
        """Generar reporte completo de TODOS los trackers"""
        print()
        print("=" * 85)
        print("📊 REPORTE ULTIMATE - TODOS LOS TRACKERS HCI")
        print("=" * 85)

        # Mouse
        events = self.db.get_mouse_events(self.session_id)
        move_count = sum(1 for e in events if e['event_type'] == 'move')
        click_count = sum(1 for e in events if e['event_type'] == 'click' and e['pressed'])
        scroll_count = sum(1 for e in events if e['event_type'] == 'scroll')

        print(f"\n🖱️  MOUSE TRACKING:")
        print(f"  Eventos: {len(events)} (Mov: {move_count}, Clicks: {click_count}, Scroll: {scroll_count})")

        # Screenshots
        screenshots = self.db.get_screenshots(self.session_id)
        if screenshots:
            total_size_mb = sum(s['file_size'] for s in screenshots) / (1024 * 1024)
            print(f"\n📸 SCREENSHOTS:")
            print(f"  Capturas: {len(screenshots)} ({total_size_mb:.2f} MB)")

        # Audio
        audio_segments = self.db.get_audio_segments(self.session_id)
        if audio_segments:
            total_duration = self.db.get_total_audio_duration(self.session_id)
            total_size_mb = sum(s['file_size'] for s in audio_segments) / (1024 * 1024)
            print(f"\n🎤 AUDIO:")
            print(f"  Segmentos: {len(audio_segments)} ({total_duration/60:.1f} min, {total_size_mb:.2f} MB)")

        # Emotions
        emotions = self.db.get_emotion_events(self.session_id)
        if emotions:
            emotion_summary = self.db.get_dominant_emotions_summary(self.session_id)
            print(f"\n😊 EMOTION DETECTION:")
            print(f"  Análisis: {len(emotions)}")

            sorted_emotions = sorted(emotion_summary.items(), key=lambda x: x[1], reverse=True)
            for emotion, count in sorted_emotions[:3]:
                percentage = (count / len(emotions)) * 100
                emoji = self._get_emotion_emoji(emotion)
                print(f"    {emoji} {emotion}: {percentage:.1f}%")

        # Eye Tracking
        eye_events = self.db.get_eye_events(self.session_id)
        if eye_events:
            calibrated_count = sum(1 for e in eye_events if e.get('is_calibrated'))
            print(f"\n👁️  EYE TRACKING:")
            print(f"  Gaze points: {len(eye_events)} ({calibrated_count} calibrados)")

        # Heatmaps
        print()
        if events:
            print("🎨 Generando heatmaps...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)

            generator = HeatmapGenerator(screen_width=1920, screen_height=1080)

            heatmap_path = output_dir / f"heatmap_ultimate_{timestamp}.png"
            generator.generate_from_events(events=events, output_path=heatmap_path, blur_radius=20)

            comparison_path = output_dir / f"comparison_ultimate_{timestamp}.png"
            generator.generate_comparison(events=events, output_path=comparison_path)

            print(f"✓ Heatmaps generados")

        # Resumen
        print()
        print("=" * 85)
        print("✅ SESIÓN HCI ULTIMATE COMPLETADA")
        print("=" * 85)
        print()
        print(f"📂 Datos almacenados:")
        print(f"  - Base de datos: data/hci_logger.db")
        print(f"  - Sesión: data/sessions/{self.session_uuid}/")
        print(f"  - Heatmaps: output/")
        print()

    def _get_emotion_emoji(self, emotion: str) -> str:
        """Obtener emoji para emoción"""
        emoji_map = {
            'happy': '😊', 'sad': '😢', 'angry': '😠',
            'fear': '😨', 'surprise': '😲', 'disgust': '🤢', 'neutral': '😐'
        }
        return emoji_map.get(emotion.lower(), '❓')


def main():
    """Punto de entrada"""
    duration = 180  # Default 3 minutos

    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"⚠️  Duración inválida, usando 180s")

    print()
    print("⚠️  DEMO ULTIMATE - REQUISITOS:")
    print("   - Cámara disponible (eye tracking + emotions)")
    print("   - Micrófono disponible (audio)")
    print("   - Primera ejecución descarga modelos (~100MB)")
    print("   - Se recomienda calibrar eye tracker para mejor precisión")
    print()

    input("Presiona ENTER para comenzar el demo ULTIMATE...")

    demo = UltimateHCIDemo(duration=duration)
    demo.start()


if __name__ == "__main__":
    main()
