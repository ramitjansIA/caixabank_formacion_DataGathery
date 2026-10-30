# Arquitectura docente — Audit Evidence Copilot

## Objetivo

Construir durante once sesiones un expediente reproducible sobre una posible campaña de
vishing que aprovecha una debilidad de control. El sistema reúne fuentes públicas y evidencia
sintética, transcribe una llamada, identifica señales, contrasta procedimientos y genera un
borrador de auditoría que una persona debe revisar.

El curso no pretende decidir si existe fraude ni automatizar una conclusión de auditoría.

## Historia acumulativa

| Sesión | Pieza incorporada al expediente |
|---|---|
| 1. Automatización Web I | Extracción del Banco de España y primer artefacto trazable |
| 2. Automatización Web II | Histórico, procedencia y hashes |
| 3. Audio | Transcripción segmentada con faster-whisper |
| 4. IA generativa | Router común y separación entre hechos e hipótesis |
| 5. Modelos de decisión de IA Generativa | Señales de vishing mediante JEV y breve introducción conceptual a LoRA |
| 6. Interfaces de IA con Gradio | Carga de llamadas, transcripción, señales justificadas y revisión humana |
| 7. Automatizaciones de correos electrónicos | Mensajes y adjuntos sintéticos vinculados al expediente y borradores de seguimiento |
| 8. Agentes | Herramientas limitadas y registro de acciones |
| 9. RAG | Evidencia recuperada con versión y cita |
| 10. Diseño | Objetivo, criterio, prueba y hallazgo |
| 11. Integración | Expediente final y revisión humana |

## Ajustes al horario actualizado

Las clases propias comienzan el 6 de noviembre de 2026 a las 12:30 con Automatización Web I.
La introducción al scraping y a la automatización la imparte previamente el otro profesor.
Las sesiones restantes se celebran los días 9 y 10 de diciembre. El bloque de las 16:00 del
día 9 se sustituye por Interfaces de IA con Gradio, con una duración de 90 minutos.

Git y Docker se introducen dentro de los bloques donde se necesitan. Los planificadores
nativos no constituyen un bloque propio. La creación de DOCX, XLSX y PPTX se incorpora al
proyecto integrador, aprovechando los conocimientos impartidos previamente por el compañero.

La interfaz de Gradio comienza con las funciones ya construidas en las sesiones 1 a 5.
Después incorpora correos, herramientas de agentes y consultas al servidor RAG. El router
Python conecta Gemini con la clave del estudiante o un modelo local servido por Ollama o
llama.cpp. La interfaz muestra la evidencia que sustenta cada resultado.

### Sesión 6: Interfaces de IA con Gradio

- 15 minutos: componentes, eventos, estado y demostración del flujo de auditoría.
- 35 minutos: parte común con llamada sintética, transcripción y señales con marcas temporales.
- 30 minutos: caso A con revisión y exportación o caso B con datos y flujo propios.
- 10 minutos: ejecución de la aplicación y checkpoint con Git.

LoRA se explica conceptualmente dentro de la sesión 5: adaptación de pesos, datos etiquetados
y diferencia respecto a prompting y RAG. No se plantea un entrenamiento práctico en este bloque.

## Patrón de cada sesión

Cada sesión dispone de una presentación Quarto y un notebook público. El notebook contiene:

1. una parte común completamente implementada que se ejecuta en clase;
2. un caso A sin resolver, sobre los datos comunes y de dificultad media-baja;
3. un caso B sin resolver, sobre una fuente escogida por el estudiante y de dificultad alta.

El estudiante elige A o B. La copia privada del docente resuelve ambos casos y vive bajo
`.instructor/`, directorio excluido de Git.

## Contrato de artefactos

Todo artefacto debe incluir:

- identificador del caso y de la sesión;
- fuente o artefactos de entrada;
- fecha y hora de creación;
- hash SHA-256 cuando exista un fichero de origen;
- separación explícita entre hecho, transformación e inferencia.

## Límites de seguridad

- Los datos internos, llamadas y operaciones del caso son sintéticos.
- Las fuentes web se revisan antes de acceder y se consultan con frecuencia limitada.
- Las claves se cargan desde variables de entorno y nunca se versionan.
- Gemini se invoca mediante un router Python con la clave del estudiante.
- Ollama y llama.cpp sirven modelos locales; no ejecutan Gemini.
- Los modelos proponen extracción, clasificación o redacción. Python conserva las reglas.
- Una persona aprueba cualquier conclusión de auditoría.
