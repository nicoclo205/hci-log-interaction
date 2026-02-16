#!/usr/bin/env python3
"""
Demo de tracking de mouse con generación de heatmap

Uso:
    python demo_tracking.py [duración_en_segundos]

Ejemplo:
    python demo_tracking.py 30  # Trackear durante 30 segundos
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
from hci_logger.processing.heatmap import HeatmapGenerator


class SimpleTrackingDemo:
    """Demo simple de tracking de mouse"""

    def __init__(self, duration: int = 30):
        self.duration = duration
        self.db = Database()
        self.session_id = None
        self.session_uuid = None
        self.tracker = None
        self.running = False

        # Buffer de eventos (para batch insert)
        self.event_buffer = []
        self.buffer_size = 50  # Flush cada 50 eventos

        # Manejo de señales
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Manejo de Ctrl+C"""
        print("\n\n⚠️  Deteniendo tracking...")
        self.stop()
        sys.exit(0)

    def _on_mouse_event(self, event: dict):
        """Callback para eventos de mouse"""
        # Añadir evento al buffer
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

        # Flush si alcanzamos el tamaño del buffer
        if len(self.event_buffer) >= self.buffer_size:
            self._flush_buffer()

    def _flush_buffer(self):
        """Escribir buffer a base de datos"""
        if self.event_buffer:
            self.db.insert_mouse_events_batch(self.event_buffer)
            self.event_buffer.clear()

    def start(self):
        """Iniciar tracking"""
        print("=" * 60)
        print("🖱️  HCI LOGGER - DEMO DE TRACKING DE MOUSE")
        print("=" * 60)
        print()

        # Inicializar base de datos
        print("📊 Inicializando base de datos...")
        self.db.initialize()

        # Crear sesión
        self.session_uuid = str(uuid.uuid4())
        self.session_id = self.db.create_session(
            session_uuid=self.session_uuid,
            participant_id="demo_user",
            experiment_id="prototype_test",
            target_url="facebook.com",
            screen_width=1920,
            screen_height=1080
        )

        print(f"✓ Sesión creada: {self.session_uuid}")
        print(f"  ID: {self.session_id}")
        print()

        # Iniciar tracker
        self.tracker = MouseTracker(
            session_id=self.session_id,
            on_event_callback=self._on_mouse_event,
            movement_threshold=5
        )
        self.tracker.start()

        print(f"⏱️  Tracking iniciado por {self.duration} segundos...")
        print(f"   Mueve el mouse y haz clicks!")
        print(f"   Presiona Ctrl+C para detener antes")
        print()

        self.running = True

        # Contador de progreso
        start_time = time.time()
        last_update = start_time

        while self.running and (time.time() - start_time) < self.duration:
            time.sleep(0.5)

            # Actualizar progreso cada segundo
            if time.time() - last_update >= 1.0:
                elapsed = int(time.time() - start_time)
                remaining = self.duration - elapsed
                event_count = self.db.get_event_count(self.session_id)

                # Barra de progreso
                progress = elapsed / self.duration
                bar_length = 40
                filled = int(bar_length * progress)
                bar = "█" * filled + "░" * (bar_length - filled)

                print(f"\r  [{bar}] {elapsed}/{self.duration}s | "
                      f"Eventos: {event_count}", end="", flush=True)

                last_update = time.time()

        print("\n")
        self.stop()

    def stop(self):
        """Detener tracking y generar heatmap"""
        self.running = False

        # Detener tracker
        if self.tracker:
            self.tracker.stop()

        # Flush buffer final
        self._flush_buffer()

        # Finalizar sesión
        if self.session_id:
            self.db.end_session(self.session_id)

        # Estadísticas
        print()
        print("=" * 60)
        print("📈 ESTADÍSTICAS DE LA SESIÓN")
        print("=" * 60)

        total_events = self.db.get_event_count(self.session_id)
        events = self.db.get_mouse_events(self.session_id)

        move_count = sum(1 for e in events if e['event_type'] == 'move')
        click_count = sum(1 for e in events if e['event_type'] == 'click' and e['pressed'])
        scroll_count = sum(1 for e in events if e['event_type'] == 'scroll')

        print(f"  Total de eventos: {total_events}")
        print(f"  - Movimientos: {move_count}")
        print(f"  - Clicks: {click_count}")
        print(f"  - Scrolls: {scroll_count}")
        print()

        # Generar heatmaps
        if events:
            print("🎨 Generando heatmaps...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)

            generator = HeatmapGenerator(screen_width=1920, screen_height=1080)

            # Heatmap general
            heatmap_path = output_dir / f"heatmap_{timestamp}.png"
            generator.generate_from_events(
                events=events,
                output_path=heatmap_path,
                blur_radius=20
            )

            # Heatmap solo de clicks
            click_heatmap_path = output_dir / f"heatmap_clicks_{timestamp}.png"
            generator.generate_click_heatmap(
                events=events,
                output_path=click_heatmap_path,
                blur_radius=30
            )

            # Comparación lado a lado
            comparison_path = output_dir / f"comparison_{timestamp}.png"
            generator.generate_comparison(
                events=events,
                output_path=comparison_path
            )

            print()
            print("✓ Heatmaps generados en el directorio 'output/':")
            print(f"  - {heatmap_path.name}")
            print(f"  - {click_heatmap_path.name}")
            print(f"  - {comparison_path.name}")
        else:
            print("⚠️  No hay eventos suficientes para generar heatmap")

        print()
        print("=" * 60)
        print("✅ Demo completada exitosamente!")
        print("=" * 60)

        # Cerrar base de datos
        self.db.close()


def main():
    """Punto de entrada"""
    # Duración desde argumentos o default 30 segundos
    duration = 30
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"⚠️  Duración inválida: {sys.argv[1]}")
            print("   Usando duración por defecto: 30 segundos")

    # Ejecutar demo
    demo = SimpleTrackingDemo(duration=duration)
    demo.start()


if __name__ == "__main__":
    main()
