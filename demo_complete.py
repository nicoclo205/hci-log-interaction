#!/usr/bin/env python3
"""
Demo completo: Mouse + Screenshots + Audio

Uso:
    python demo_complete.py [duración] [screenshot_interval] [audio_segment_duration]

Ejemplo:
    python demo_complete.py 60 5 30  # 60s total, screenshot cada 5s, audio cada 30s
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
from hci_logger.processing.heatmap import HeatmapGenerator


class CompleteDemo:
    """Demo completo con todos los trackers implementados"""

    def __init__(
        self,
        duration: int = 60,
        screenshot_interval: int = 5,
        audio_segment_duration: int = 30
    ):
        self.duration = duration
        self.screenshot_interval = screenshot_interval
        self.audio_segment_duration = audio_segment_duration

        self.db = Database()
        self.session_id = None
        self.session_uuid = None

        # Trackers
        self.mouse_tracker = None
        self.screenshot_tracker = None
        self.audio_tracker = None

        self.running = False

        # Buffer de eventos de mouse
        self.event_buffer = []
        self.buffer_size = 50

        # Manejo de señales
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Manejo de Ctrl+C"""
        print("\n\n⚠️  Deteniendo tracking...")
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

    def _flush_mouse_buffer(self):
        """Escribir buffer de mouse a base de datos"""
        if self.event_buffer:
            self.db.insert_mouse_events_batch(self.event_buffer)
            self.event_buffer.clear()

    def start(self):
        """Iniciar tracking completo"""
        print("=" * 75)
        print("🖱️📸🎤 HCI LOGGER - DEMO COMPLETO")
        print("=" * 75)
        print()
        print("  Trackers activos:")
        print("    🖱️  Mouse Tracking")
        print("    📸 Screenshot Capture")
        print("    🎤 Audio Recording")
        print()

        # Inicializar base de datos
        print("📊 Inicializando base de datos...")
        self.db.initialize()

        # Crear sesión
        self.session_uuid = str(uuid.uuid4())
        self.session_id = self.db.create_session(
            session_uuid=self.session_uuid,
            participant_id="demo_user",
            experiment_id="complete_hci_demo",
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
        print("🚀 Iniciando trackers...")
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
            interval=self.screenshot_interval,
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
                segment_duration=self.audio_segment_duration,
                sample_rate=44100,
                channels=1
            )
            self.audio_tracker.start()
        except Exception as e:
            print(f"⚠️  Audio tracker falló (continuando sin audio): {e}")
            self.audio_tracker = None

        print()
        print(f"⏱️  Tracking iniciado por {self.duration} segundos...")
        print(f"   Presiona Ctrl+C para detener antes")
        print()

        self.running = True

        # Contador de progreso
        start_time = time.time()
        last_update = start_time
        last_screenshot_count = 0
        last_audio_count = 0

        while self.running and (time.time() - start_time) < self.duration:
            time.sleep(0.5)

            # Actualizar progreso cada segundo
            if time.time() - last_update >= 1.0:
                elapsed = int(time.time() - start_time)

                # Obtener contadores
                mouse_count = self.db.get_event_count(self.session_id)
                screenshot_count = self.db.get_screenshot_count(self.session_id)
                audio_count = self.db.get_audio_segment_count(self.session_id)

                # Barra de progreso
                progress = elapsed / self.duration
                bar_length = 40
                filled = int(bar_length * progress)
                bar = "█" * filled + "░" * (bar_length - filled)

                # Indicadores de nuevo contenido
                indicators = ""
                if screenshot_count > last_screenshot_count:
                    indicators += " 📸"
                    last_screenshot_count = screenshot_count
                if audio_count > last_audio_count:
                    indicators += " 🎤"
                    last_audio_count = audio_count

                print(f"\r  [{bar}] {elapsed}/{self.duration}s | "
                      f"Mouse: {mouse_count} | Screens: {screenshot_count} | "
                      f"Audio: {audio_count}{indicators}",
                      end="", flush=True)

                last_update = time.time()

        print("\n")
        self.stop()

    def stop(self):
        """Detener todos los trackers y generar reportes"""
        self.running = False

        print()
        print("⏹️  Deteniendo trackers...")

        # Detener trackers
        if self.mouse_tracker:
            self.mouse_tracker.stop()

        if self.screenshot_tracker:
            self.screenshot_tracker.stop()

        if self.audio_tracker:
            self.audio_tracker.stop()

        # Flush buffer final
        self._flush_mouse_buffer()

        # Finalizar sesión
        if self.session_id:
            self.db.end_session(self.session_id)

        # Generar reporte completo
        self._generate_report()

        # Cerrar base de datos
        self.db.close()

    def _generate_report(self):
        """Generar reporte completo de la sesión"""
        print()
        print("=" * 75)
        print("📊 REPORTE COMPLETO DE LA SESIÓN")
        print("=" * 75)

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
        screenshot_count = len(screenshots)

        if screenshot_count > 0:
            total_size = sum(s['file_size'] for s in screenshots)
            avg_size = total_size / screenshot_count
            total_size_mb = total_size / (1024 * 1024)

            print(f"\n📸 SCREENSHOTS:")
            print(f"  Total capturados: {screenshot_count}")
            print(f"  Tamaño total: {total_size_mb:.2f} MB")
            print(f"  Tamaño promedio: {avg_size / 1024:.2f} KB")
            print(f"  Directorio: data/sessions/{self.session_uuid}/screenshots/")

        # === AUDIO ===
        audio_segments = self.db.get_audio_segments(self.session_id)
        audio_count = len(audio_segments)

        if audio_count > 0:
            total_duration = self.db.get_total_audio_duration(self.session_id)
            total_size = sum(s['file_size'] for s in audio_segments)
            total_size_mb = total_size / (1024 * 1024)

            print(f"\n🎤 AUDIO:")
            print(f"  Total de segmentos: {audio_count}")
            print(f"  Duración total: {total_duration:.1f} segundos ({total_duration/60:.1f} min)")
            print(f"  Tamaño total: {total_size_mb:.2f} MB")
            print(f"  Sample rate: {audio_segments[0]['sample_rate']} Hz")
            print(f"  Directorio: data/sessions/{self.session_uuid}/audio/")

        # === HEATMAPS ===
        print()
        if events:
            print("🎨 Generando heatmaps...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)

            generator = HeatmapGenerator(screen_width=1920, screen_height=1080)

            # Heatmap general
            heatmap_path = output_dir / f"heatmap_full_{timestamp}.png"
            generator.generate_from_events(
                events=events,
                output_path=heatmap_path,
                blur_radius=20
            )

            # Comparación
            comparison_path = output_dir / f"comparison_full_{timestamp}.png"
            generator.generate_comparison(
                events=events,
                output_path=comparison_path
            )

            print()
            print("✓ Heatmaps generados en 'output/':")
            print(f"  - {heatmap_path.name}")
            print(f"  - {comparison_path.name}")

        # === RESUMEN FINAL ===
        print()
        print("=" * 75)
        print("✅ SESIÓN COMPLETADA EXITOSAMENTE")
        print("=" * 75)
        print()
        print("📂 Archivos generados:")
        print(f"  - Base de datos: data/hci_logger.db")
        print(f"  - Datos de sesión: data/sessions/{self.session_uuid}/")
        print(f"  - Heatmaps: output/")
        print()


def main():
    """Punto de entrada"""
    # Parámetros desde argumentos
    duration = 60
    screenshot_interval = 5
    audio_segment_duration = 30

    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"⚠️  Duración inválida: {sys.argv[1]}")

    if len(sys.argv) > 2:
        try:
            screenshot_interval = int(sys.argv[2])
        except ValueError:
            print(f"⚠️  Intervalo de screenshot inválido: {sys.argv[2]}")

    if len(sys.argv) > 3:
        try:
            audio_segment_duration = int(sys.argv[3])
        except ValueError:
            print(f"⚠️  Duración de segmento de audio inválida: {sys.argv[3]}")

    # Ejecutar demo
    demo = CompleteDemo(
        duration=duration,
        screenshot_interval=screenshot_interval,
        audio_segment_duration=audio_segment_duration
    )
    demo.start()


if __name__ == "__main__":
    main()
