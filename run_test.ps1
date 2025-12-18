
# Script de Auditoria y Prueba de Vuelo
$sitlLog = "pipeline\logs\sitl_test.log"
$brainLog = "pipeline\logs\brain_test.log"

# Limpieza previa
Write-Host "Limpiando procesos anteriores..."
taskkill /F /IM python.exe 2>$null
wsl -e pkill -9 -f arducopter 2>$null

# Crear directorio de logs si no existe
New-Item -ItemType Directory -Force -Path "pipeline\logs" | Out-Null

# 1. Iniciar SITL (WSL)
Write-Host "Iniciando SITL (WSL)..."
# Convertir path a formato WSL
$wslPath = wsl wslpath -u "$PWD/pipeline/run_sitl.sh"
$sitlProcess = Start-Process -FilePath "wsl" -ArgumentList "-e", "bash", $wslPath -RedirectStandardOutput $sitlLog -RedirectStandardError $sitlLog -PassThru -NoNewWindow

# Esperar a que SITL arranque (unos segundos)
Start-Sleep -Seconds 10

# 2. Iniciar Flight Controller (Python Windows)
Write-Host "Iniciando Flight Controller..."
$brainProcess = Start-Process -FilePath "python" -ArgumentList "-u", "pipeline/flight_controller.py" -RedirectStandardOutput $brainLog -RedirectStandardError $brainLog -PassThru -NoNewWindow

# 3. Esperar tiempo de vuelo (Despegue + WP1)
Write-Host "Ejecutando prueba de vuelo (45 segundos)..."
Start-Sleep -Seconds 45

# 4. Detener Procesos
Write-Host "Deteniendo procesos..."
Stop-Process -Id $brainProcess.Id -Force -ErrorAction SilentlyContinue
wsl -e pkill -9 -f arducopter

Write-Host "Prueba finalizada."
