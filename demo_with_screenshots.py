#!/usr/bin/env python3
"""
Demo de tracking completo: Mouse + Screenshots

Uso:
    python demo_with_screenshots.py [duración_en_segundos] [intervalo_screenshots]

Ejemplo:
    python demo_with_screenshots.py 30 5  # 30 segundos, screenshot cada 5s
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
from hci_logger.processing.heatmap import HeatmapGenerator


class CompleteTrackingDemo:
    """Demo completo con mouse tracking + screenshots"""

    def __init__(self, duration: int = 30, screenshot_interval: int = 5):
        self.duration = duration
        self.screenshot_interval = screenshot_interval

        self.db = Database()
        self.session_id = None
        self.session_uuid = None

        # Trackers
        self.mouse_tracker = None
        self.screenshot_tracker = None

        self.running = False

        # Buffer de eventos
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
        """Callback para screenshots capturados"""
        # Guardar en DB inmediatamente
        self.db.insert_screenshot(
            session_id=screenshot_info['session_id'],
            timestamp=screenshot_info['timestamp'],
            file_path=screenshot_info['file_path'],
            file_size=screenshot_info['file_size'],
            width=screenshot_info['width'],
            height=screenshot_info['height'],
            format=screenshot_info['format']
        )

    def _flush_mouse_buffer(self):
        """Escribir buffer de mouse a base de datos"""
        if self.event_buffer:
            self.db.insert_mouse_events_batch(self.event_buffer)
            self.event_buffer.clear()

    def start(self):
        """Iniciar tracking completo"""
        print("=" * 70)
        print("🖱️📸 HCI LOGGER - DEMO COMPLETO: MOUSE + SCREENSHOTS")
        print("=" * 70)
        print()

        # Inicializar base de datos
        print("📊 Inicializando base de datos...")
        self.db.initialize()

        # Crear sesión
        self.session_uuid = str(uuid.uuid4())
        self.session_id = self.db.create_session(
            session_uuid=self.session_uuid,
            participant_id="demo_user",
            experiment_id="complete_prototype_test",
            target_url="facebook.com",
            screen_width=1920,
            screen_height=1080
        )

        print(f"✓ Sesión creada: {self.session_uuid}")
        print(f"  ID: {self.session_id}")
        print()

        # Configurar directorio de screenshots
        screenshot_dir = Path("data/screenshots") / self.session_uuid
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        # Iniciar mouse tracker
        self.mouse_tracker = MouseTracker(
            session_id=self.session_id,
            on_event_callback=self._on_mouse_event,
            movement_threshold=5
        )
        self.mouse_tracker.start()

        # Iniciar screenshot tracker
        self.screenshot_tracker = ScreenshotTrackerAsync(
            session_id=self.session_id,
            on_screenshot_callback=self._on_screenshot_captured,
            output_dir=screenshot_dir,
            interval=self.screenshot_interval,
            format='png',
            quality=85
        )
        self.screenshot_tracker.start()

        print(f"⏱️  Tracking iniciado por {self.duration} segundos...")
        print(f"   🖱️  Mouse tracking activo")
        print(f"   📸 Screenshots cada {self.screenshot_interval}s")
        print(f"   Presiona Ctrl+C para detener antes")
        print()

        self.running = True

        # Contador de progreso
        start_time = time.time()
        last_update = start_time
        last_screenshot_count = 0

        while self.running and (time.time() - start_time) < self.duration:
            time.sleep(0.5)

            # Actualizar progreso cada segundo
            if time.time() - last_update >= 1.0:
                elapsed = int(time.time() - start_time)
                remaining = self.duration - elapsed

                # Obtener contadores
                mouse_count = self.db.get_event_count(self.session_id)
                screenshot_count = self.db.get_screenshot_count(self.session_id)

                # Barra de progreso
                progress = elapsed / self.duration
                bar_length = 40
                filled = int(bar_length * progress)
                bar = "█" * filled + "░" * (bar_length - filled)

                # Indicador de screenshot nuevo
                screenshot_indicator = ""
                if screenshot_count > last_screenshot_count:
                    screenshot_indicator = " 📸 ¡Screenshot!"
                    last_screenshot_count = screenshot_count

                print(f"\r  [{bar}] {elapsed}/{self.duration}s | "
                      f"Mouse: {mouse_count} | Screenshots: {screenshot_count}"
                      f"{screenshot_indicator}", end="", flush=True)

                last_update = time.time()

        print("\n")
        self.stop()

    def stop(self):
        """Detener tracking y generar reportes"""
        self.running = False

        # Detener trackers
        if self.mouse_tracker:
            self.mouse_tracker.stop()

        if self.screenshot_tracker:
            self.screenshot_tracker.stop()

        # Flush buffer final
        self._flush_mouse_buffer()

        # Finalizar sesión
        if self.session_id:
            self.db.end_session(self.session_id)

        # Estadísticas
        print()
        print("=" * 70)
        print("📈 ESTADÍSTICAS DE LA SESIÓN")
        print("=" * 70)

        # Mouse events
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

        # Screenshots
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
            print(f"  Directorio: data/screenshots/{self.session_uuid}/")

        # Generar heatmaps
        print()
        if events:
            print("🎨 Generando heatmaps...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)

            generator = HeatmapGenerator(screen_width=1920, screen_height=1080)

            # Heatmap general
            heatmap_path = output_dir / f"heatmap_complete_{timestamp}.png"
            generator.generate_from_events(
                events=events,
                output_path=heatmap_path,
                blur_radius=20
            )

            # Comparación
            comparison_path = output_dir / f"comparison_complete_{timestamp}.png"
            generator.generate_comparison(
                events=events,
                output_path=comparison_path
            )

            print()
            print("✓ Heatmaps generados en 'output/':")
            print(f"  - {heatmap_path.name}")
            print(f"  - {comparison_path.name}")

        print()
        print("=" * 70)
        print("✅ Demo completada exitosamente!")
        print("=" * 70)
        print()
        print("📂 Archivos generados:")
        print(f"  - Base de datos: data/hci_logger.db")
        print(f"  - Screenshots: data/screenshots/{self.session_uuid}/")
        print(f"  - Heatmaps: output/")
        print()

        # Cerrar base de datos
        self.db.close()


def main():
    """Punto de entrada"""
    # Duración y screenshot interval desde argumentos
    duration = 30
    screenshot_interval = 5

    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"⚠️  Duración inválida: {sys.argv[1]}")
            print("   Usando duración por defecto: 30 segundos")

    if len(sys.argv) > 2:
        try:
            screenshot_interval = int(sys.argv[2])
        except ValueError:
            print(f"⚠️  Intervalo inválido: {sys.argv[2]}")
            print("   Usando intervalo por defecto: 5 segundos")

    # Ejecutar demo
    demo = CompleteTrackingDemo(
        duration=duration,
        screenshot_interval=screenshot_interval
    )
    demo.start()


if __name__ == "__main__":
    main()
