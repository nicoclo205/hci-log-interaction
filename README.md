# HCI Logger - Sistema de Tracking de Interacciones

Sistema de seguimiento de interacciones humano-computador (HCI) para estudios de usabilidad. Captura eventos de mouse, clicks, y genera heatmaps de actividad.

## 🎯 Características

### Prototipo Actual (v0.4) 🔥
- ✅ **Mouse Tracking**: Captura movimientos, clicks y scroll
- ✅ **Screenshot Capture**: Capturas periódicas de pantalla (mss - 10x más rápido)
- ✅ **Audio Recording**: Grabación de audio en segmentos (sounddevice)
- ✅ **Emotion Detection**: Análisis facial de 7 emociones + edad + género (DeepFace)
- ✅ **Almacenamiento SQLite**: Base de datos eficiente con modo WAL
- ✅ **Generación de Heatmaps**: Visualizaciones de actividad
- ✅ **Batch Processing**: Escritura optimizada en lotes
- ✅ **Multi-tracker**: Sistema que coordina 4 trackers simultáneos

### Roadmap Futuro
- 🔲 Eye Tracking (MediaPipe) - Próximo
- 🔲 Dashboard Web (FastAPI)
- 🔲 Real-time Analytics
- 🔲 Emotion Timeline Visualization

## 📁 Estructura del Proyecto

```
hci-log-interaction/
├── hci_logger/              # Paquete principal
│   ├── trackers/           # Módulos de tracking
│   │   └── mouse_tracker.py
│   ├── storage/            # Base de datos
│   │   ├── database.py
│   │   └── schema.sql
│   └── processing/         # Procesamiento de datos
│       └── heatmap.py
├── demo_tracking.py        # Script de prueba
├── requirements.txt        # Dependencias
└── README.md              # Este archivo
```

## 🚀 Instalación

### 1. Clonar/Navegar al directorio
```bash
cd /home/maosuarez/Programas/hci-log-interaction
```

### 2. Crear entorno virtual
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows
```

### 3. Instalar dependencias
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 💻 Uso

### Demo Básico: Solo Mouse Tracking
```bash
python demo_tracking.py [duración]

# Ejemplos:
python demo_tracking.py     # 30 segundos (default)
python demo_tracking.py 60  # 60 segundos
```

### Demo Completo: Mouse + Screenshots 🆕
```bash
python demo_with_screenshots.py [duración] [intervalo_screenshots]

# Ejemplos:
python demo_with_screenshots.py           # 30s, screenshot cada 5s
python demo_with_screenshots.py 60 3      # 60s, screenshot cada 3s
python demo_with_screenshots.py 120 10    # 2min, screenshot cada 10s
```

### Demo Full: Mouse + Screenshots + Audio 🔥
```bash
python demo_complete.py [duración] [screenshot_interval] [audio_segment_duration]

# Ejemplos:
python demo_complete.py                   # 60s, screenshot cada 5s, audio cada 30s
python demo_complete.py 120 5 60          # 2min, screenshot cada 5s, audio cada 60s
python demo_complete.py 300 10 120        # 5min, screenshot cada 10s, audio cada 2min
```

### Demo DEFINITIVO: TODOS los Trackers 🚀😊
```bash
python demo_full.py [duración]

# Ejemplos:
python demo_full.py          # 2 minutos con TODOS los trackers
python demo_full.py 300      # 5 minutos de tracking completo

# Incluye:
# 🖱️  Mouse tracking
# 📸 Screenshots cada 10s
# 🎤 Audio en segmentos de 60s
# 😊 Emotion detection cada 0.5s (7 emociones + edad + género)
```

**Notas Importantes**:
- Primera ejecución descarga modelos de DeepFace (~100MB)
- Requiere permisos de cámara y micrófono
- Si falla audio o emociones, continúa con los demás trackers

### Durante el tracking:
- Mueve el mouse por toda la pantalla
- Haz clicks en diferentes lugares
- Usa scroll
- Presiona **Ctrl+C** para detener antes de tiempo

### Resultados:
El script generará automáticamente:
- Base de datos SQLite en `data/hci_logger.db`
- 3 heatmaps en el directorio `output/`:
  - `heatmap_YYYYMMDD_HHMMSS.png` - Todos los eventos
  - `heatmap_clicks_YYYYMMDD_HHMMSS.png` - Solo clicks
  - `comparison_YYYYMMDD_HHMMSS.png` - Comparación lado a lado

## 📊 Ejemplo de Output

```
============================================================
🖱️  HCI LOGGER - DEMO DE TRACKING DE MOUSE
============================================================

📊 Inicializando base de datos...
✓ Database initialized at data/hci_logger.db
✓ Sesión creada: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  ID: 1

🖱️  Mouse tracker starting...
✓ Mouse tracker started
⏱️  Tracking iniciado por 30 segundos...
   Mueve el mouse y haz clicks!
   Presiona Ctrl+C para detener antes

  [████████████████████████████████████████] 30/30s | Eventos: 1247

✓ Mouse tracker stopped (1247 events captured)

============================================================
📈 ESTADÍSTICAS DE LA SESIÓN
============================================================
  Total de eventos: 1247
  - Movimientos: 1198
  - Clicks: 45
  - Scrolls: 4

🎨 Generando heatmaps...
✓ Heatmap generado: output/heatmap_20260216_143052.png
✓ Click heatmap generado: output/heatmap_clicks_20260216_143052.png
✓ Comparación generada: output/comparison_20260216_143052.png

✓ Heatmaps generados en el directorio 'output/':
  - heatmap_20260216_143052.png
  - heatmap_clicks_20260216_143052.png
  - comparison_20260216_143052.png

============================================================
✅ Demo completada exitosamente!
============================================================
```

## 🗃️ Base de Datos

### Schema SQLite

**Tabla `sessions`**:
- Metadata de cada sesión de tracking
- UUID único, timestamps, información del participante

**Tabla `mouse_events`**:
- Todos los eventos de mouse capturados
- Tipos: `move`, `click`, `scroll`
- Coordenadas X/Y, timestamp, detalles del evento

### Consultas útiles

```bash
# Conectar a la base de datos
sqlite3 data/hci_logger.db

# Ver sesiones
SELECT * FROM sessions;

# Contar eventos por tipo
SELECT event_type, COUNT(*) as count
FROM mouse_events
WHERE session_id = 1
GROUP BY event_type;

# Ver últimos clicks
SELECT timestamp, x, y, button
FROM mouse_events
WHERE event_type = 'click' AND pressed = 1
ORDER BY timestamp DESC
LIMIT 10;
```

## 🎨 Heatmaps

### Colores
- **Azul**: Baja actividad
- **Verde**: Actividad media
- **Amarillo**: Alta actividad
- **Rojo**: Actividad muy alta

### Tipos generados

1. **Heatmap general**: Movimientos + clicks combinados
2. **Heatmap de clicks**: Solo muestra dónde se hizo click
3. **Comparación**: Lado a lado (movimientos vs clicks)

### Personalización

Editar parámetros en `hci_logger/processing/heatmap.py`:
- `blur_radius`: Radio del gaussian blur (default: 20)
- `screen_width/height`: Resolución de pantalla
- Colormaps personalizados

## 🔧 Desarrollo

### Estructura de código

```python
# Crear sesión
db = Database()
db.initialize()
session_id = db.create_session(session_uuid="...")

# Iniciar tracker
tracker = MouseTracker(
    session_id=session_id,
    on_event_callback=callback_function
)
tracker.start()

# ... tiempo de tracking ...

# Detener y generar heatmap
tracker.stop()
events = db.get_mouse_events(session_id)
generator = HeatmapGenerator()
generator.generate_from_events(events, output_path)
```

### Agregar nuevos trackers

1. Crear clase que herede de patrón similar a `MouseTracker`
2. Implementar callbacks de eventos
3. Definir schema en `schema.sql`
4. Añadir métodos de inserción en `database.py`

## 📝 Configuración

### Ajustar threshold de movimiento

En `demo_tracking.py`:
```python
self.tracker = MouseTracker(
    session_id=self.session_id,
    on_event_callback=self._on_mouse_event,
    movement_threshold=5  # Cambiar este valor (pixels)
)
```

Valores más altos = menos eventos capturados (mejor performance)

### Ajustar buffer size

```python
self.buffer_size = 50  # Cambiar para flush más/menos frecuente
```

## 🐛 Troubleshooting

### Error: "ModuleNotFoundError: No module named 'pynput'"
```bash
pip install -r requirements.txt
```

### Error de permisos en Linux
En algunos sistemas, pynput requiere permisos adicionales:
```bash
sudo usermod -a -G input $USER
# Luego cerrar sesión y volver a entrar
```

### Heatmap vacío
- Asegúrate de mover el mouse durante el tracking
- Verifica que los eventos se capturaron: `sqlite3 data/hci_logger.db "SELECT COUNT(*) FROM mouse_events;"`

## 📚 Referencias

- **pynput**: https://pynput.readthedocs.io/
- **matplotlib**: https://matplotlib.org/
- **scipy**: https://scipy.org/

## 🤝 Contribuir

Este es un proyecto académico. Para contribuir:
1. Fork el proyecto
2. Crea una rama (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Añadir nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crea un Pull Request

## 📄 Licencia

MIT License - Ver archivo LICENSE para detalles

## 👤 Autor

Proyecto de investigación HCI

---

**Versión**: 0.1.0 (Prototipo)
**Última actualización**: Febrero 2026
