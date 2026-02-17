# -*- coding: utf-8 -*-
"""Screenshot tracker basado en eventos (clicks y scrolls)"""

import time
import mss
from pathlib import Path
from typing import Optional, Callable
from PIL import Image
import threading


class EventBasedScreenshotTracker:
    """
    Captura screenshots solo cuando ocurren eventos significativos:
    - Clicks del mouse
    - Scrolls significativos

    Esto es más eficiente y útil que capturas periódicas porque:
    - Solo captura momentos de interacción real
    - Reduce espacio en disco
    - Cada screenshot tiene contexto significativo
    """

    def __init__(
        self,
        session_id: int,
        on_screenshot_callback: Callable,
        output_dir: Path,
        scroll_threshold: int = 100,
        cooldown: float = 0.5,
        format: str = 'png',
        quality: int = 85,
        monitor: int = 1
    ):
        """
        Args:
            session_id: ID de la sesión actual
            on_screenshot_callback: Callback que se llama cuando se captura un screenshot
            output_dir: Directorio donde guardar screenshots
            scroll_threshold: Scroll acumulado mínimo para triggerar screenshot (pixels)
            cooldown: Tiempo mínimo entre screenshots (segundos)
            format: Formato de imagen ('png', 'jpg')
            quality: Calidad de compresión (1-100, solo para jpg)
            monitor: Número de monitor (1 = primario, 0 = todos)
        """
        self.session_id = session_id
        self.on_screenshot_callback = on_screenshot_callback
        self.output_dir = Path(output_dir)
        self.scroll_threshold = scroll_threshold
        self.cooldown = cooldown
        self.format = format.lower()
        self.quality = quality
        self.monitor = monitor

        self.running = False
        self.screenshots_captured = 0

        # Control de cooldown
        self.last_screenshot_time = 0

        # Acumulador de scroll
        self.scroll_accumulator_x = 0
        self.scroll_accumulator_y = 0

        # Thread lock para evitar race conditions
        self.lock = threading.Lock()

        # Crear directorio de output
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def start(self):
        """Iniciar el tracker"""
        print(f"📸 Event-based screenshot tracker starting...")
        print(f"   Output: {self.output_dir}")
        print(f"   Triggers: clicks + scrolls (>{self.scroll_threshold}px)")
        print(f"   Cooldown: {self.cooldown}s")
        print(f"   Format: {self.format}")

        self.running = True

        # Obtener info del monitor
        with mss.mss() as sct:
            monitor_info = sct.monitors[self.monitor]
            print(f"   Monitor: {monitor_info['width']}x{monitor_info['height']}")

        print(f"✓ Event-based screenshot tracker started")

    def on_mouse_event(self, event: dict):
        """
        Callback para eventos de mouse

        Args:
            event: Diccionario con info del evento (tipo, coordenadas, etc.)
        """
        if not self.running:
            return

        event_type = event.get('event_type')

        # TRIGGER 1: Click
        if event_type == 'click' and event.get('pressed') is True:
            self._capture_on_event(
                event_type='click',
                x=event.get('x'),
                y=event.get('y'),
                button=event.get('button'),
                reason=f"click_{event.get('button')}"
            )

        # TRIGGER 2: Scroll significativo
        elif event_type == 'scroll':
            self._accumulate_scroll(
                dx=event.get('scroll_dx', 0) or 0,
                dy=event.get('scroll_dy', 0) or 0,
                x=event.get('x'),
                y=event.get('y')
            )

    def _accumulate_scroll(self, dx: float, dy: float, x: int, y: int):
        """
        Acumula scroll y captura screenshot si supera el threshold

        Args:
            dx: Scroll horizontal
            dy: Scroll vertical
            x: Posición X del mouse
            y: Posición Y del mouse
        """
        with self.lock:
            self.scroll_accumulator_x += abs(dx)
            self.scroll_accumulator_y += abs(dy)

            total_scroll = abs(self.scroll_accumulator_x) + abs(self.scroll_accumulator_y)

            if total_scroll >= self.scroll_threshold:
                # Reset acumulador
                self.scroll_accumulator_x = 0
                self.scroll_accumulator_y = 0

                # Capturar screenshot
                self._capture_on_event(
                    event_type='scroll',
                    x=x,
                    y=y,
                    scroll_amount=int(total_scroll),
                    reason=f"scroll_{int(total_scroll)}px"
                )

    def _capture_on_event(self, event_type: str, x: int, y: int, **metadata):
        """
        Captura screenshot si ha pasado el cooldown

        Args:
            event_type: Tipo de evento que triggereó ('click' o 'scroll')
            x: Coordenada X del evento
            y: Coordenada Y del evento
            **metadata: Metadata adicional del evento
        """
        current_time = time.time()

        # Verificar cooldown
        with self.lock:
            if (current_time - self.last_screenshot_time) < self.cooldown:
                return  # Ignorar, muy pronto desde el último screenshot

            self.last_screenshot_time = current_time

        # Capturar screenshot
        success = self._capture_screenshot(
            timestamp=current_time,
            trigger_event_type=event_type,
            trigger_x=x,
            trigger_y=y,
            metadata=metadata
        )

        if success:
            # Log visual
            reason = metadata.get('reason', event_type)
            print(f"  📸 Screenshot #{self.screenshots_captured} - Trigger: {reason} @ ({x}, {y})")

    def _capture_screenshot(
        self,
        timestamp: float,
        trigger_event_type: str,
        trigger_x: int,
        trigger_y: int,
        metadata: dict
    ) -> bool:
        """
        Captura el screenshot

        Args:
            timestamp: Timestamp del evento
            trigger_event_type: Tipo de evento ('click' o 'scroll')
            trigger_x: Coordenada X del evento trigger
            trigger_y: Coordenada Y del evento trigger
            metadata: Metadata adicional

        Returns:
            True si la captura fue exitosa
        """
        try:
            # Crear mss dentro de capture() para thread safety
            with mss.mss() as sct:
                screenshot = sct.grab(sct.monitors[self.monitor])

                # Convertir a PIL Image
                img = Image.frombytes(
                    'RGB',
                    screenshot.size,
                    screenshot.rgb
                )

            # Generar nombre de archivo
            filename = f"screenshot_{self.session_id}_{int(timestamp)}_{trigger_event_type}.{self.format}"
            file_path = self.output_dir / filename

            # Guardar imagen
            if self.format == 'png':
                img.save(file_path, format='PNG', optimize=True)
            elif self.format in ['jpg', 'jpeg']:
                img.save(file_path, format='JPEG', quality=self.quality, optimize=True)
            else:
                img.save(file_path)

            # Obtener tamaño del archivo
            file_size = file_path.stat().st_size

            # Llamar callback con la info
            self.on_screenshot_callback({
                'session_id': self.session_id,
                'timestamp': timestamp,
                'file_path': str(file_path),
                'file_size': file_size,
                'width': screenshot.width,
                'height': screenshot.height,
                'format': self.format,
                # Metadata del evento trigger
                'trigger_event_type': trigger_event_type,
                'trigger_x': trigger_x,
                'trigger_y': trigger_y,
                'trigger_metadata': metadata
            })

            self.screenshots_captured += 1
            return True

        except Exception as e:
            print(f"❌ Error capturing screenshot: {e}")
            return False

    def stop(self):
        """Detener el tracker"""
        self.running = False
        print(f"✓ Event-based screenshot tracker stopped ({self.screenshots_captured} screenshots captured)")

    def get_stats(self):
        """Obtener estadísticas del tracker"""
        return {
            'screenshots_captured': self.screenshots_captured,
            'output_dir': str(self.output_dir),
            'scroll_threshold': self.scroll_threshold,
            'cooldown': self.cooldown,
            'format': self.format,
            'running': self.running
        }
