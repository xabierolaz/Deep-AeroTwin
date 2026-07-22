$ErrorActionPreference = "Stop"
$PaperPath = Join-Path $PSScriptRoot "..\..\pipeline_b_concept.tex"
$Text = Get-Content -LiteralPath $PaperPath -Raw
$Replacements = @{
    "bandwidth evidence" = "Debemos medir la carga total del enlace."
    "geospatial validation evidence" = "Debemos validar la posicion con una referencia externa."
    "geospatial-prior audit" = "Debemos auditar origen, fecha, cache y trafico del prior."
    "sensor/detector configuration evidence" = "Debemos fijar sensor, pesos, version, clases y umbral."
    "end-to-end latency evidence" = "Debemos medir desde la fuente hasta el actor visible en el visor."
    "reproducibility package" = "Debemos congelar codigo, schemas y versiones."
    "Unreal/VR demonstration evidence" = "Debemos aportar una ejecucion Unreal/VR trazable."
    "operator study evidence" = "Debemos comparar tareas con operadores y baselines."
    "information-role display taxonomy" = "Debemos cerrar las etiquetas visuales de origen y estado."
    "operational safety envelope" = "Debemos fijar umbrales y la regla de fallback."
    "tracking persistence evidence" = "Debemos medir persistencia, ID switches y despawn."
    "prior-plus-state-update utility evidence" = "Debemos comparar la utilidad del prior y sus actualizaciones."
    "network degradation evidence" = "Debemos ensayar perdida, jitter y recuperacion."
    "network degradation and tracking evidence" = "Debemos combinar red degradada y persistencia de actores."
    "measured evaluation results" = "Debemos cerrar los resultados medidos."
    "VR-headset figure evidence" = "Debemos aportar una captura real del visor o mirror."
    "flight/replay evidence source" = "Debemos identificar plataforma, autopiloto y fuente del replay."
    "geospatial-prior and low-visibility evidence" = "Debemos separar sensor observable de render legible."
    "low-visibility sensor evidence" = "Debemos ensayar una configuracion de baja visibilidad."
    "geospatial-prior validation evidence" = "Debemos medir cobertura y vigencia del prior."
    "reproducibility and safety evidence" = "Debemos dejar evidencia de seguridad y reproducibilidad."
    "funding and acknowledgements" = "Debemos completar financiacion y agradecimientos."
    "CRediT author roles" = "Debemos confirmar los roles CRediT."
    "competing interests statement" = "Debemos declarar conflictos o ausencia de ellos."
    "data and code availability" = "Debemos fijar que datos y codigo compartimos."
    "ethics approval" = "Debemos obtener aprobacion o exencion etica."
    "AI-use declaration" = "Debemos completar la declaracion de uso de IA."
    "statistical analysis plan" = "Debemos cerrar el plan estadistico antes de reclutar."
}
foreach ($Key in $Replacements.Keys) {
    $Text = $Text.Replace("\pendiente{$Key}", "\pendiente{$($Replacements[$Key])}")
}
Set-Content -LiteralPath $PaperPath -Value $Text -Encoding utf8
Write-Host "Translated paper placeholders in $PaperPath"
