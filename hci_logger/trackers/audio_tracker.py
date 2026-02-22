"""Audio tracker usando sounddevice"""

import time
import numpy as np
import sounddevice as sd
import soundfile as sf
from pathlib import Path
from typing import Optional, Callable
from threading import Thread, Event
from queue import Queue
import logging

logger = logging.getLogger(__name__)


class AudioTracker:
    """Captura audio del micrófono en segmentos"""

    def __init__(
        self,
        session_id: int,
        on_segment_callback: Callable,
        output_dir: Path,
        segment_duration: int = 60,
        sample_rate: int = 44100,
        channels: int = 1,
        device: Optional[int] = None
    ):
        """
        Args:
            session_id: ID de la sesión actual
            on_segment_callback: Callback llamado cuando se completa un segmento
            output_dir: Directorio donde guardar archivos de audio
            segment_duration: Duración de cada segmento en segundos
            sample_rate: Sample rate en Hz (44100 = calidad CD, 16000 = voz)
            channels: Número de canales (1 = mono, 2 = stereo)
            device: ID del dispositivo de entrada (None = default)
        """
        self.session_id = session_id
        self.on_segment_callback = on_segment_callback
        self.output_dir = Path(output_dir)
        self.segment_duration = segment_duration
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device

        self.stream: Optional[sd.InputStream] = None
        self.running = False
        self.segments_captured = 0

        # Buffer de audio
        self.audio_buffer = Queue()
        self.current_segment = []
        self.segment_start_time = None

        # Thread para escritura de archivos
        self._writer_thread: Optional[Thread] = None
        self._stop_event = Event()

        # Crear directorio de output
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def start(self):
        """Iniciar captura de audio"""
        print(f"🎤 Audio tracker starting...")
        print(f"   Output: {self.output_dir}")
        print(f"   Sample rate: {self.sample_rate} Hz")
        print(f"   Channels: {self.channels}")
        print(f"   Segment duration: {self.segment_duration}s")

        # Verificar dispositivos disponibles
        try:
            devices = sd.query_devices()
            if self.device is None:
                default_device = sd.query_devices(kind='input')
                print(f"   Device: {default_device['name']} (default)")
            else:
                device_info = devices[self.device]
                print(f"   Device: {device_info['name']}")
        except Exception as e:
            print(f"⚠️  Warning: Could not query audio devices: {e}")

        self.running = True
        self.segment_start_time = time.time()

        # Iniciar stream de audio
        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                device=self.device,
                callback=self._audio_callback
            )
            self.stream.start()
            print(f"✓ Audio tracker started")

            # Iniciar thread de escritura
            self._writer_thread = Thread(
                target=self._writer_loop,
                daemon=True,
                name="AudioWriter"
            )
            self._writer_thread.start()

        except Exception as e:
            print(f"❌ Error starting audio stream: {e}")
            print(f"   Tip: Check microphone permissions")
            self.running = False
            raise

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback del stream de audio"""
        if status:
            logger.warning(f"Audio stream status: {status}")

        # Copiar datos al buffer
        audio_data = indata.copy()
        self.current_segment.append(audio_data)

        # Verificar si completamos un segmento
        elapsed = time.time() - self.segment_start_time
        if elapsed >= self.segment_duration:
            # Enviar segmento al queue de escritura
            segment_data = np.concatenate(self.current_segment, axis=0)
            self.audio_buffer.put({
                'data': segment_data,
                'start_time': self.segment_start_time,
                'end_time': time.time()
            })

            # Resetear para siguiente segmento
            self.current_segment = []
            self.segment_start_time = time.time()

    def _writer_loop(self):
        """Loop que escribe segmentos de audio a disco"""
        while self.running or not self.audio_buffer.empty():
            try:
                # Esperar por segmento con timeout
                if not self.audio_buffer.empty():
                    segment_info = self.audio_buffer.get(timeout=1.0)

                    # Guardar segmento
                    self._save_segment(
                        audio_data=segment_info['data'],
                        start_time=segment_info['start_time'],
                        end_time=segment_info['end_time']
                    )
                else:
                    time.sleep(0.1)

            except Exception as e:
                if self.running:  # Solo log si no estamos cerrando
                    logger.error(f"Error in writer loop: {e}")

    def _save_segment(self, audio_data: np.ndarray, start_time: float, end_time: float):
        """Guardar un segmento de audio a archivo"""
        try:
            duration = end_time - start_time

            # Generar nombre de archivo
            filename = f"audio_{self.session_id}_{int(start_time)}.wav"
            file_path = self.output_dir / filename

            # Guardar usando soundfile
            sf.write(
                file_path,
                audio_data,
                self.sample_rate,
                subtype='PCM_16'  # 16-bit PCM
            )

            # Obtener tamaño del archivo
            file_size = file_path.stat().st_size

            # Llamar callback
            self.on_segment_callback({
                'session_id': self.session_id,
                'start_timestamp': start_time,
                'end_timestamp': end_time,
                'duration': duration,
                'file_path': str(file_path),
                'sample_rate': self.sample_rate,
                'channels': self.channels,
                'file_size': file_size
            })

            self.segments_captured += 1

            # Mensaje de progreso
            file_size_kb = file_size / 1024
            print(f"  🎤 Segmento {self.segments_captured} guardado "
                  f"({duration:.1f}s, {file_size_kb:.1f} KB)")

        except Exception as e:
            logger.error(f"Error saving audio segment: {e}")

    def stop(self):
        """Detener captura de audio"""
        # 1. Parar el stream primero para que no lleguen más callbacks
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        # 2. Encolar segmento final ANTES de señalar parada,
        #    así el writer_loop no puede salir antes de procesarlo
        if self.current_segment:
            segment_data = np.concatenate(self.current_segment, axis=0)
            self.audio_buffer.put({
                'data': segment_data,
                'start_time': self.segment_start_time,
                'end_time': time.time()
            })

        # 3. Ahora señalar parada (el writer_loop ve la cola no vacía y termina limpio)
        self.running = False

        # 4. Esperar al writer thread con tiempo suficiente para procesar
        if self._writer_thread:
            self._writer_thread.join(timeout=10.0)

        print(f"✓ Audio tracker stopped ({self.segments_captured} segments captured)")

    def get_stats(self):
        """Obtener estadísticas del tracker"""
        return {
            'segments_captured': self.segments_captured,
            'output_dir': str(self.output_dir),
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'segment_duration': self.segment_duration,
            'running': self.running
        }


class AudioTrackerAsync:
    """
    Versión async del audio tracker para uso con otros trackers

    El audio tracker ya es inherentemente async (usa callbacks),
    pero esta clase provee una interfaz consistente con otros trackers
    """

    def __init__(
        self,
        session_id: int,
        on_segment_callback: Callable,
        output_dir: Path,
        segment_duration: int = 60,
        sample_rate: int = 44100,
        channels: int = 1
    ):
        self.tracker = AudioTracker(
            session_id=session_id,
            on_segment_callback=on_segment_callback,
            output_dir=output_dir,
            segment_duration=segment_duration,
            sample_rate=sample_rate,
            channels=channels
        )

    def start(self):
        """Start audio tracking"""
        self.tracker.start()

    def stop(self, timeout: float = 5.0):
        """Stop audio tracking"""
        self.tracker.stop()

    def get_stats(self):
        """Get tracker stats"""
        return self.tracker.get_stats()


def list_audio_devices():
    """Listar dispositivos de audio disponibles"""
    print("\n🎤 Dispositivos de Audio Disponibles:\n")
    devices = sd.query_devices()

    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            is_default = " (DEFAULT)" if i == sd.default.device[0] else ""
            print(f"  [{i}] {device['name']}{is_default}")
            print(f"      Channels: {device['max_input_channels']} in, "
                  f"{device['max_output_channels']} out")
            print(f"      Sample rate: {device['default_samplerate']} Hz")
            print()


if __name__ == "__main__":
    # Listar dispositivos disponibles
    list_audio_devices()
