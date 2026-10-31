# Audit Evidence Copilot — material docente

Curso práctico para auditores tecnológicos de CaixaBank. A lo largo de once sesiones se
construye un expediente reproducible sobre una posible campaña de vishing y sobre la eficacia
de los controles internos que deberían detectarla.

El sistema reúne fuentes públicas y datos sintéticos, transcribe llamadas, identifica señales,
contrasta procedimientos y prepara documentos para revisión humana. No decide si existe fraude
ni emite una conclusión de auditoría de forma autónoma.

## Estado de la migración

El bloque 12, Automatización Web I, es el piloto completo del nuevo formato:

- presentación Quarto con imágenes reales y fuentes visibles;
- parte común ejecutable y reproducible;
- caso A sobre los datos comunes;
- caso B sobre una fuente elegida por el estudiante;
- copia privada del docente con ambos casos resueltos.

Esta actualización incorpora únicamente el bloque 12 cerrado y sus recursos. Las carpetas
13 a 22 están preparadas para las sesiones nuevas; su README indica el material pendiente.
Los notebooks anteriores conservan su versión previa mientras se revisan en la rama de trabajo.
La numeración continúa la del repositorio: los bloques anteriores al 12 mantienen su ubicación.

## Calendario docente

| Nº | Fecha y hora | Duración | Sesión |
|---:|---|---:|---|
| 12 | 06/11/2026 12:30 | 1 h | [Automatización Web I](12_automatizacion_web_i/) |
| 13 | 09/12/2026 10:00 | 1 h | [Automatización Web II](13_automatizacion_web_ii/) |
| 14 | 09/12/2026 11:30 | 1 h | [Automatización por voz](14_automatizacion_por_voz/) |
| 15 | 09/12/2026 12:30 | 0,5 h | [Introducción a IA generativa](15_introduccion_ia_generativa/) |
| 16 | 09/12/2026 14:30 | 1 h | [Modelos de decisión de IA Generativa](16_modelos_decision_ia_generativa/) |
| 17 | 09/12/2026 16:00 | 1,5 h | [Interfaces de IA con Gradio](17_interfaces_ia_gradio/) |
| 18 | 10/12/2026 08:30 | 1,5 h | [Automatizaciones de correos electrónicos](18_automatizaciones_correos/) |
| 19 | 10/12/2026 10:30 | 1,5 h | [Agentes y herramientas limitadas](19_agentes_herramientas/) |
| 20 | 10/12/2026 12:30 | 1 h | [RAG con servidor privado](20_rag_servidor_privado/) |
| 21 | 10/12/2026 14:30 | 1 h | [Diseño del proyecto de auditoría](21_diseno_proyecto_auditoria/) |
| 22 | 10/12/2026 16:00 | 1,5 h | [Integración y revisión humana](22_integracion_revision_humana/) |

## Bloque 12 · Automatización Web I

- Notebook público: [notebook_alumnado.ipynb](12_automatizacion_web_i/notebook_alumnado.ipynb)
- Presentación fuente: [presentacion.qmd](12_automatizacion_web_i/presentacion.qmd)
- Presentación autocontenida: [12_automatizacion_web_i_presentacion.html](12_automatizacion_web_i/12_automatizacion_web_i_presentacion.html)
- Índice docente: <code>data/caso_comun/sesion_01/bde_fraude_indice_docente.html</code>
- Solución docente: <code>.instructor/notebooks_resueltos/</code>, excluida de Git

Para regenerar el notebook público:

~~~bash
uv run python scripts/build_session_12_notebook.py
~~~

Para renderizar la presentación:

~~~bash
quarto render 12_automatizacion_web_i/presentacion.qmd
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
