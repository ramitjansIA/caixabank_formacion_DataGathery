# 12 · Automatización Web I

- [Notebook de alumnado](notebook_alumnado.ipynb).
- [Presentación Quarto](presentacion.qmd).
- [Presentación HTML autocontenida](12_automatizacion_web_i_presentacion.html).
- Estilos y recursos locales: `plantilla_*.css`, `estilo_sesion.css` y `recursos/`.

Desde la raíz del repositorio:

```bash
uv run python scripts/build_session_12_notebook.py
quarto render 12_automatizacion_web_i/presentacion.qmd
```

Las soluciones docentes permanecen bajo `.instructor/`, excluidas de Git.
Los datos y artefactos conservan el identificador interno de la primera sesión del caso
(`data/caso_comun/sesion_01/` y `artifacts/session_01/`).
