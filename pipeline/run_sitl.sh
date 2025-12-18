#!/bin/bash
# Helper script to launch ArduCopter SITL from WSL
# Versión Simplificada y Robusta: Salida directa a consola

# 1. Obtener directorio donde reside este script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 2. Configurar rutas
SITL_DIR="$PROJECT_ROOT/ardupilot"
BINARY="$SITL_DIR/build/sitl/bin/arducopter"

# 3. Parametros
HOME_LOC="42.229695,-1.235085,500,147"
PARAMS="--model x --home=$HOME_LOC --serial0=tcp:0.0.0.0:5760"

# 4. Validaciones
if [ ! -f "$BINARY" ]; then
    echo "[ERROR] Binario SITL no encontrado en: $BINARY"
    exit 1
fi

echo "=========================================="
echo " Lanzando ArduPilot SITL (WSL)"
echo " Salida directa a consola (Debug Mode)"
echo "=========================================="

cd "$SITL_DIR" || exit 1

# 5. Ejecucion Directa (Sin pipes que puedan romperse)
"$BINARY" $PARAMS
