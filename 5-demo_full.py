#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demo FULL v2.0: Mouse + Screenshots Inteligentes + Audio + Emotions

Sistema completo de HCI Logging con análisis de emociones

Uso:
    python demo_full.py [duración]

Ejemplo:
    python demo_full.py 120  # 2 minutos de tracking completo
"""

import sys
import time
import uuid
import signal
from pathlib import Path
from datetime import datetime
import mss
import json

# Fix para encoding en Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Añadir el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from hci_logger.storage.database import Database
from hci_logger.trackers.mouse_tracker import MouseTracker
from hci_logger.trackers.event_screenshot_tracker import EventBasedScreenshotTracker
from hci_logger.trackers.audio_tracker import AudioTrackerAsync
from hci_logger.trackers.emotion_tracker import EmotionTrackerAsync
from hci_logger.processing.heatmap import HeatmapGenerator
from hci_logger.processing.heatmap_overlay import HeatmapOverlayGenerator


def get_screen_dimensions():
    """Detecta las dimensiones completas del espacio de trabajo"""
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        width = monitor['width']
        height = monitor['height']
        left = monitor['left']
        top = monitor['top']

        print(f"📐 Dimensiones detectadas del espacio de trabajo:")
        print(f"   Resolución completa: {width}x{height}")
        print(f"   Origen: ({left}, {top})")

        return width, height, left, top


class FullHCIDemo:
    """Demo completo v2.0: Mouse + Screenshots Inteligentes + Audio + Emotions"""

    def __init__(self, duration: int = 120):
        self.duration = duration

        self.db = Database()
        self.session_id = None
        self.session_uuid = None
        self.screen_width = None
        self.screen_height = None

        # Trackers
        self.mouse_tracker = None
        self.screenshot_tracker = None
        self.audio_tracker = None
        self.emotion_tracker = None

        self.running = False

        # Buffer de eventos de mouse
        self.event_buffer = []
        self.buffer_size = 50

        # Manejo de señales
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Manejo de Ctrl+C"""
        print("\n\n⚠️  Deteniendo todos los trackers...")
        self.stop()
        sys.exit(0)

    def _on_mouse_event(self, event: dict):
        """Callback para eventos de mouse"""
        # 1. Guardar en buffer para DB
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

        # 2. Pasar al screenshot tracker para que decida si captura
        if self.screenshot_tracker:
            self.screenshot_tracker.on_mouse_event(event)

    def _on_screenshot_captured(self, screenshot_info: dict):
        """Callback para screenshots con metadata de eventos"""
        # Extraer metadata del evento trigger
        trigger_metadata = screenshot_info.pop('trigger_metadata', {})

        self.db.insert_screenshot(
            session_id=screenshot_info['session_id'],
            timestamp=screenshot_info['timestamp'],
            file_path=screenshot_info['file_path'],
            file_size=screenshot_info['file_size'],
            width=screenshot_info['width'],
            height=screenshot_info['height'],
            format=screenshot_info['format'],
            trigger_event_type=screenshot_info.get('trigger_event_type'),
            trigger_x=screenshot_info.get('trigger_x'),
            trigger_y=screenshot_info.get('trigger_y'),
            trigger_metadata=json.dumps(trigger_metadata) if trigger_metadata else None
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

    def _flush_mouse_buffer(self):
        """Escribir buffer de mouse a base de datos"""
        if self.event_buffer:
            self.db.insert_mouse_events_batch(self.event_buffer)
            self.event_buffer.clear()

    def start(self):
        """Iniciar tracking completo"""
        print("=" * 80)
        print("🚀 HCI LOGGER - DEMO FULL v2.0: SISTEMA COMPLETO HCI")
        print("=" * 80)
        print()
        print("  Componentes activos:")
        print("    🖱️  Mouse Tracking          - Movimientos, clicks, scroll")
        print("    📸 Screenshots Inteligentes - En clicks + scrolls (>100px)")
        print("    🎤 Audio Recording         - Segmentos de 60s (Think-Aloud)")
        print("    😊 Emotion Detection       - Análisis cada 2s (7 emociones + edad + género)")
        print()

        # Detectar dimensiones de pantalla
        screen_width, screen_height, _, _ = get_screen_dimensions()
        self.screen_width = screen_width
        self.screen_height = screen_height
        print()

        # Inicializar base de datos
        print("📊 Inicializando base de datos...")
        self.db.initialize()

        # Crear sesión
        self.session_uuid = str(uuid.uuid4())
        self.session_id = self.db.create_session(
            session_uuid=self.session_uuid,
            participant_id="demo_user",
            experiment_id="full_hci_demo_v2",
            target_url="test_application",
            screen_width=screen_width,
            screen_height=screen_height
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
        print("🚀 Iniciando todos los trackers...")
        print()

        # 1. Mouse Tracker
        self.mouse_tracker = MouseTracker(
            session_id=self.session_id,
            on_event_callback=self._on_mouse_event,
            movement_threshold=5
        )
        self.mouse_tracker.start()

        # 2. Event-Based Screenshot Tracker (Inteligente)
        self.screenshot_tracker = EventBasedScreenshotTracker(
            session_id=self.session_id,
            on_screenshot_callback=self._on_screenshot_captured,
            output_dir=screenshot_dir,
            scroll_threshold=100,  # Screenshot cuando scroll > 100px
            cooldown=0.5,          # Mínimo 0.5s entre screenshots
            format='png',
            quality=85
        )
        self.screenshot_tracker.start()

        # 3. Audio Tracker
        try:
            self.audio_tracker = AudioTrackerAsync(
                session_id=self.session_id,
                on_segment_callback=self._on_audio_segment,
                output_dir=audio_dir,
                segment_duration=60,  # Segmentos de 1 minuto
                sample_rate=44100,
                channels=1
            )
            self.audio_tracker.start()
        except Exception as e:
            print(f"⚠️  Audio tracker falló (continuando sin audio): {e}")
            self.audio_tracker = None

        # 4. Emotion Tracker
        try:
            self.emotion_tracker = EmotionTrackerAsync(
                session_id=self.session_id,
                on_emotion_callback=self._on_emotion_detected,
                sample_rate=2.0,  # 2 análisis por segundo
                camera_id=0,
                detector_backend='opencv'
            )
            self.emotion_tracker.start()
        except Exception as e:
            print(f"⚠️  Emotion tracker falló (continuando sin emociones): {e}")
            print(f"    Tip: Asegúrate de que la cámara esté disponible")
            self.emotion_tracker = None

        print()
        print(f"⏱️  Tracking iniciado por {self.duration} segundos...")
        print(f"   ¡Interactúa con el computador normalmente!")
        print(f"   Presiona Ctrl+C para detener antes")
        print()

        self.running = True

        # Contador de progreso
        start_time = time.time()
        last_update = start_time
        last_counts = {'screenshot': 0, 'audio': 0, 'emotion': 0}

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

                # Barra de progreso
                progress = elapsed / self.duration
                bar_length = 35
                filled = int(bar_length * progress)
                bar = "█" * filled + "░" * (bar_length - filled)

                # Indicadores de nuevo contenido
                indicators = ""
                if screenshot_count > last_counts['screenshot']:
                    indicators += " 📸"
                    last_counts['screenshot'] = screenshot_count
                if audio_count > last_counts['audio']:
                    indicators += " 🎤"
                    last_counts['audio'] = audio_count
                if emotion_count > last_counts['emotion'] and emotion_count % 5 == 0:
                    # Mostrar cada 5 emociones para no saturar
                    indicators += " 😊"
                    last_counts['emotion'] = emotion_count

                print(f"\r  [{bar}] {elapsed}/{self.duration}s | "
                      f"🖱️ {mouse_count} | 📸 {screenshot_count} | "
                      f"🎤 {audio_count} | 😊 {emotion_count}"
                      f"{indicators}",
                      end="", flush=True)

                last_update = time.time()

        print("\n")
        self.stop()

    def stop(self):
        """Detener todos los trackers y generar reportes"""
        self.running = False

        print()
        print("⏹️  Deteniendo todos los trackers...")

        # Detener trackers en orden
        if self.mouse_tracker:
            self.mouse_tracker.stop()

        if self.screenshot_tracker:
            self.screenshot_tracker.stop()

        if self.audio_tracker:
            self.audio_tracker.stop()

        if self.emotion_tracker:
            self.emotion_tracker.stop()

        # Flush buffer final
        self._flush_mouse_buffer()

        # Finalizar sesión
        if self.session_id:
            self.db.end_session(self.session_id)

        # Generar reporte completo
        self._generate_full_report()

        # Cerrar base de datos
        self.db.close()

    def _generate_full_report(self):
        """Generar reporte completo de TODOS los trackers"""
        print()
        print("=" * 80)
        print("📊 REPORTE COMPLETO DE LA SESIÓN HCI")
        print("=" * 80)

        # === MOUSE TRACKING ===
        total_events = self.db.get_event_count(self.session_id)
        events = self.db.get_mouse_events(self.session_id)

        move_count = sum(1 for e in events if e['event_type'] == 'move')
        click_count = sum(1 for e in events if e['event_type'] == 'click' and e['pressed'])
        scroll_count = sum(1 for e in events if e['event_type'] == 'scroll')

        print(f"\n🖱️  MOUSE TRACKING:")
        print(f"  Total de eventos: {total_events}")
        print(f"  - Movimientos: {move_count}")
        print(f"  - Clicks: {click_count}")
        print(f"  - Scrolls: {scroll_count}")

        # === SCREENSHOTS ===
        screenshots = self.db.get_screenshots(self.session_id)
        if screenshots:
            total_size = sum(s['file_size'] for s in screenshots)
            total_size_mb = total_size / (1024 * 1024)

            # Contar por tipo de trigger
            trigger_types = {}
            for s in screenshots:
                trigger = s.get('trigger_event_type', 'unknown')
                trigger_types[trigger] = trigger_types.get(trigger, 0) + 1

            print(f"\n📸 SCREENSHOTS (Basados en Eventos):")
            print(f"  Total capturados: {len(screenshots)}")
            print(f"  Por tipo de trigger:")
            for trigger, count in trigger_types.items():
                print(f"    - {trigger}: {count}")
            print(f"  Tamaño total: {total_size_mb:.2f} MB")
            print(f"  Directorio: data/sessions/{self.session_uuid}/screenshots/")

        # === AUDIO ===
        audio_segments = self.db.get_audio_segments(self.session_id)
        if audio_segments:
            total_duration = self.db.get_total_audio_duration(self.session_id)
            total_size = sum(s['file_size'] for s in audio_segments)
            total_size_mb = total_size / (1024 * 1024)

            print(f"\n🎤 AUDIO:")
            print(f"  Segmentos: {len(audio_segments)}")
            print(f"  Duración total: {total_duration:.1f}s ({total_duration/60:.1f} min)")
            print(f"  Tamaño total: {total_size_mb:.2f} MB")
            print(f"  Directorio: data/sessions/{self.session_uuid}/audio/")

        # === EMOTIONS ===
        emotions = self.db.get_emotion_events(self.session_id)
        if emotions:
            emotion_summary = self.db.get_dominant_emotions_summary(self.session_id)

            print(f"\n😊 EMOTION DETECTION:")
            print(f"  Total de análisis: {len(emotions)}")
            print(f"  Emociones detectadas:")

            # Ordenar por frecuencia
            sorted_emotions = sorted(
                emotion_summary.items(),
                key=lambda x: x[1],
                reverse=True
            )

            for emotion, count in sorted_emotions:
                percentage = (count / len(emotions)) * 100
                emoji = self._get_emotion_emoji(emotion)
                bar = "█" * int(percentage / 5)  # Barra visual
                print(f"    {emoji} {emotion:10} : {bar} {percentage:5.1f}% ({count})")

        # === HEATMAPS Y OVERLAYS ===
        print()
        if events:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)

            # 1. Heatmap general
            print("🎨 Generando heatmap general...")
            generator = HeatmapGenerator(
                screen_width=self.screen_width,
                screen_height=self.screen_height
            )

            heatmap_path = output_dir / f"heatmap_full_{timestamp}.png"
            generator.generate_from_events(
                events=events,
                output_path=heatmap_path,
                blur_radius=20
            )

            comparison_path = output_dir / f"comparison_full_{timestamp}.png"
            generator.generate_comparison(
                events=events,
                output_path=comparison_path
            )

            print(f"✓ Heatmap general: {heatmap_path.name}")
            print(f"✓ Comparación: {comparison_path.name}")

            # 2. Generar overlays sobre screenshots
            if screenshots:
                print()
                overlay_generator = HeatmapOverlayGenerator(
                    screen_width=self.screen_width,
                    screen_height=self.screen_height
                )

                overlay_dir = output_dir / f"overlays_full_{timestamp}"

                # Generar todos los overlays
                overlay_paths = overlay_generator.generate_all_overlays(
                    screenshots=screenshots,
                    all_events=events,
                    output_dir=overlay_dir,
                    time_window=5.0,
                    blur_radius=25,
                    alpha=0.6,
                    show_clicks=True,
                    click_radius=20
                )

                # Crear grilla de comparación
                if overlay_paths:
                    grid_path = output_dir / f"overlay_grid_full_{timestamp}.png"
                    overlay_generator.create_comparison_grid(
                        screenshots=screenshots,
                        overlay_paths=overlay_paths,
                        output_path=grid_path,
                        max_per_row=2
                    )

                    print(f"\n✓ Overlays generados en: {overlay_dir}/")
                    print(f"✓ Grilla de comparación: {grid_path.name}")

            print()
            print("=" * 80)
            print("📊 RESUMEN DE VISUALIZACIONES")
            print("=" * 80)
            print(f"\n1. Heatmaps Generales:")
            print(f"   - {heatmap_path}")
            print(f"   - {comparison_path}")

            if screenshots:
                print(f"\n2. Heatmap Overlays ({len(overlay_paths)} screenshots):")
                print(f"   - Carpeta: {overlay_dir}/")
                print(f"   - Grilla: {grid_path}")
                print(f"\n💡 Los overlays correlacionan contexto visual + actividad + emociones")

        # === RESUMEN FINAL ===
        print()
        print("=" * 80)
        print("✅ SESIÓN HCI COMPLETADA EXITOSAMENTE")
        print("=" * 80)
        print()
        print("📂 Todos los datos almacenados en:")
        print(f"  - Base de datos: data/hci_logger.db (con metadata completa)")
        print(f"  - Screenshots: data/sessions/{self.session_uuid}/screenshots/")
        print(f"  - Audio: data/sessions/{self.session_uuid}/audio/")
        print(f"  - Heatmaps y Overlays: output/")
        print()
        print("💡 Análisis Multimodal Disponible:")
        print("  - Correlacionar emociones con eventos de interacción")
        print("  - Reproducir audio sincronizado con screenshots")
        print("  - Identificar momentos de frustración (emociones + clics repetitivos)")
        print("  - Analizar patrones de comportamiento visual + emocional")
        print()
        print("🔍 Consulta la base de datos:")
        print(f"   sqlite3 data/hci_logger.db")
        print()

    def _get_emotion_emoji(self, emotion: str) -> str:
        """Obtener emoji para una emoción"""
        emoji_map = {
            'happy': '😊',
            'sad': '😢',
            'angry': '😠',
            'fear': '😨',
            'surprise': '😲',
            'disgust': '🤢',
            'neutral': '😐'
        }
        return emoji_map.get(emotion.lower(), '❓')


def main():
    """Punto de entrada"""
    # Duración desde argumentos
    duration = 120  # Default 2 minutos

    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"⚠️  Duración inválida: {sys.argv[1]}")
            print("   Usando duración por defecto: 120 segundos")

    print()
    print("⚠️  IMPORTANTE:")
    print("   - Asegúrate de tener permisos de cámara y micrófono")
    print("   - La primera ejecución descargará modelos de DeepFace (~100MB)")
    print("   - Interactúa naturalmente con el computador durante el tracking")
    print()

    input("Presiona ENTER para comenzar...")

    # Ejecutar demo
    demo = FullHCIDemo(duration=duration)
    demo.start()


if __name__ == "__main__":
    main()
