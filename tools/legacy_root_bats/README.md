# Legacy root BAT launchers

Estos .bat vivian antes en la raiz del repo. Se archivaron para que la raiz tenga una unica entrada operativa: LANZAR_TODO_PAPER.bat.

Contenido:

- launch.bat: wrapper antiguo de pipeline SIMULATION; ahora LANZAR_TODO_PAPER.bat llama directamente a tools\launch_workflow.bat SIMULATION.
- launch_digital_twin.bat: wrapper historico de REAL_TWIN.
- LIMPIAR_PORTPROXY_ADMIN.bat: utilidad manual de limpieza de netsh portproxy, no launcher de vuelo.
