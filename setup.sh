#!/bin/bash

echo "============================================================"
echo "  HCI Logger - Script de Instalación"
echo "============================================================"
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 no está instalado"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Python detectado: $(python3 --version)"

# Crear entorno virtual
echo ""
echo "📦 Creando entorno virtual..."
if [ -d "venv" ]; then
    echo "  ⚠️  venv/ ya existe, omitiendo..."
else
    python3 -m venv venv
    echo "  ✓ Entorno virtual creado"
fi

# Activar entorno virtual
echo ""
echo "🔄 Activando entorno virtual..."
source venv/bin/activate

# Actualizar pip
echo ""
echo "⬆️  Actualizando pip..."
pip install --upgrade pip --quiet

# Instalar dependencias
echo ""
echo "📥 Instalando dependencias..."
echo "   Esto puede tomar unos minutos..."
pip install -r requirements.txt --quiet

if [ $? -eq 0 ]; then
    echo "  ✓ Dependencias instaladas correctamente"
else
    echo "  ❌ Error instalando dependencias"
    exit 1
fi

# Verificar instalación
echo ""
echo "🔍 Verificando instalación..."
python3 << EOF
try:
    import pynput
    import numpy
    import matplotlib
    import scipy
    print("  ✓ Todas las librerías importadas correctamente")
except ImportError as e:
    print(f"  ❌ Error: {e}")
    exit(1)
EOF

# Crear directorios necesarios
echo ""
echo "📁 Creando directorios de datos..."
mkdir -p data logs output
echo "  ✓ Directorios creados"

echo ""
echo "============================================================"
echo "✅ Instalación completada!"
echo "============================================================"
echo ""
echo "Para usar el proyecto:"
echo ""
echo "  1. Activar entorno virtual:"
echo "     source venv/bin/activate"
echo ""
echo "  2. Ejecutar demo:"
echo "     python demo_tracking.py"
echo ""
echo "  3. Ver README para más información:"
echo "     cat README.md"
echo ""
echo "============================================================"
