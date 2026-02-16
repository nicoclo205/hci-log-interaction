# 🚀 Guía de Inicio Rápido

## Instalación en 3 pasos

### 1️⃣ Ejecutar script de instalación
```bash
./setup.sh
```

### 2️⃣ Activar entorno virtual
```bash
source venv/bin/activate
```

### 3️⃣ Ejecutar demo
```bash
python demo_tracking.py 30
```

## ¿Qué hace el demo?

1. **Inicia tracking de mouse** durante 30 segundos
2. **Captura** todos tus movimientos y clicks
3. **Almacena** eventos en SQLite
4. **Genera** 3 heatmaps automáticamente:
   - Heatmap general (movimientos + clicks)
   - Heatmap de clicks
   - Comparación lado a lado

## Durante el tracking:

✅ **Mueve el mouse** por toda la pantalla
✅ **Haz clicks** en diferentes lugares
✅ **Usa scroll** (opcional)
✅ **Presiona Ctrl+C** para detener antes

## Resultados:

Después del tracking, encontrarás:

📂 `data/hci_logger.db` - Base de datos SQLite
📂 `output/heatmap_*.png` - Heatmap general
📂 `output/heatmap_clicks_*.png` - Heatmap de clicks
📂 `output/comparison_*.png` - Comparación

## Ejemplos de uso:

```bash
# 15 segundos
python demo_tracking.py 15

# 1 minuto
python demo_tracking.py 60

# 5 minutos
python demo_tracking.py 300
```

## Consultar datos:

```bash
# Conectar a la base de datos
sqlite3 data/hci_logger.db

# Ver sesiones
SELECT * FROM sessions;

# Contar eventos
SELECT COUNT(*) FROM mouse_events;

# Salir
.quit
```

## Próximos pasos:

1. Ver **README.md** para documentación completa
2. Explorar código en **hci_logger/**
3. Personalizar parámetros en **demo_tracking.py**
4. Agregar nuevos trackers (eye, emotion, audio)

---

**¿Problemas?** Revisa la sección "Troubleshooting" en README.md
