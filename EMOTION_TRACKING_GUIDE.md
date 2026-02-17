# 😊 Emotion Tracking en HCI Logger

## ¿Qué es Emotion Tracking?

El **Emotion Tracker** utiliza análisis facial con **DeepFace** para detectar emociones del usuario en tiempo real mientras interactúa con la aplicación.

## 🎯 Propósito en Estudios HCI

### Datos Capturados

Para cada análisis facial (2 veces por segundo), el sistema detecta:

**7 Emociones Básicas:**
- 😊 **Happy** (Felicidad) - Usuario satisfecho/contento
- 😢 **Sad** (Tristeza) - Usuario decepcionado
- 😠 **Angry** (Enojo) - Usuario frustrado
- 😨 **Fear** (Miedo) - Usuario preocupado/inseguro
- 😲 **Surprise** (Sorpresa) - Usuario impactado/sorprendido
- 🤢 **Disgust** (Disgusto) - Usuario rechaza algo
- 😐 **Neutral** (Neutral) - Sin emoción dominante

**Metadata Adicional:**
- **Edad estimada** del participante
- **Género** detectado
- **Confianza** de detección facial (0-1)
- **Emoción dominante** (la más fuerte)

## 💡 Casos de Uso en UX Research

### 1. Detectar Pain Points
```
Timeline:
00:15 - Usuario hace click en botón X → 😐 Neutral
00:16 - Nada sucede (bug) → 😕 Confusión
00:17 - Intenta de nuevo → 😠 Frustración
00:18 - Click repetitivo (5 veces) → 😡 Enojo

✅ INSIGHT: Botón X no funciona → Causa frustración
```

### 2. Validar Experiencias Positivas
```
00:30 - Usuario descubre feature nuevo → 😲 Sorpresa
00:31 - Prueba el feature → 😊 Felicidad
00:35 - Sigue usándolo → 😊 Satisfacción

✅ INSIGHT: Feature bien recibido → Mantener en producto
```

### 3. Correlación Multimodal
```
Momento X:
- 🖱️  Click repetitivo (8 veces en 2s)
- 📸 Screenshot muestra formulario
- 🎤 Audio: "¿Dónde está el botón de enviar?"
- 😠 Emoción: Frustración creciente

✅ INSIGHT: Botón de enviar no es visible
```

## 🔬 Cómo Funciona Técnicamente

### Pipeline de Detección

```
Cámara → Captura Frame → DeepFace Analysis → Extracción de Emociones → Base de Datos
   ↓           ↓               ↓                    ↓                      ↓
 30 FPS    Cada 0.5s      7 emociones         Emoción dominante      SQLite
                          + edad + género
```

### Configuración

```python
EmotionTrackerAsync(
    session_id=1,
    on_emotion_callback=callback,
    sample_rate=2.0,      # 2 análisis por segundo
    camera_id=0,          # Cámara por defecto
    detector_backend='opencv'  # Detector facial
)
```

### Frecuencia de Análisis

- **2 Hz** (2 veces por segundo) - Balance perfecto entre:
  - Capturar cambios emocionales rápidos
  - No saturar el sistema
  - No generar datos excesivos

## 📊 Análisis de Datos de Emociones

### Queries Útiles

```sql
-- Emoción dominante por sesión
SELECT dominant_emotion, COUNT(*) as count
FROM emotion_events
WHERE session_id = 1
GROUP BY dominant_emotion
ORDER BY count DESC;

-- Momentos de frustración
SELECT timestamp, dominant_emotion
FROM emotion_events
WHERE session_id = 1
  AND (angry > 0.5 OR disgust > 0.3)
ORDER BY timestamp;

-- Correlacionar emociones con clicks
SELECT
    e.timestamp,
    e.dominant_emotion,
    e.angry,
    m.event_type,
    m.x, m.y
FROM emotion_events e
LEFT JOIN mouse_events m
    ON e.session_id = m.session_id
    AND ABS(e.timestamp - m.timestamp) < 1.0
WHERE e.session_id = 1
ORDER BY e.timestamp;
```

### Visualizaciones Posibles

1. **Timeline de Emociones**
   - Gráfico de línea mostrando evolución emocional
   - Identificar picos de frustración/satisfacción

2. **Heatmap Emocional**
   - Superponer emoción dominante en cada screenshot
   - Ver qué UI elements causan qué emociones

3. **Distribución de Emociones**
   - Gráfico de pastel mostrando % de cada emoción
   - Comparar entre diferentes versiones de UI

## ⚠️ Consideraciones Importantes

### Privacidad
- ❌ **NO se guardan imágenes faciales**
- ✅ Solo se guardan valores numéricos de emociones
- ✅ Metadata anónima (edad/género son opcionales)

### Precisión
- La detección funciona mejor con:
  - Buena iluminación
  - Rostro frontal a la cámara
  - Sin obstrucciones (lentes oscuros, manos)
- Puede fallar con:
  - Iluminación muy baja
  - Perfil lateral
  - Múltiples personas en frame

### Ética
- Siempre obtener **consentimiento informado**
- Explicar que se detectarán emociones
- Dar opción de opt-out
- No usar para decisiones automatizadas sensibles

## 🎯 Ejemplo de Flujo Completo

### Durante el Test (2 minutos)

```
Participante: "Voy a probar esta app..."

[0:00] 😐 Neutral - Navegando la UI inicial
[0:15] 😊 Happy - Descubre feature interesante
[0:30] 😲 Surprise - Feature hace algo inesperado
[0:45] 😠 Angry - Botón no responde (click x8)
[1:00] 😢 Sad - Se rinde con ese feature
[1:15] 😐 Neutral - Intenta otra cosa
[1:30] 😊 Happy - Nueva feature funciona bien
[1:45] 😊 Happy - Completa tarea exitosamente
```

### Análisis Post-Test

```sql
-- Resultados de la sesión
Emociones Detectadas:
  😊 Happy:    40% (48 eventos)
  😐 Neutral:  35% (42 eventos)
  😠 Angry:    15% (18 eventos)  ← ⚠️ REVISAR
  😲 Surprise: 7%  (8 eventos)
  😢 Sad:      3%  (4 eventos)

Pain Point Identificado:
  Timestamp: 0:45
  Emoción: 😠 Angry (angry=0.8)
  Contexto: Click repetitivo en botón X
  Audio: "¿Por qué no funciona?"
  Screenshot: Muestra botón deshabilitado sin indicación visual

  ✅ ACCIÓN: Agregar estado visual claro cuando botón está disabled
```

## 🚀 Demo Full - ¿Qué Hace?

Al ejecutar `python demo_full.py`:

1. **Detecta emociones** cada 0.5s
2. **Captura screenshots** en clicks/scrolls
3. **Graba audio** del participante
4. **Tracking de mouse** completo
5. **Guarda todo** en DB con timestamps
6. **Genera overlays** mostrando actividad visual

**Resultado:** Análisis multimodal completo que combina:
- Qué hizo (mouse, clicks)
- Qué dijo (audio)
- Qué sintió (emociones)
- Qué vio (screenshots)

## 📚 Referencias

- **DeepFace**: https://github.com/serengil/deepface
- **Emotion Recognition**: Basado en modelos de Facial Action Coding System (FACS)
- **HCI Research**: Métodos estándar de usability testing con análisis afectivo

---

**Versión:** 2.0
**Última actualización:** 2026-02-16
