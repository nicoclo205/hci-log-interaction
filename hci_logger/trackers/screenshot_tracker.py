"""Screenshot tracker usando mss (muy rápido)"""

import time
import mss
from pathlib import Path
from typing import Optional, Callable
from PIL import Image
import io


class ScreenshotTracker:
    """Captura screenshots periódicas de la pantalla"""

    def __init__(
        self,
        session_id: int,
        on_screenshot_callback: Callable,
        output_dir: Path,
        interval: int = 5,
        format: str = 'png',
        quality: int = 85,
        monitor: int = 1
    ):
        """
        Args:
            session_id: ID de la sesión actual
            on_screenshot_callback: Callback que se llama cuando se captura un screenshot
            output_dir: Directorio donde guardar screenshots
            interval: Intervalo entre capturas en segundos
            format: Formato de imagen ('png', 'jpg')
            quality: Calidad de compresión (1-100, solo para jpg)
            monitor: Número de monitor (1 = primario, 0 = todos)
        """
        self.session_id = session_id
        self.on_screenshot_callback = on_screenshot_callback
        self.output_dir = Path(output_dir)
        self.interval = interval
        self.format = format.lower()
        self.quality = quality
        self.monitor = monitor

        self.sct: Optional[mss.mss] = None
        self.running = False
        self.screenshots_captured = 0

        # Crear directorio de output
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def start(self):
        """Iniciar captura de screenshots"""
        print(f"📸 Screenshot tracker starting...")
        print(f"   Output: {self.output_dir}")
        print(f"   Interval: {self.interval}s")
        print(f"   Format: {self.format}")

        self.sct = mss.mss()
        self.running = True

        # Obtener info del monitor
        monitor_info = self.sct.monitors[self.monitor]
        print(f"   Monitor: {monitor_info['width']}x{monitor_info['height']}")
        print(f"✓ Screenshot tracker started")

    def capture(self) -> bool:
        """
        Capturar un screenshot

        Returns:
            True si la captura fue exitosa, False en caso contrario
        """
        if not self.running or not self.sct:
            return False

        try:
            timestamp = time.time()

            # Capturar screenshot
            screenshot = self.sct.grab(self.sct.monitors[self.monitor])

            # Convertir a PIL Image
            img = Image.frombytes(
                'RGB',
                screenshot.size,
                screenshot.rgb
            )

            # Generar nombre de archivo
            filename = f"screenshot_{self.session_id}_{int(timestamp)}.{self.format}"
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
                'format': self.format
            })

            self.screenshots_captured += 1

            # Mensaje de progreso cada 10 screenshots
            if self.screenshots_captured % 10 == 0:
                print(f"  📸 {self.screenshots_captured} screenshots capturados")

            return True

        except Exception as e:
            print(f"❌ Error capturing screenshot: {e}")
            return False

    def run(self, duration: Optional[float] = None):
        """
        Ejecutar loop de captura

        Args:
            duration: Duración en segundos (None = infinito)
        """
        start_time = time.time()

        while self.running:
            # Verificar duración
            if duration and (time.time() - start_time) >= duration:
                break

            # Capturar screenshot
            self.capture()

            # Esperar intervalo
            time.sleep(self.interval)

    def stop(self):
        """Detener captura de screenshots"""
        self.running = False

        if self.sct:
            self.sct.close()
            self.sct = None

        print(f"✓ Screenshot tracker stopped ({self.screenshots_captured} screenshots captured)")

    def get_stats(self):
        """Obtener estadísticas del tracker"""
        return {
            'screenshots_captured': self.screenshots_captured,
            'output_dir': str(self.output_dir),
            'interval': self.interval,
            'format': self.format,
            'running': self.running
        }


class ScreenshotTrackerAsync:
    """
    Versión async del screenshot tracker para usar con threading

    Similar al MouseTracker, corre en su propio thread y captura
    screenshots periódicamente sin bloquear el thread principal
    """

    def __init__(
        self,
        session_id: int,
        on_screenshot_callback: Callable,
        output_dir: Path,
        interval: int = 5,
        format: str = 'png',
        quality: int = 85
    ):
        from threading import Thread, Event

        self.tracker = ScreenshotTracker(
            session_id=session_id,
            on_screenshot_callback=on_screenshot_callback,
            output_dir=output_dir,
            interval=interval,
            format=format,
            quality=quality
        )

        self._thread: Optional[Thread] = None
        self._stop_event = Event()

    def start(self):
        """Start tracker in background thread"""
        from threading import Thread

        self.tracker.start()

        self._thread = Thread(
            target=self._run,
            daemon=True,
            name="ScreenshotTracker"
        )
        self._thread.start()

    def _run(self):
        """Thread run method"""
        while not self._stop_event.is_set():
            self.tracker.capture()
            self._stop_event.wait(timeout=self.tracker.interval)

    def stop(self, timeout: float = 5.0):
        """Stop tracker gracefully"""
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=timeout)

        self.tracker.stop()

    def get_stats(self):
        """Get tracker stats"""
        return self.tracker.get_stats()
