#!/usr/bin/env python3
"""
HCI Logger — Estudio de Usabilidad Facebook

Pregunta de investigación:
  ¿Qué tan fácil es para usuarios jóvenes (20-25 años) sin experiencia previa en
  Facebook completar el proceso de creación de una fanpage, y en qué etapas del
  flujo encuentran mayor dificultad para adaptarse a la interfaz de la plataforma?

Captura:
  - Movimientos y clicks del mouse (heatmap)
  - Screenshots en cada click/scroll
  - Audio completo de la sesión (un único archivo WAV)
  - Emociones faciales en tiempo real (DeepFace)

Población objetivo: 20-25 años, sin experiencia previa en Facebook.

Uso:
    python main.py   (desde el entorno hci-env)
"""

import os
import sys

# ── Desactivar accesibilidad de Qt ANTES de importar PySide6 ──────────────────
# Esto elimina el botón nativo "Cerrar" que Qt genera sobre los modales web.
os.environ["QT_ACCESSIBILITY"] = "0"
os.environ["QT_LINUX_ACCESSIBILITY_ALWAYS_ON"] = "0"

# Deshabilitar infobars y notificaciones del motor Chromium embebido
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--disable-notifications "
    "--disable-infobars "
    "--disable-save-password-bubble "
    "--disable-translate "
    "--disable-features=Accessibility,TranslateUI,PasswordManagerOnboarding "
    "--force-renderer-accessibility=false"
)

import uuid
import threading
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFrame, QLabel, QPushButton, QLineEdit, QTextEdit,
    QSizePolicy, QDialog, QTabWidget, QScrollArea,
    QGridLayout, QSlider, QFileDialog, QMessageBox,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineScript,
)
from PySide6.QtCore import QUrl, Qt, Signal, QObject
from PySide6.QtGui import QFont, QPixmap

sys.path.insert(0, str(Path(__file__).parent))

from hci_logger.storage.database import Database
from hci_logger.trackers.mouse_tracker import MouseTracker
from hci_logger.trackers.event_screenshot_tracker import EventBasedScreenshotTracker
from hci_logger.trackers.audio_tracker import AudioTrackerAsync
from hci_logger.trackers.emotion_tracker import EmotionTrackerAsync
from hci_logger.processing.heatmap import HeatmapGenerator

# ── Configuración ─────────────────────────────────────────────────────────────
TARGET_URL = "https://www.facebook.com"

TASKS = {
    1: "Crear un fanpage en Facebook",
}

EMOTION_EMOJIS = {
    "happy": "😊", "sad": "😢", "angry": "😠",
    "fear": "😨", "surprise": "😲", "disgust": "🤢", "neutral": "😐",
}


# ── Señales Qt ────────────────────────────────────────────────────────────────

class SilentWebPage(QWebEnginePage):
    """Página personalizada que suprime TODOS los diálogos/popups nativos de Qt
    para evitar el botón 'Cerrar' que interfiere con el tracking de clicks."""

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        # Denegar automáticamente todas las solicitudes de permisos (notificaciones, etc.)
        self.featurePermissionRequested.connect(self._deny_permission)
        # Desactivar notificaciones push
        try:
            self.setNotificationPresenter(lambda notification: notification.close())
        except Exception:
            pass

    def _deny_permission(self, origin, feature):
        """Denegar todas las solicitudes de permisos (notificaciones, geoloc, cámara, etc.)"""
        self.setFeaturePermission(origin, feature, QWebEnginePage.PermissionDeniedByUser)

    def javaScriptAlert(self, securityOrigin, msg):
        pass  # Suprimir alertas JS

    def javaScriptConfirm(self, securityOrigin, msg):
        return True  # Aceptar automáticamente

    def javaScriptPrompt(self, securityOrigin, msg, defaultValue):
        return (True, defaultValue)  # Devolver valor por defecto

    def certificateError(self, error):
        error.acceptCertificate()
        return True

    def createWindow(self, window_type):
        return None  # Bloquear popups / ventanas nuevas


class UISignals(QObject):
    click_count_updated      = Signal(int)
    screenshot_count_updated = Signal(int)
    emotion_updated          = Signal(str)
    log_message              = Signal(str)


# ── Diálogo de análisis post-sesión ──────────────────────────────────────────
class ReportDialog(QDialog):
    """Muestra el análisis de la sesión recién finalizada."""

    # Resolución lógica de pantalla (coordenadas del mouse de pynput)
    SCREEN_W = 1920
    SCREEN_H = 1080

    def __init__(self, session_id: int, session_uuid: str, db: Database,
                 heatmap_path=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Análisis de Sesión")
        self.resize(1050, 750)
        self.setStyleSheet("background: #1e2124; color: #dcddde;")

        self._heatmap_path = heatmap_path   # ruta exacta del heatmap de esta sesión
        self._players = []                  # QMediaPlayer refs (evitar GC)

        # Cargar todos los datos una sola vez
        self._mouse_events   = db.get_mouse_events(session_id)
        self._screenshots    = db.get_screenshots(session_id)
        self._audio_segments = db.get_audio_segments(session_id)
        self._emotions       = db.get_emotion_events(session_id)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel(f"Análisis — Sesión {session_uuid[:8]}…")
        title.setStyleSheet("font-size: 15px; font-weight: bold; padding: 6px 2px;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #40444b; }"
            "QTabBar::tab { background: #2f3136; color: #dcddde; padding: 8px 16px; }"
            "QTabBar::tab:selected { background: #7289da; color: white; }"
        )
        layout.addWidget(tabs)

        tabs.addTab(self._build_stats_tab(session_id, db),        "📊 Resumen")
        tabs.addTab(self._build_screenshots_tab(),                 "📸 Capturas")
        tabs.addTab(self._build_heatmap_tab(),                     "🗺 Heatmap General")
        tabs.addTab(self._build_audio_tab(),                       "🎵 Audio")
        tabs.addTab(self._build_emotions_tab(session_id, db),      "😊 Emociones")

        close_btn = QPushButton("Cerrar")
        close_btn.setStyleSheet(
            "QPushButton { background: #7289da; color: white; border-radius: 4px; "
            "padding: 8px 24px; font-size: 13px; } "
            "QPushButton:hover { background: #677bc4; }"
        )
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _build_stats_tab(self, session_id: int, db: Database) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: #2f3136;")
        grid = QGridLayout(w)
        grid.setSpacing(12)
        grid.setContentsMargins(20, 20, 20, 20)

        events = self._mouse_events
        clicks  = sum(1 for e in events if e["event_type"] == "click" and e["pressed"])
        moves   = sum(1 for e in events if e["event_type"] == "move")
        scrolls = sum(1 for e in events if e["event_type"] == "scroll")
        audio_s = sum(s["duration"] for s in self._audio_segments)

        stats = [
            ("Tarea",                  "T1: Crear un fanpage en Facebook"),
            ("Clicks totales",         str(clicks)),
            ("Movimientos de mouse",   f"{moves:,}"),
            ("Scrolls",                str(scrolls)),
            ("Screenshots capturados", str(len(self._screenshots))),
            ("Audio grabado",          f"{len(self._audio_segments)} archivo(s)  ({audio_s / 60:.1f} min)"),
            ("Eventos de emoción",     str(len(self._emotions))),
        ]

        for row, (label, value) in enumerate(stats):
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #72767d; font-size: 13px;")
            val = QLabel(value)
            val.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
            grid.addWidget(lbl, row, 0)
            grid.addWidget(val, row, 1)

        grid.setRowStretch(len(stats), 1)
        return w

    def _build_screenshots_tab(self) -> QWidget:
        """Galería de screenshots con heatmap overlay y marcadores de clicks."""
        w = QWidget()
        w.setStyleSheet("background: #2f3136;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        if not self._screenshots:
            lbl = QLabel("No hay capturas de pantalla en esta sesión.")
            lbl.setStyleSheet("color: #72767d; font-size: 13px;")
            lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl, alignment=Qt.AlignCenter)
            return w

        top_row = QHBoxLayout()
        header = QLabel(
            f"{len(self._screenshots)} capturas  —  "
            f"heatmap de actividad de mouse + círculos rojos = clicks"
        )
        header.setStyleSheet("color: #72767d; font-size: 11px;")
        top_row.addWidget(header, stretch=1)

        exp_btn = QPushButton("📁 Exportar capturas…")
        exp_btn.setFixedHeight(26)
        exp_btn.setStyleSheet(
            "QPushButton { background: #4f545c; color: #dcddde; border-radius: 4px; "
            "font-size: 11px; padding: 0 10px; }"
            "QPushButton:hover { background: #5d6269; }"
        )
        shots = list(self._screenshots)
        exp_btn.clicked.connect(lambda: self._export_files(
            [s["file_path"] for s in shots], "capturas"
        ))
        top_row.addWidget(exp_btn)
        layout.addLayout(top_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #2f3136; }")

        gallery = QWidget()
        gallery.setStyleSheet("background: #2f3136;")
        gallery_layout = QVBoxLayout(gallery)
        gallery_layout.setSpacing(10)
        gallery_layout.setContentsMargins(0, 0, 4, 0)

        MAX_W = 980  # ancho máximo de imagen en la galería

        for i, ss in enumerate(self._screenshots):
            ts_str      = datetime.fromtimestamp(ss["timestamp"]).strftime("%H:%M:%S")
            task_str    = f"T{ss.get('task_id', '?')}"
            trigger_str = ss.get("trigger_event_type", "periodic") or "periodic"
            pos_str     = f"({ss.get('trigger_x', '?')}, {ss.get('trigger_y', '?')})" \
                          if ss.get("trigger_x") else ""

            card = QFrame()
            card.setStyleSheet(
                "QFrame { background: #23272a; border-radius: 6px; padding: 6px; }"
            )
            card_v = QVBoxLayout(card)
            card_v.setSpacing(4)

            # Info row
            info = QLabel(
                f"<b style='color:#dcddde'>#{i+1}</b>"
                f"  <span style='color:#72767d'>[{ts_str}]</span>"
                f"  <span style='color:#7289da'>{task_str}</span>"
                f"  <span style='color:#72767d'>trigger: {trigger_str}  {pos_str}</span>"
            )
            info.setStyleSheet("font-size: 11px;")
            card_v.addWidget(info)

            # Overlay image (generated on-the-fly with PIL)
            pixmap = self._make_overlay_pixmap(ss, self._mouse_events)
            img_lbl = QLabel()
            if pixmap and not pixmap.isNull():
                scaled = pixmap.scaledToWidth(MAX_W, Qt.SmoothTransformation)
                img_lbl.setPixmap(scaled)
            else:
                img_lbl.setText("No se pudo generar la visualización")
                img_lbl.setStyleSheet("color: #555; font-size: 12px;")
            img_lbl.setAlignment(Qt.AlignCenter)
            card_v.addWidget(img_lbl)

            gallery_layout.addWidget(card)

        gallery_layout.addStretch()
        scroll.setWidget(gallery)
        layout.addWidget(scroll)
        return w

    def _build_heatmap_tab(self) -> QWidget:
        """Muestra el heatmap de movimientos y clicks de esta sesión."""
        w = QWidget()
        w.setStyleSheet("background: #2f3136;")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)

        img_path = Path(self._heatmap_path) if self._heatmap_path else None

        if img_path and img_path.exists():
            # Botón de exportar
            export_row = QHBoxLayout()
            export_row.setContentsMargins(8, 8, 8, 4)
            exp_btn = QPushButton("📁 Exportar heatmap…")
            exp_btn.setFixedHeight(30)
            exp_btn.setStyleSheet(
                "QPushButton { background: #4f545c; color: #dcddde; border-radius: 4px; "
                "font-size: 12px; padding: 0 12px; }"
                "QPushButton:hover { background: #5d6269; }"
            )
            exp_btn.clicked.connect(lambda: self._export_files([str(img_path)], "heatmap"))
            export_row.addStretch()
            export_row.addWidget(exp_btn)
            v.addLayout(export_row)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { border: none; background: #2f3136; }")
            img_label = QLabel()
            pixmap = QPixmap(str(img_path))
            img_label.setPixmap(pixmap.scaledToWidth(1020, Qt.SmoothTransformation))
            img_label.setAlignment(Qt.AlignCenter)
            scroll.setWidget(img_label)
            v.addWidget(scroll)
        else:
            info = QLabel("No se encontró heatmap.\n(Se genera al finalizar la sesión.)")
            info.setStyleSheet("color: #72767d; font-size: 13px;")
            info.setAlignment(Qt.AlignCenter)
            v.addWidget(info, alignment=Qt.AlignCenter)

        return w

    def _build_audio_tab(self) -> QWidget:
        """Reproductor de audio de la sesión + exportación."""
        w = QWidget()
        w.setStyleSheet("background: #2f3136;")
        outer = QVBoxLayout(w)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        if not self._audio_segments:
            lbl = QLabel("No hay audio grabado en esta sesión.")
            lbl.setStyleSheet("color: #72767d; font-size: 13px;")
            lbl.setAlignment(Qt.AlignCenter)
            outer.addWidget(lbl, alignment=Qt.AlignCenter)
            return w

        # Importar multimedia (opcional — falla silenciosamente)
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            multimedia_ok = True
        except ImportError:
            multimedia_ok = False

        for seg in self._audio_segments:
            file_path = Path(seg["file_path"])
            dur_min  = seg["duration"] / 60
            size_kb  = seg["file_size"] / 1024

            card = QFrame()
            card.setStyleSheet(
                "QFrame { background: #23272a; border-radius: 6px; padding: 6px; }"
            )
            card_v = QVBoxLayout(card)
            card_v.setSpacing(6)

            # ── Info ──
            info_row = QHBoxLayout()
            fname_lbl = QLabel(file_path.name)
            fname_lbl.setStyleSheet("color: #dcddde; font-size: 12px; font-weight: bold;")
            info_row.addWidget(fname_lbl)
            meta_lbl = QLabel(
                f"  {dur_min:.1f} min  ·  {size_kb:.0f} KB  ·  {seg['sample_rate']} Hz"
            )
            meta_lbl.setStyleSheet("color: #72767d; font-size: 11px;")
            info_row.addWidget(meta_lbl)
            info_row.addStretch()
            card_v.addLayout(info_row)

            # ── Controles de reproducción ──
            if multimedia_ok and file_path.exists():
                player = QMediaPlayer()
                audio_out = QAudioOutput()
                audio_out.setVolume(1.0)
                player.setAudioOutput(audio_out)
                player.setSource(QUrl.fromLocalFile(str(file_path.resolve())))
                self._players.append((player, audio_out))

                ctrl_row = QHBoxLayout()
                ctrl_row.setSpacing(8)

                btn_play = QPushButton("▶ Play")
                btn_play.setFixedWidth(90)
                btn_play.setStyleSheet(
                    "QPushButton { background: #43b581; color: white; border-radius: 4px; "
                    "font-size: 12px; padding: 4px 8px; }"
                    "QPushButton:hover { background: #3ca374; }"
                )

                btn_stop = QPushButton("⏹ Stop")
                btn_stop.setFixedWidth(90)
                btn_stop.setStyleSheet(
                    "QPushButton { background: #4f545c; color: #dcddde; border-radius: 4px; "
                    "font-size: 12px; padding: 4px 8px; }"
                    "QPushButton:hover { background: #5d6269; }"
                )

                slider = QSlider(Qt.Horizontal)
                slider.setRange(0, 0)
                slider.setStyleSheet(
                    "QSlider::groove:horizontal { height: 4px; background: #40444b; border-radius: 2px; }"
                    "QSlider::handle:horizontal { width: 12px; height: 12px; margin: -4px 0; "
                    "background: #7289da; border-radius: 6px; }"
                    "QSlider::sub-page:horizontal { background: #7289da; border-radius: 2px; }"
                )

                pos_lbl = QLabel("0:00 / 0:00")
                pos_lbl.setStyleSheet("color: #72767d; font-size: 11px; min-width: 80px;")
                pos_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

                # Closures para conectar señales correctamente por iteración
                def _make_play_cb(p, btn):
                    def cb():
                        from PySide6.QtMultimedia import QMediaPlayer as _MP
                        if p.playbackState() == _MP.PlaybackState.PlayingState:
                            p.pause()
                            btn.setText("▶ Play")
                        else:
                            p.play()
                            btn.setText("⏸ Pausa")
                    return cb

                def _make_stop_cb(p, btn):
                    def cb():
                        p.stop()
                        btn.setText("▶ Play")
                    return cb

                def _make_pos_cb(sl, lbl, p):
                    def cb(pos):
                        if not sl.isSliderDown():
                            sl.setValue(pos)
                        dur = p.duration()
                        ps, ds = pos // 1000, dur // 1000
                        lbl.setText(f"{ps//60}:{ps%60:02d} / {ds//60}:{ds%60:02d}")
                    return cb

                def _make_dur_cb(sl):
                    def cb(dur):
                        sl.setRange(0, dur)
                    return cb

                def _make_seek_cb(p):
                    def cb(val):
                        p.setPosition(val)
                    return cb

                btn_play.clicked.connect(_make_play_cb(player, btn_play))
                btn_stop.clicked.connect(_make_stop_cb(player, btn_play))
                player.positionChanged.connect(_make_pos_cb(slider, pos_lbl, player))
                player.durationChanged.connect(_make_dur_cb(slider))
                slider.sliderMoved.connect(_make_seek_cb(player))

                ctrl_row.addWidget(btn_play)
                ctrl_row.addWidget(btn_stop)
                ctrl_row.addWidget(slider, stretch=1)
                ctrl_row.addWidget(pos_lbl)
                card_v.addLayout(ctrl_row)

            elif not file_path.exists():
                warn = QLabel(f"Archivo no encontrado: {file_path}")
                warn.setStyleSheet("color: #f04747; font-size: 11px;")
                card_v.addWidget(warn)
            else:
                warn = QLabel("Reproducción no disponible (PySide6.QtMultimedia no encontrado).")
                warn.setStyleSheet("color: #72767d; font-size: 11px;")
                card_v.addWidget(warn)

            outer.addWidget(card)

        outer.addStretch()

        # ── Botón exportar ──
        segs = list(self._audio_segments)
        exp_btn = QPushButton("📁 Exportar audio(s) a carpeta…")
        exp_btn.setFixedHeight(36)
        exp_btn.setStyleSheet(
            "QPushButton { background: #7289da; color: white; border-radius: 6px; "
            "font-size: 13px; padding: 0 16px; }"
            "QPushButton:hover { background: #677bc4; }"
        )
        exp_btn.clicked.connect(lambda: self._export_files(
            [s["file_path"] for s in segs], "audio"
        ))
        outer.addWidget(exp_btn)

        return w

    # ── Exportación genérica ──────────────────────────────────────────────────

    def _export_files(self, file_paths: list, kind: str = "archivos"):
        """Copia una lista de archivos a una carpeta elegida por el usuario."""
        import shutil
        folder = QFileDialog.getExistingDirectory(
            self, f"Seleccionar carpeta de destino para {kind}", str(Path.home())
        )
        if not folder:
            return
        dest = Path(folder)
        copied, missing = 0, 0
        for fp in file_paths:
            src = Path(fp)
            if src.exists():
                shutil.copy2(src, dest / src.name)
                copied += 1
            else:
                missing += 1
        msg = f"{copied} archivo(s) copiados a:\n{folder}"
        if missing:
            msg += f"\n\n({missing} archivo(s) no encontrado(s))"
        QMessageBox.information(self, "Exportación completada", msg)

    def _build_emotions_tab(self, session_id: int, db: Database) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: #2f3136;")
        v = QVBoxLayout(w)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(8)

        emotions = self._emotions
        if not emotions:
            lbl = QLabel("Sin datos de emoción en esta sesión.")
            lbl.setStyleSheet("color: #72767d; font-size: 13px;")
            v.addWidget(lbl, alignment=Qt.AlignCenter)
            return w

        summary = db.get_dominant_emotions_summary(session_id)
        total   = len(emotions)

        title = QLabel("Distribución de emociones dominantes (sesión completa)")
        title.setStyleSheet("color: #dcddde; font-size: 13px; font-weight: bold;")
        v.addWidget(title)

        BAR_W = 420
        for emotion, count in sorted(summary.items(), key=lambda x: x[1], reverse=True):
            pct   = (count / total) * 100
            emoji = EMOTION_EMOJIS.get(emotion, "❓")
            row   = QHBoxLayout()

            name_lbl = QLabel(f"{emoji}  {emotion}")
            name_lbl.setStyleSheet("color: #dcddde; font-size: 13px; min-width: 110px;")
            row.addWidget(name_lbl)

            bar_bg = QFrame()
            bar_bg.setStyleSheet("background: #40444b; border-radius: 4px;")
            bar_bg.setFixedHeight(18)
            bar_bg.setFixedWidth(BAR_W)
            bar_fill = QFrame(bar_bg)
            bar_fill.setFixedHeight(18)
            bar_fill.setFixedWidth(max(2, int(BAR_W * pct / 100)))
            bar_fill.setStyleSheet("background: #7289da; border-radius: 4px;")
            row.addWidget(bar_bg)

            pct_lbl = QLabel(f"{pct:.1f}%  ({count})")
            pct_lbl.setStyleSheet("color: #72767d; font-size: 12px; min-width: 90px;")
            row.addWidget(pct_lbl)

            row.addStretch()
            v.addLayout(row)

        v.addSpacing(16)
        task_title = QLabel("Emoción dominante por tarea")
        task_title.setStyleSheet("color: #dcddde; font-size: 13px; font-weight: bold;")
        v.addWidget(task_title)

        for task_id, task_name in TASKS.items():
            task_emotions = [e for e in emotions if e.get("task_id") == task_id]
            if not task_emotions:
                continue
            task_summary: dict[str, int] = {}
            for e in task_emotions:
                d = e["dominant_emotion"]
                task_summary[d] = task_summary.get(d, 0) + 1
            top   = max(task_summary, key=task_summary.get)
            emoji = EMOTION_EMOJIS.get(top, "❓")
            lbl   = QLabel(f"T{task_id}: {task_name}  →  {emoji} {top}")
            lbl.setStyleSheet("color: #b9ffa0; font-size: 12px;")
            v.addWidget(lbl)

        v.addStretch()
        return w

    # ── Generación de overlays con PIL (sin matplotlib) ───────────────────────

    @staticmethod
    def _make_overlay_pixmap(screenshot_info: dict, mouse_events: list):
        """
        Genera en memoria un overlay de heatmap + clicks sobre el screenshot.
        Usa PIL + scipy para rapidez, sin necesidad de matplotlib.
        Devuelve un QPixmap o None si hay error.
        """
        try:
            import numpy as np
            from PIL import Image, ImageDraw
            from scipy.ndimage import gaussian_filter
            from io import BytesIO

            path = Path(screenshot_info["file_path"])
            if not path.exists():
                return None

            img    = Image.open(path).convert("RGB")
            img_w, img_h = img.size

            # Dimensiones lógicas de pantalla (coordenadas de pynput)
            SCREEN_W = screenshot_info.get("width")  or img_w
            SCREEN_H = screenshot_info.get("height") or img_h

            # ── Heatmap de movimientos ─────────────────────────────────────────
            hm     = np.zeros((SCREEN_H, SCREEN_W), dtype=np.float32)
            clicks = []

            for e in mouse_events:
                ex = max(0, min(int(e["x"]), SCREEN_W - 1))
                ey = max(0, min(int(e["y"]), SCREEN_H - 1))
                if e["event_type"] in ("move", "click"):
                    hm[ey, ex] += 1.0
                if e["event_type"] == "click" and e.get("pressed"):
                    clicks.append((e["x"], e["y"]))

            hm = gaussian_filter(hm, sigma=25)
            if hm.max() > 0:
                hm /= hm.max()

            # Escalar heatmap al tamaño real del screenshot
            hm_pil    = Image.fromarray((hm * 255).astype(np.uint8)).resize(
                (img_w, img_h), Image.LANCZOS
            )
            hm_scaled = np.array(hm_pil).astype(np.float32) / 255.0

            # Colormap jet-like: azul → cian → verde → amarillo → rojo
            r_ch = np.clip(hm_scaled * 2.0 - 0.0, 0, 1)
            g_ch = np.clip(1.0 - np.abs(hm_scaled * 2.0 - 1.0), 0, 1)
            b_ch = np.clip(1.0 - hm_scaled * 2.0, 0, 1)
            a_ch = (hm_scaled * 170).astype(np.uint8)

            hm_rgba = np.stack([
                (r_ch * 255).astype(np.uint8),
                (g_ch * 255).astype(np.uint8),
                (b_ch * 255).astype(np.uint8),
                a_ch,
            ], axis=-1)

            overlay_layer = Image.fromarray(hm_rgba, "RGBA")
            result        = Image.alpha_composite(img.convert("RGBA"), overlay_layer)

            # ── Marcadores de clicks ───────────────────────────────────────────
            if clicks:
                draw = ImageDraw.Draw(result)
                sx   = img_w / SCREEN_W
                sy   = img_h / SCREEN_H

                for cx, cy in clicks:
                    px  = int(cx * sx)
                    py  = int(cy * sy)
                    r   = max(10, int(16 * min(sx, sy)))

                    # Anillo blanco exterior (visibilidad)
                    draw.ellipse(
                        [px - r - 3, py - r - 3, px + r + 3, py + r + 3],
                        outline=(255, 255, 255, 200), width=3,
                    )
                    # Círculo rojo semi-transparente
                    draw.ellipse(
                        [px - r, py - r, px + r, py + r],
                        outline=(220, 50, 50, 255),
                        fill=(220, 50, 50, 140),
                        width=2,
                    )
                    # Punto central blanco
                    draw.ellipse(
                        [px - 4, py - 4, px + 4, py + 4],
                        fill=(255, 255, 255, 255),
                    )

            # ── Convertir a QPixmap ───────────────────────────────────────────
            buf = BytesIO()
            result.convert("RGB").save(buf, format="PNG")
            buf.seek(0)
            pixmap = QPixmap()
            pixmap.loadFromData(buf.getvalue())
            return pixmap

        except Exception as e:
            print(f"Error generando overlay: {e}")
            return None


# ── Ventana principal ─────────────────────────────────────────────────────────
class HCILoggerWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HCI Logger — Estudio Facebook")
        self.resize(1440, 900)

        self.signals = UISignals()

        # Estado de sesión
        self.db              = Database()
        self.session_id      = None
        self.session_uuid    = None
        self.current_task_id = 1
        self.is_recording    = False
        self.click_count     = 0

        # Trackers
        self.mouse_tracker      = None
        self.screenshot_tracker = None
        self.audio_tracker      = None
        self.emotion_tracker    = None

        self._last_heatmap_path = None   # ruta del heatmap de la sesión más reciente

        # Buffer de mouse – NOTA: flush se extrae fuera del lock para evitar deadlock
        self._event_buffer = []
        self._buffer_lock  = threading.Lock()
        self._BUFFER_SIZE  = 50

        self._stopping = False

        self._build_ui()
        self._connect_signals()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        self.browser = QWebEngineView()

        # Usar página personalizada que suprime diálogos JS y permisos
        profile = QWebEngineProfile.defaultProfile()
        profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)

        # Inyectar JS al inicio que deshabilita la Notification API
        # (Facebook no podrá pedir permisos de notificaciones → sin popup "Cerrar")
        kill_notifications_js = QWebEngineScript()
        kill_notifications_js.setName("KillNotifications")
        kill_notifications_js.setSourceCode("""
            // Deshabilitar Notification API para evitar solicitud de permisos
            Object.defineProperty(window, 'Notification', {
                value: function() {},
                writable: false,
                configurable: false,
            });
            window.Notification.permission = 'denied';
            window.Notification.requestPermission = function() {
                return Promise.resolve('denied');
            };

            // Deshabilitar Service Workers (push notifications)
            if (navigator.serviceWorker) {
                Object.defineProperty(navigator, 'serviceWorker', {
                    value: { register: function() { return Promise.reject(); } },
                    writable: false,
                });
            }
        """)
        kill_notifications_js.setInjectionPoint(QWebEngineScript.DocumentCreation)
        kill_notifications_js.setWorldId(QWebEngineScript.MainWorld)
        kill_notifications_js.setRunsOnSubFrames(True)
        profile.scripts().insert(kill_notifications_js)

        silent_page = SilentWebPage(profile, self.browser)
        self.browser.setPage(silent_page)

        # Deshabilitar ventanas emergentes y notificaciones
        settings = self.browser.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, False)

        # Inyectar JS adicional después de cargar para cerrar modales de Facebook
        self.browser.loadFinished.connect(self._inject_modal_killer)

        self.browser.load(QUrl(TARGET_URL))
        self.browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.browser, stretch=1)

        root.addWidget(self._build_bottom_panel())

    def _build_bottom_panel(self) -> QFrame:
        panel = QFrame()
        panel.setFixedHeight(158)
        panel.setObjectName("BottomPanel")
        panel.setStyleSheet(
            "QFrame#BottomPanel { background: #1e2124; border-top: 2px solid #36393f; }"
        )

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(18)

        # Col 1 – Participante + Tareas
        col1 = QVBoxLayout()
        col1.setSpacing(4)

        lbl_part = QLabel("Participante")
        lbl_part.setStyleSheet("color: #72767d; font-size: 11px; font-weight: bold;")
        self.input_participant = QLineEdit()
        self.input_participant.setPlaceholderText("ID o nombre…")
        self.input_participant.setFixedWidth(190)
        self.input_participant.setStyleSheet(
            "QLineEdit { background: #2f3136; color: #dcddde; border: 1px solid #40444b; "
            "border-radius: 4px; padding: 4px 8px; font-size: 13px; }"
            "QLineEdit:focus { border: 1px solid #7289da; }"
        )
        col1.addWidget(lbl_part)
        col1.addWidget(self.input_participant)

        lbl_task = QLabel("Tarea")
        lbl_task.setStyleSheet("color: #72767d; font-size: 11px; font-weight: bold; margin-top: 3px;")
        col1.addWidget(lbl_task)

        task_lbl = QLabel(f"T1: {TASKS[1]}")
        task_lbl.setStyleSheet(
            "color: #b9ffa0; font-size: 12px; font-weight: bold; "
            "background: #2f3136; border-radius: 4px; padding: 4px 8px;"
        )
        task_lbl.setWordWrap(True)
        col1.addWidget(task_lbl)

        col1.addStretch()
        layout.addLayout(col1)
        layout.addWidget(self._vline())

        # Col 2 – Log / Estado
        col2 = QVBoxLayout()
        col2.setSpacing(4)

        lbl_tr = QLabel("Estado / Log")
        lbl_tr.setStyleSheet("color: #72767d; font-size: 11px; font-weight: bold;")
        col2.addWidget(lbl_tr)

        self.transcription_box = QTextEdit()
        self.transcription_box.setReadOnly(True)
        self.transcription_box.setStyleSheet(
            "QTextEdit { background: #2f3136; color: #b9ffa0; font-family: Consolas, monospace; "
            "font-size: 12px; border: 1px solid #40444b; border-radius: 4px; padding: 4px; }"
        )
        self.transcription_box.setPlaceholderText("Los eventos de sesión aparecerán aquí…")
        col2.addWidget(self.transcription_box, stretch=1)

        layout.addLayout(col2, stretch=1)
        layout.addWidget(self._vline())

        # Col 3 – Métricas + Botones
        col3 = QVBoxLayout()
        col3.setSpacing(6)
        col3.setAlignment(Qt.AlignTop)

        self.lbl_status = QLabel("● EN ESPERA")
        self.lbl_status.setStyleSheet("color: #72767d; font-weight: bold; font-size: 13px;")
        col3.addWidget(self.lbl_status)

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(8)
        self.metric_clicks  = self._make_metric("🖱", "0",       "Clicks")
        self.metric_shots   = self._make_metric("📸", "0",       "Capturas")
        self.metric_emotion = self._make_metric("😐", "neutral", "Emoción")
        for w in [self.metric_clicks, self.metric_shots, self.metric_emotion]:
            metrics_row.addWidget(w)
        col3.addLayout(metrics_row)

        col3.addStretch()

        self.btn_toggle = QPushButton("▶  Iniciar Sesión")
        self.btn_toggle.setFixedHeight(40)
        self.btn_toggle.setMinimumWidth(180)
        self._style_btn_start()
        self.btn_toggle.clicked.connect(self.toggle_session)
        col3.addWidget(self.btn_toggle)

        # Botón Ver Análisis (habilitado después de la primera sesión)
        self.btn_report = QPushButton("📊 Ver Análisis")
        self.btn_report.setFixedHeight(34)
        self.btn_report.setMinimumWidth(180)
        self.btn_report.setEnabled(False)
        self.btn_report.setStyleSheet(
            "QPushButton { background: #4f545c; color: #dcddde; border-radius: 6px; "
            "font-size: 13px; padding: 0 16px; }"
            "QPushButton:enabled:hover { background: #5d6269; }"
            "QPushButton:disabled { color: #555; }"
        )
        self.btn_report.clicked.connect(self._show_report)
        col3.addWidget(self.btn_report)

        layout.addLayout(col3)
        return panel

    @staticmethod
    def _vline() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.VLine)
        f.setStyleSheet("color: #40444b;")
        return f

    @staticmethod
    def _make_metric(icon: str, value: str, label: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet("QFrame { background: #2f3136; border-radius: 6px; }")
        f.setFixedWidth(90)
        v = QVBoxLayout(f)
        v.setSpacing(0)
        v.setContentsMargins(6, 4, 6, 4)

        val_lbl = QLabel(f"{icon} {value}")
        val_lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")
        val_lbl.setAlignment(Qt.AlignCenter)

        sub_lbl = QLabel(label)
        sub_lbl.setStyleSheet("color: #72767d; font-size: 10px;")
        sub_lbl.setAlignment(Qt.AlignCenter)

        v.addWidget(val_lbl)
        v.addWidget(sub_lbl)
        f.value_label = val_lbl
        return f

    # ── Señales → UI ──────────────────────────────────────────────────────────

    def _connect_signals(self):
        self.signals.click_count_updated.connect(
            lambda n: self.metric_clicks.value_label.setText(f"🖱 {n}")
        )
        self.signals.screenshot_count_updated.connect(
            lambda n: self.metric_shots.value_label.setText(f"📸 {n}")
        )
        self.signals.emotion_updated.connect(self._display_emotion)
        self.signals.log_message.connect(self._append_log)

    def _display_emotion(self, emotion: str):
        emoji = EMOTION_EMOJIS.get(emotion, "😐")
        self.metric_emotion.value_label.setText(f"{emoji} {emotion[:7]}")

    def _append_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.transcription_box.append(
            f'<span style="color:#72767d">[{ts}] {msg}</span>'
        )

    # ── Sesión ────────────────────────────────────────────────────────────────

    def toggle_session(self):
        if not self.is_recording:
            self._start_session()
        else:
            self._stop_session()

    def _start_session(self):
        participant = self.input_participant.text().strip() or "anonimo"

        self.db.initialize()
        self.session_uuid = str(uuid.uuid4())
        self.session_id   = self.db.create_session(
            session_uuid=self.session_uuid,
            participant_id=participant,
            experiment_id="facebook_fanpage_v1",
            target_url=TARGET_URL,
            screen_width=1920,
            screen_height=1080,
        )

        session_dir    = Path("data/sessions") / self.session_uuid
        screenshot_dir = session_dir / "screenshots"
        audio_dir      = session_dir / "audio"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        audio_dir.mkdir(parents=True, exist_ok=True)

        self._stopping = False
        self.click_count = 0

        # 1. Mouse
        self.mouse_tracker = MouseTracker(
            session_id=self.session_id,
            on_event_callback=self._on_mouse_event,
            movement_threshold=5,
        )
        self.mouse_tracker.start()

        # 2. Screenshots
        self.screenshot_tracker = EventBasedScreenshotTracker(
            session_id=self.session_id,
            on_screenshot_callback=self._on_screenshot,
            output_dir=screenshot_dir,
            cooldown=0.5,
            format="png",
        )
        self.screenshot_tracker.start()

        # 3. Audio (opcional) — graba toda la sesión como un único archivo
        try:
            self.audio_tracker = AudioTrackerAsync(
                session_id=self.session_id,
                on_segment_callback=self._on_audio_segment,
                output_dir=audio_dir,
                segment_duration=9999,   # sin cortes: se guarda todo al finalizar
                sample_rate=16000,
                channels=1,
            )
            self.audio_tracker.start()
        except Exception as e:
            self.signals.log_message.emit(f"⚠ Micrófono no disponible: {e}")
            self.audio_tracker = None

        # 4. Emociones (opcional)
        try:
            self.emotion_tracker = EmotionTrackerAsync(
                session_id=self.session_id,
                on_emotion_callback=self._on_emotion,
                sample_rate=0.5,
                camera_id=0,
                detector_backend="opencv",
            )
            self.emotion_tracker.start()
        except Exception as e:
            self.signals.log_message.emit(f"⚠ Cámara no disponible: {e}")
            self.emotion_tracker = None

        self.is_recording = True
        self.input_participant.setEnabled(False)
        self._style_btn_stop()
        self.lbl_status.setText("● GRABANDO")
        self.lbl_status.setStyleSheet("color: #f04747; font-weight: bold; font-size: 13px;")
        self.signals.log_message.emit(
            f"Sesión iniciada — Participante: {participant} | ID: {self.session_uuid[:8]}…"
        )

    def _stop_session(self):
        self.is_recording  = False
        self._stopping     = True

        # Detener trackers
        if self.mouse_tracker:
            self.mouse_tracker.stop()
        if self.screenshot_tracker:
            self.screenshot_tracker.stop()
        if self.audio_tracker:
            self.audio_tracker.stop()      # puede disparar último _on_audio_segment
        if self.emotion_tracker:
            self.emotion_tracker.stop()

        # Flush final del buffer de mouse
        self._flush_buffer_safe()

        if self.session_id:
            self.db.end_session(self.session_id)

        self._generate_heatmaps()
        self.db.close()

        # Restaurar UI
        self.input_participant.setEnabled(True)
        self._style_btn_start()
        self.btn_report.setEnabled(True)
        self.lbl_status.setText("● SESIÓN GUARDADA")
        self.lbl_status.setStyleSheet("color: #43b581; font-weight: bold; font-size: 13px;")
        self.signals.log_message.emit(
            f"Sesión guardada → data/sessions/{self.session_uuid}/"
        )

    # ── Callbacks de trackers ─────────────────────────────────────────────────

    def _on_mouse_event(self, event: dict):
        # ── IMPORTANTE: extraer el batch FUERA del lock para evitar deadlock ──
        # (threading.Lock no es reentrante; _flush_buffer_safe también adquiere el lock)
        batch_to_write = None
        with self._buffer_lock:
            self._event_buffer.append((
                event["session_id"],
                event["timestamp"],
                event["event_type"],
                event["x"],
                event["y"],
                event["button"],
                event["pressed"],
                event["scroll_dx"],
                event["scroll_dy"],
                self.current_task_id,
            ))
            if len(self._event_buffer) >= self._BUFFER_SIZE:
                batch_to_write = list(self._event_buffer)
                self._event_buffer.clear()

        # Flush fuera del lock
        if batch_to_write and self.session_id:
            self.db.insert_mouse_events_batch(batch_to_write)

        # Alimentar screenshot tracker
        if self.screenshot_tracker:
            self.screenshot_tracker.on_mouse_event(event)

        # Contar clicks
        if event["event_type"] == "click" and event.get("pressed"):
            self.click_count += 1
            self.signals.click_count_updated.emit(self.click_count)

    def _on_screenshot(self, info: dict):
        self.db.insert_screenshot(
            session_id=info["session_id"],
            timestamp=info["timestamp"],
            file_path=info["file_path"],
            file_size=info["file_size"],
            width=info["width"],
            height=info["height"],
            format=info["format"],
            trigger_event_type=info.get("trigger_event_type"),
            trigger_x=info.get("trigger_x"),
            trigger_y=info.get("trigger_y"),
            task_id=self.current_task_id,
        )
        count = self.db.get_screenshot_count(self.session_id)
        self.signals.screenshot_count_updated.emit(count)

    def _on_audio_segment(self, segment: dict):
        self.db.insert_audio_segment(
            session_id=segment["session_id"],
            start_timestamp=segment["start_timestamp"],
            end_timestamp=segment["end_timestamp"],
            duration=segment["duration"],
            file_path=segment["file_path"],
            sample_rate=segment["sample_rate"],
            channels=segment["channels"],
            file_size=segment["file_size"],
            task_id=self.current_task_id,
        )
        dur_min = segment["duration"] / 60
        self.signals.log_message.emit(
            f"Audio guardado → {segment['file_path']}  ({dur_min:.1f} min)"
        )

    def _on_emotion(self, data: dict):
        self.db.insert_emotion_event(
            session_id=data["session_id"],
            timestamp=data["timestamp"],
            angry=data["angry"],
            disgust=data["disgust"],
            fear=data["fear"],
            happy=data["happy"],
            sad=data["sad"],
            surprise=data["surprise"],
            neutral=data["neutral"],
            dominant_emotion=data["dominant_emotion"],
            face_confidence=data.get("face_confidence"),
            age=data.get("age"),
            gender=data.get("gender"),
            task_id=self.current_task_id,
        )
        self.signals.emotion_updated.emit(data["dominant_emotion"])

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _inject_modal_killer(self, ok: bool):
        """Inyecta JS que cierra automáticamente modales/diálogos de Facebook
        (ej: 'Recordar contraseña') y oculta widgets nativos de Qt."""
        if not ok:
            return

        # ── 1. Ocultar widgets hijos nativos que Qt pone sobre el browser ────
        self._hide_native_overlays()

        js = """
        (function() {
            // Cerrar modales de Facebook
            function killModals() {
                // Buscar botones "Ahora no" / "Not Now"
                var buttons = document.querySelectorAll('[role="button"], button, a, span');
                for (var i = 0; i < buttons.length; i++) {
                    var text = (buttons[i].textContent || '').trim();
                    if (text === 'Ahora no' || text === 'Not Now' || text === 'Not now' ||
                        text === 'Dismiss' || text === 'Descartar') {
                        buttons[i].click();
                        return;
                    }
                }
                // Cerrar diálogos via aria-label
                var closers = document.querySelectorAll(
                    '[aria-label="Cerrar"], [aria-label="Close"], [aria-label="Dismiss"]'
                );
                for (var j = 0; j < closers.length; j++) {
                    // Solo si el diálogo está visible
                    var parent = closers[j].closest('[role="dialog"]');
                    if (parent) {
                        closers[j].click();
                        return;
                    }
                }
                // Remover overlays/backdrops que oscurecen la página
                var overlays = document.querySelectorAll(
                    '[data-testid="dialog_overlay"], .__fb-dark-mode-compatible-background-overlay'
                );
                overlays.forEach(function(el) { el.remove(); });
            }
            // Ejecutar cada 1.5 segundos durante 60 segundos
            var count = 0;
            var iv = setInterval(function() {
                killModals();
                count++;
                if (count > 40) clearInterval(iv);
            }, 1500);
            killModals();
        })();
        """
        self.browser.page().runJavaScript(js)

    def _hide_native_overlays(self):
        """Inicia un timer periódico que busca y oculta widgets nativos de Qt
        que aparecen sobre el browser (como el botón 'Cerrar')."""
        from PySide6.QtCore import QTimer
        self._overlay_timer = QTimer(self)
        self._overlay_timer.timeout.connect(self._scan_and_hide_overlays)
        self._overlay_timer.start(500)  # Cada 500ms

    def _scan_and_hide_overlays(self):
        """Busca recursivamente en TODA la jerarquía del browser y elimina
        cualquier widget nativo de overlay (botones, labels, frames)."""
        from PySide6.QtWidgets import QWidget as QW, QPushButton as QPB
        try:
            for child in self.browser.findChildren(QW):
                class_name = child.metaObject().className()

                # Preservar widgets esenciales del render
                if any(x in class_name for x in [
                    "RenderWidget", "WebEngineView", "QWebEngine",
                    "FocusProxy", "QtWebEngineCore",
                ]):
                    continue

                # Si es un QPushButton → eliminar siempre (no debería haber botones en el browser)
                if isinstance(child, QPB):
                    print(f"[DEBUG overlay] Eliminando QPushButton: '{child.text()}' "
                          f"class={class_name} parent={child.parent().metaObject().className() if child.parent() else 'None'}")
                    child.hide()
                    child.setParent(None)
                    child.deleteLater()
                    continue

                # Buscar widgets con texto sospechoso
                try:
                    if hasattr(child, 'text') and callable(child.text):
                        text = child.text()
                        if text in ("Cerrar", "Close", "Dismiss"):
                            print(f"[DEBUG overlay] Eliminando widget con texto '{text}': "
                                  f"class={class_name}")
                            child.hide()
                            child.setParent(None)
                            child.deleteLater()
                            continue
                except Exception:
                    pass

        except Exception as e:
            print(f"[DEBUG overlay] Error: {e}")

    def _flush_buffer_safe(self):
        """Flush seguro del buffer (llamar SOLO desde fuera de _on_mouse_event)."""
        with self._buffer_lock:
            if self._event_buffer and self.session_id:
                self.db.insert_mouse_events_batch(self._event_buffer)
                self._event_buffer.clear()

    def _generate_heatmaps(self):
        events = self.db.get_mouse_events(self.session_id)
        if not events:
            return
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = Path("output")
        out.mkdir(exist_ok=True)
        heatmap_file = out / f"heatmap_{ts}.png"
        gen = HeatmapGenerator(screen_width=1920, screen_height=1080)
        gen.generate_from_events(events, heatmap_file)
        self._last_heatmap_path = heatmap_file
        self.signals.log_message.emit(f"Heatmap → {heatmap_file}")

    def _show_report(self):
        if self.session_id is None:
            return
        # Reabrir DB en modo lectura para el reporte
        report_db = Database()
        report_db.initialize()
        dlg = ReportDialog(
            self.session_id, self.session_uuid, report_db,
            heatmap_path=self._last_heatmap_path,
            parent=self,
        )
        dlg.exec()
        report_db.close()

    def _style_btn_start(self):
        self.btn_toggle.setText("▶  Iniciar Sesión")
        self.btn_toggle.setStyleSheet(
            "QPushButton { background: #43b581; color: white; font-weight: bold; "
            "font-size: 14px; border-radius: 6px; padding: 0 20px; }"
            "QPushButton:hover { background: #3ca374; }"
        )

    def _style_btn_stop(self):
        self.btn_toggle.setText("⏹  Finalizar Sesión")
        self.btn_toggle.setStyleSheet(
            "QPushButton { background: #f04747; color: white; font-weight: bold; "
            "font-size: 14px; border-radius: 6px; padding: 0 20px; }"
            "QPushButton:hover { background: #d84040; }"
        )

    def closeEvent(self, event):
        if self.is_recording:
            self._stop_session()
        event.accept()


# ── Punto de entrada ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Deshabilitar features de Chromium que generan overlays/popups nativos
    # (el botón "Cerrar" es un widget nativo que Qt pone sobre la página)
    sys.argv += [
        "--disable-features=Accessibility,TranslateUI",
        "--force-renderer-accessibility=false",
        "--disable-notifications",
        "--disable-infobars",
        "--disable-save-password-bubble",
        "--disable-translate",
        "--disable-popup-blocking",
        "--no-first-run",
        "--disable-prompt-on-repost",
    ]

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))

    win = HCILoggerWindow()
    win.show()

    sys.exit(app.exec())
