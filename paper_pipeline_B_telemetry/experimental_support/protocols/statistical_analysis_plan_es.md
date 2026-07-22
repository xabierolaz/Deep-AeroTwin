# Plan estadistico preliminar

Estado: borrador. Debe cerrarse antes de ejecutar el estudio humano para evitar
analisis oportunista.

## Hipotesis

H1. La telemetria semantica tiene menor bitrate medio y p95 que los perfiles de
video declarados para el mismo intervalo de mision.

H2. La latencia fuente-HMD queda por debajo del umbral auxiliar definido antes
del experimento.

H3. El error geoespacial queda dentro de la envolvente de incertidumbre mostrada
al operador.

H4. Bajo perdida/jitter, el display no presenta datos obsoletos como frescos.

H5. La condicion VR mejora conciencia espacial o exito de tarea respecto a
baselines sin aumentar carga de trabajo/cibermareo de forma inaceptable.

## Endpoints

Endpoint primario recomendado:

- puntuacion de conciencia espacial o exito de tarea, predefinir uno antes de
  recoger datos.

Endpoints secundarios:

- tiempo de respuesta;
- error de localizacion;
- deteccion de stale/uncertainty;
- NASA-TLX;
- SSQ;
- SART/SAGAT;
- near misses simulados;
- overtrust.

## Diseno

Preferencia: within-subject con contrabalanceo por orden de interfaz.

Modelo recomendado:

- variable continua: modelo lineal mixto con participante como efecto aleatorio;
- variable binaria: modelo logistico mixto;
- ordinal/cuestionarios: modelo ordinal o analisis no parametrico justificado;
- si la muestra es pequena: reportar efecto, intervalo de confianza y tests
  pareados robustos, no solo p-values.

## Comparaciones

Comparaciones primarias:

- VR digital twin vs video-only;
- VR digital twin vs map-only;
- VR digital twin vs desktop-hybrid.

Controlar multiplicidad cuando haya multiples endpoints o comparaciones. Usar
Holm o FDR si procede. Predefinir la familia primaria.

## Tamano muestral

Pendiente. Opciones:

- estudio piloto: justificar como estimacion de efecto y viabilidad;
- estudio confirmatorio: calcular potencia a partir del efecto minimo relevante.

Registrar abandonos y exclusiones antes de analizar resultados.

## Criterios de aceptacion tecnicos

Estos umbrales deben cerrarse antes de ejecutar pruebas:

- p95 de latencia fuente-HMD maximo permitido;
- edad maxima de actor antes de stale;
- edad maxima antes de remove/despawn;
- incertidumbre maxima visible;
- confianza minima para actor confirmado;
- regla de fallback.

## Reporting

Reportar:

- media, mediana, desviacion/iqr segun proceda;
- intervalos de confianza;
- tamano del efecto;
- numero de muestras validas;
- datos perdidos;
- criterio de exclusion;
- analisis de sensibilidad si hay fallos tecnicos.
