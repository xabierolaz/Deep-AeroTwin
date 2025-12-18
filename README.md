# PORCE: Autonomous Drone Pipeline (SITL + Vision)
**Version:** STABLE V1 (16 Dec 2025)
**Status:** WORKING (Takeoff & Navigation Loop Verified)

## 1. Arquitectura del Sistema (Actual)

El sistema opera en un entorno híbrido **Windows + WSL (Windows Subsystem for Linux)**.

### Componentes Principales

1.  **SITL (ArduCopter):** 
    *   **Entorno:** WSL (Ubuntu/Linux).
    *   **Ejecución:** `pipeline/run_sitl.sh`.
    *   **Función:** Simula la física del dron y el piloto automático.
    *   **Red:** Escucha en `0.0.0.0:5760` (TCP) dentro de WSL. Accesible desde Windows vía `localhost:5760`.
    *   **Parametros Críticos:**
        *   Home: `42.229695, -1.235085, 500m (MSL), 147° (Heading)`.

2.  **FLIGHT CONTROLLER (The Brain):**
    *   **Entorno:** Windows (Python Nativo).
    *   **Ejecución:** `pipeline/flight_controller.py`.
    *   **Función:** "Cerebro" de alto nivel. Se conecta a SITL vía MAVLink, carga la misión y decide maniobras (incluyendo evasión).
    *   **API:** Expone telemetría en HTTP `localhost:8080`.

3.  **LAUNCHER:**
    *   **Script:** `launch.bat`.
    *   **Función:** Orquestador. Inicia SITL (llamando a WSL), Logs, Vision y Cerebro en ventanas separadas. Maneja la limpieza de procesos.

---

## 2. Mapa de Puertos y Comunicación

| Puerto | Protocolo | Origen | Destino | Descripción |
| :--- | :--- | :--- | :--- | :--- |
| **5760** | TCP | Windows (Brain) | WSL (SITL) | Conexión principal MAVLink. SITL actúa como Server (`-serial0`), Brain como Cliente. |
| **8080** | HTTP | Windows (Vision) | Windows (Brain) | API REST unificada para obtener estado del dron (lat, lon, alt). |
| **9005** | UDP | WSL (SITL) | Windows (Vision) | Simulación de cámara (Irlock/Gazebo bridge si aplica). |

---

## 3. Configuración de Misión y Alturas (CORREGIDO)

Para garantizar un despegue estable, se han alineado todas las referencias de altitud.

*   **Ubicación:** Ejea de los Caballeros.
*   **Elevación del Terreno (Home):** **500 metros** (MSL).
*   **Altura de Vuelo Misión:** **523 metros** (MSL).
*   **Altura Relativa (AGL):** 23 metros.

### Archivos Críticos:
*   `pipeline/run_sitl.sh`: Define el punto de origen del simulador.
    *   `HOME_LOC="42.229695,-1.235085,500,147"`
*   `pipeline/ejea_default.waypoints`: Define la ruta de vuelo.
    *   WP0 (Home): 500.00m
    *   WP1 (Takeoff Target): 523.00m
    *   WP2..N: 523.00m

---

## 4. Histórico de Correcciones (Lo que estaba mal)

Esta sección documenta los errores corregidos para llegar a la versión STABLE V1.

### A. Inconsistencia de Altitudes (Causa de "Crash" o "No Takeoff")
*   **Antes:**
    *   SITL Home estaba a 503m.
    *   Waypoints empezaban a 518m (15m AGL).
    *   Tolerancia de despegue era 1m.
*   **Problema:** A veces el dron iniciaba en 503m pero la misión pedía bajar o subir de forma inconsistente, o el terreno de Google Maps/Cesium no coincidía.
*   **Solución Actual:** Se estandarizó Home a **500m** y Vuelo a **523m** en todos los archivos (`.sh` y `.waypoints`).

### B. Rutas de Archivos (Windows vs WSL)
*   **Problema:** Los scripts de Python fallaban al cargar `ejea_default.waypoints` porque se ejecutaban desde la raíz del proyecto y el archivo estaba en `pipeline/`.
*   **Solución:** Los scripts ahora asumen ejecución dentro del directorio `pipeline/` o gestionan rutas relativas. `launch.bat` hace `cd pipeline` explícitamente antes de lanzar Python.

### C. Conectividad WSL
*   **Problema:** SITL en WSL no recibía conexiones si usaba `127.0.0.1` como bind address.
*   **Solución:** SITL se lanza con `--serial0=tcp:0.0.0.0:5760` para escuchar en todas las interfaces internas de WSL, permitiendo que Windows conecte a `localhost:5760`.

---

## 5. Cómo Ejecutar (Quickstart)

1.  **Requisito:** Tener WSL instalado y Python en Windows (con entorno virtual activado).
2.  Doble click en **`launch.bat`**.
3.  Esperar a que se abran las 4 ventanas:
    *   Master Log
    *   SITL (ArduCopter)
    *   Flight Controller (Brain)
    *   Vision System
4.  El dron despegará automáticamente tras armar motores (aprox 10-20 segundos).

---

**Nota:** No editar los archivos `.waypoints` manualmente sin actualizar `run_sitl.sh` acorde a la altura del Home.