#!/bin/bash
# Helper script to launch ArduCopter SITL from WSL
# Versión Simplificada y Robusta: Salida directa a consola

# 1. Obtener directorio donde reside este script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 2. Configurar rutas
SITL_DIR="$PROJECT_ROOT/ardupilot"
DEFAULT_BINARY="$SITL_DIR/build/sitl/bin/arducopter"
BINARY="${ARDUPILOT_SITL_BIN:-$DEFAULT_BINARY}"
ALLOW_HOME_FALLBACK_RAW="${PORCE_SITL_ALLOW_HOME_FALLBACK:-0}"
ALLOW_HOME_FALLBACK="$(printf '%s' "$ALLOW_HOME_FALLBACK_RAW" | tr '[:upper:]' '[:lower:]')"
if [ "$ALLOW_HOME_FALLBACK" = "1" ] || [ "$ALLOW_HOME_FALLBACK" = "true" ] || [ "$ALLOW_HOME_FALLBACK" = "yes" ] || [ "$ALLOW_HOME_FALLBACK" = "on" ]; then
    ALLOW_HOME_FALLBACK="1"
else
    ALLOW_HOME_FALLBACK="0"
fi

# Fallback to a WSL-home clone if the repo submodule is not initialized/built.
if [ "$ALLOW_HOME_FALLBACK" = "1" ] && [ ! -f "$BINARY" ] && [ -f "$HOME/ardupilot/build/sitl/bin/arducopter" ]; then
    BINARY="$HOME/ardupilot/build/sitl/bin/arducopter"
    SITL_DIR="$HOME/ardupilot"
fi

# 3. Parametros
HOME_LOC="${SITL_HOME:-42.229695,-1.235085,500,147}"
MODEL="${SITL_MODEL:-x}"
SERIAL0="${SITL_SERIAL0:-tcp:127.0.0.1:5760}"
WIPE="${SITL_WIPE:-1}"

# Load ArduPilot defaults. For Copter, we want a base file + an optional frame override.
# In ArduPilot, these defaults are typically passed as a comma-separated list.
DEFAULTS_FILES=()
BASE_DEFAULT="$SITL_DIR/Tools/autotest/default_params/copter.parm"
if [ -f "$BASE_DEFAULT" ]; then
  DEFAULTS_FILES+=("$BASE_DEFAULT")
fi

# Frame override for X quad. (This file can be a tiny override; it is not a complete defaults set.)
if [ "$MODEL" = "x" ] || [ "$MODEL" = "X" ]; then
  FRAME_OVERRIDE="$SITL_DIR/Tools/autotest/default_params/copter-X.parm"
  if [ -f "$FRAME_OVERRIDE" ]; then
    DEFAULTS_FILES+=("$FRAME_OVERRIDE")
  fi
fi

DEFAULTS_ARG=""
if [ ${#DEFAULTS_FILES[@]} -gt 0 ]; then
  DEFAULTS_JOINED="$(IFS=,; echo "${DEFAULTS_FILES[*]}")"
  DEFAULTS_ARG="--defaults $DEFAULTS_JOINED"
fi

WIPE_ARG=""
if [ "$WIPE" = "1" ] || [ "$WIPE" = "true" ] || [ "$WIPE" = "True" ]; then
  WIPE_ARG="--wipe"
fi

PARAMS="$WIPE_ARG $DEFAULTS_ARG --model $MODEL --home=$HOME_LOC --serial0=$SERIAL0"

# 4. Validaciones
if [ ! -f "$BINARY" ]; then
    echo "[ERROR] Binario SITL no encontrado en: $BINARY"
    echo "[HINT] Opcion 1 (reproducible): inicializa el submodulo y compila SITL en WSL bajo $PROJECT_ROOT/ardupilot"
    echo "[HINT] Opcion 2 (override): export ARDUPILOT_SITL_BIN=/path/to/arducopter"
    echo "[HINT] Opcion 3 (fallback no reproducible): export PORCE_SITL_ALLOW_HOME_FALLBACK=1"
    exit 1
fi

echo "=========================================="
echo " Lanzando ArduPilot SITL (WSL)"
echo " Salida directa a consola (Debug Mode)"
echo "=========================================="
echo " Model: $MODEL"
echo " Serial0: $SERIAL0"
echo " Wipe: $WIPE"
echo " Home fallback: $ALLOW_HOME_FALLBACK"
if [ ${#DEFAULTS_FILES[@]} -gt 0 ]; then
  echo " Defaults: $(IFS=,; echo "${DEFAULTS_FILES[*]}")"
else
  echo " Defaults: (none)"
fi

cd "$SITL_DIR" || exit 1

# 5. Ejecucion Directa (Sin pipes que puedan romperse)
"$BINARY" $PARAMS
