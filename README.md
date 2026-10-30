# Audit Evidence Copilot — material docente

Curso práctico para auditores tecnológicos de CaixaBank. A lo largo de once sesiones se
construye un expediente reproducible sobre una posible campaña de vishing y sobre la eficacia
de los controles internos que deberían detectarla.

El sistema reúne fuentes públicas y datos sintéticos, transcribe llamadas, identifica señales,
contrasta procedimientos y prepara documentos para revisión humana. No decide si existe fraude
ni emite una conclusión de auditoría de forma autónoma.

## Estado de la migración

La sesión 1 es el piloto completo del nuevo formato:

- presentación Quarto con imágenes reales y fuentes visibles;
- parte común ejecutable y reproducible;
- caso A sobre los datos comunes;
- caso B sobre una fuente elegida por el estudiante;
- copia privada del docente con ambos casos resueltos.

Esta actualización incorpora únicamente la sesión 1 cerrada y sus recursos. Los notebooks
de las otras sesiones conservan su versión previa mientras se revisan en la rama de trabajo.

## Calendario docente

| Nº | Fecha y hora | Duración | Sesión |
|---:|---|---:|---|
| 1 | 06/11/2026 12:30 | 1 h | Automatización Web I |
| 2 | 09/12/2026 10:00 | 1 h | Automatización Web II |
| 3 | 09/12/2026 11:30 | 1 h | Automatización por voz |
| 4 | 09/12/2026 12:30 | 0,5 h | Introducción a IA generativa |
| 5 | 09/12/2026 14:30 | 1 h | Modelos de decisión de IA Generativa |
| 6 | 09/12/2026 16:00 | 1,5 h | Interfaces de IA con Gradio |
| 7 | 10/12/2026 08:30 | 1,5 h | Automatizaciones de correos electrónicos |
| 8 | 10/12/2026 10:30 | 1,5 h | Agentes y herramientas limitadas |
| 9 | 10/12/2026 12:30 | 1 h | RAG con servidor privado |
| 10 | 10/12/2026 14:30 | 1 h | Diseño del proyecto de auditoría |
| 11 | 10/12/2026 16:00 | 1,5 h | Integración y revisión humana |

## Sesión 1

- Notebook público: <code>12_web_scraping_para_auditoria.ipynb</code>
- Presentación fuente: <code>presentaciones/01_web_scraping_para_auditoria.qmd</code>
- Presentación autocontenida: <code>presentaciones/01_web_scraping_para_auditoria.html</code>
- Índice docente: <code>data/caso_comun/sesion_01/bde_fraude_indice_docente.html</code>
- Solución docente: <code>.instructor/notebooks_resueltos/</code>, excluida de Git

Para regenerar el notebook público:

~~~bash
uv run python scripts/build_session_01_notebook.py
~~~

Para renderizar la presentación:

~~~bash
quarto render presentaciones/01_web_scraping_para_auditoria.qmd
~~~

## Entorno

~~~bash
uv sync --extra dev
uv run jupyter lab
~~~

Las claves y los servicios reales se activarán mediante variables de entorno. Gemini se llamará
desde un router Python con la clave del estudiante. Ollama o llama.cpp servirán los modelos
locales. Las claves nunca se guardan en notebooks ni en Git.

## Scraping responsable

La parte común usa un índice HTML docente con metadatos de nueve artículos oficiales sobre
fraude del Portal del Cliente Bancario. No es una captura del listado oficial ni una selección
exhaustiva. Incluye enlaces, explorador con búsqueda y fechas, resumen visual y errores guiados.
El acceso remoto a un artículo real es opcional y está desactivado por defecto. Para otra URL hay
que revisar términos, aviso legal, robots.txt, existencia de una API, frecuencia, volumen y
presencia de datos personales. No se eluden autenticación, CAPTCHA ni controles de acceso.

La arquitectura completa y el contrato de artefactos están en
<code>docs/curso_auditoria.md</code>.
