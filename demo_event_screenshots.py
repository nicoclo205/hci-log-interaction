#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demo de tracking con Screenshots Inteligentes basados en eventos

Este demo captura screenshots SOLO cuando:
- El usuario hace click
- El usuario hace scroll significativo (>100px acumulado)

Uso:
    python demo_event_screenshots.py [duración_en_segundos]

Ejemplo:
    python demo_event_screenshots.py 60  # 60 segundos de tracking
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
        print(f"   Monitores individuales:")

        for i, m in enumerate(sct.monitors[1:], 1):
            print(f"     Monitor {i}: {m['width']}x{m['height']} en ({m['left']}, {m['top']})")

        return width, height, left, top


class EventScreenshotDemo:
    """Demo de tracking con screenshots basados en eventos"""

    def __init__(self, duration: int = 60):
        self.duration = duration
        self.db = Database()
        self.session_id = None
        self.session_uuid = None
        self.screen_width = None
        self.screen_height = None

        # Trackers
        self.mouse_tracker = None
        self.screenshot_tracker = None

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
        # 1. Guardar evento en buffer para la DB
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

        # 2. Pasar evento al screenshot tracker para que decida si captura
        if self.screenshot_tracker:
            self.screenshot_tracker.on_mouse_event(event)

    def _on_screenshot_captured(self, screenshot_info: dict):
        """Callback para screenshots capturados"""
        # Extraer metadata del evento trigger
        trigger_metadata = screenshot_info.pop('trigger_metadata', {})

        # Guardar en DB
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

    def _flush_mouse_buffer(self):
        """Escribir buffer de mouse a base de datos"""
        if self.event_buffer:
            self.db.insert_mouse_events_batch(self.event_buffer)
            self.event_buffer.clear()

    def start(self):
        """Iniciar tracking"""
        print("=" * 70)
        print("🖱️📸 HCI LOGGER - SCREENSHOTS INTELIGENTES (Basados en Eventos)")
        print("=" * 70)
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
            experiment_id="event_screenshot_test",
            target_url="test_page",
            screen_width=screen_width,
            screen_height=screen_height
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

        # Iniciar screenshot tracker basado en eventos
        self.screenshot_tracker = EventBasedScreenshotTracker(
            session_id=self.session_id,
            on_screenshot_callback=self._on_screenshot_captured,
            output_dir=screenshot_dir,
            scroll_threshold=100,  # 100px de scroll acumulado
            cooldown=0.5,          # Mínimo 0.5s entre screenshots
            format='png',
            quality=85
        )
        self.screenshot_tracker.start()

        print()
        print(f"⏱️  Tracking iniciado por {self.duration} segundos...")
        print(f"   🖱️  Mouse tracking activo")
        print(f"   📸 Screenshots en clicks y scrolls (>100px)")
        print(f"   💡 Haz clicks y scrolls para ver screenshots capturados!")
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

                # Obtener contadores
                mouse_count = self.db.get_event_count(self.session_id)
                screenshot_count = self.db.get_screenshot_count(self.session_id)

                # Barra de progreso
                progress = elapsed / self.duration
                bar_length = 40
                filled = int(bar_length * progress)
                bar = "█" * filled + "░" * (bar_length - filled)

                print(f"\r  [{bar}] {elapsed}/{self.duration}s | "
                      f"Mouse: {mouse_count} | Screenshots: {screenshot_count}",
                      end="", flush=True)

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

            # Contar por tipo de trigger
            trigger_types = {}
            for s in screenshots:
                trigger = s.get('trigger_event_type', 'unknown')
                trigger_types[trigger] = trigger_types.get(trigger, 0) + 1

            print(f"\n📸 SCREENSHOTS (Basados en Eventos):")
            print(f"  Total capturados: {screenshot_count}")
            print(f"  Por tipo de trigger:")
            for trigger, count in trigger_types.items():
                print(f"    - {trigger}: {count}")
            print(f"  Tamaño total: {total_size_mb:.2f} MB")
            print(f"  Tamaño promedio: {avg_size / 1024:.2f} KB")
            print(f"  Directorio: data/screenshots/{self.session_uuid}/")
        else:
            print(f"\n📸 SCREENSHOTS:")
            print(f"  ⚠️  No se capturaron screenshots")
            print(f"  💡 Tip: Haz clicks o scrolls durante el tracking")

        # Generar heatmaps y overlays
        print()
        if events:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)

            # 1. Heatmap general (como antes)
            print("🎨 Generando heatmap general...")
            generator = HeatmapGenerator(
                screen_width=self.screen_width,
                screen_height=self.screen_height
            )

            heatmap_path = output_dir / f"heatmap_event_{timestamp}.png"
            generator.generate_from_events(
                events=events,
                output_path=heatmap_path,
                blur_radius=20
            )

            comparison_path = output_dir / f"comparison_event_{timestamp}.png"
            generator.generate_comparison(
                events=events,
                output_path=comparison_path
            )

            print(f"✓ Heatmap general: {heatmap_path.name}")
            print(f"✓ Comparación: {comparison_path.name}")

            # 2. Generar overlays sobre screenshots (NUEVO)
            if screenshot_count > 0:
                print()
                overlay_generator = HeatmapOverlayGenerator(
                    screen_width=self.screen_width,
                    screen_height=self.screen_height
                )

                overlay_dir = output_dir / f"overlays_{timestamp}"

                # Generar todos los overlays
                overlay_paths = overlay_generator.generate_all_overlays(
                    screenshots=screenshots,
                    all_events=events,
                    output_dir=overlay_dir,
                    time_window=5.0,  # 5 segundos antes de cada screenshot
                    blur_radius=25,
                    alpha=0.6,
                    show_clicks=True,
                    click_radius=20
                )

                # Crear grilla de comparación
                if overlay_paths:
                    grid_path = output_dir / f"overlay_grid_{timestamp}.png"
                    overlay_generator.create_comparison_grid(
                        screenshots=screenshots,
                        overlay_paths=overlay_paths,
                        output_path=grid_path,
                        max_per_row=2
                    )

                    print(f"\n✓ Overlays generados en: {overlay_dir}/")
                    print(f"✓ Grilla de comparación: {grid_path.name}")

            print()
            print("=" * 70)
            print("📊 RESUMEN DE VISUALIZACIONES GENERADAS")
            print("=" * 70)
            print(f"\n1. Heatmap General:")
            print(f"   - {heatmap_path}")
            print(f"   - {comparison_path}")

            if screenshot_count > 0:
                print(f"\n2. Heatmap Overlays ({len(overlay_paths)} screenshots):")
                print(f"   - Carpeta: {overlay_dir}/")
                print(f"   - Grilla comparativa: {grid_path}")
                print(f"\n💡 Los overlays muestran el contexto visual + heatmap de actividad")

        print()
        print("=" * 70)
        print("✅ Demo completada exitosamente!")
        print("=" * 70)
        print()
        print("📂 Archivos generados:")
        print(f"  - Base de datos: data/hci_logger.db")
        print(f"  - Screenshots: data/screenshots/{self.session_uuid}/")
        print(f"  - Heatmaps: output/")
        if screenshot_count > 0:
            print(f"  - Overlays: output/overlays_*/")
        print()

        # Cerrar base de datos
        self.db.close()


def main():
    """Punto de entrada"""
    # Duración desde argumentos o default 60 segundos
    duration = 60
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"⚠️  Duración inválida: {sys.argv[1]}")
            print("   Usando duración por defecto: 60 segundos")

    # Ejecutar demo
    demo = EventScreenshotDemo(duration=duration)
    demo.start()


if __name__ == "__main__":
    main()
