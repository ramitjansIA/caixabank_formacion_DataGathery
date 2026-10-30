"""Construye el notebook público de la sesión 01 sin incluir soluciones."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "12_web_scraping_para_auditoria.ipynb"


def markdown(source: str, *, cell_id: str, tags: list[str] | None = None) -> dict:
    return {
        "cell_type": "markdown",
        "id": cell_id,
        "metadata": {"tags": tags or []},
        "source": dedent(source).strip() + "\n",
    }


def code(source: str, *, cell_id: str, tags: list[str] | None = None) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": cell_id,
        "metadata": {"tags": tags or []},
        "outputs": [],
        "source": dedent(source).strip() + "\n",
    }


cells = [
    markdown(
        """
        # Sesión 01 · Automatización Web I

        **Banco de España y evidencia de auditoría · 6 de noviembre de 2026 · 12:30–13:30**

        Partimos de la introducción al scraping impartida previamente. En esta sesión
        aplicamos los conceptos a una fuente real y construimos un artefacto reutilizable.

        **Caso acumulativo:** AUD-2026-017

        Una alerta pública sobre ciberseguridad abre una investigación sobre una posible
        campaña de vishing y la eficacia de los controles internos que deberían detectarla.

        En la parte común construiremos juntos el primer artefacto del expediente:
        un conjunto de alertas públicas con fuente, fecha de recogida e integridad verificable.
        Después elige **un solo reto**, A o B.
        """,
        cell_id="title",
    ),
    markdown(
        """
        ## Antes de extraer: permiso y minimización

        Este ejemplo usa una selección de metadatos reales del Portal del Cliente Bancario del Banco de España.
        El índice HTML es una construcción docente: sus clases CSS son propias y no deben
        confundirse con los selectores del sitio oficial. Los enlaces apuntan a cada artículo.
        No constituye una captura íntegra ni prueba qué conocía la entidad en una fecha.
        El aviso legal permite reproducir información con fidelidad y atribución, pero antes de
        reutilizar el patrón con otra web debes revisar sus términos, robots.txt, frecuencia,
        volumen y posible presencia de datos personales.

        robots.txt expresa preferencias de rastreo. No concede permiso ni sustituye la revisión
        jurídica o las normas internas.
        """,
        cell_id="responsible-use",
    ),
    code(
        """
        from __future__ import annotations

        import hashlib
        import json
        import sys
        import time
        from datetime import UTC, datetime
        from pathlib import Path
        from urllib.parse import urljoin, urlparse
        from urllib.robotparser import RobotFileParser

        import pandas as pd
        import requests
        from bs4 import BeautifulSoup

        start_path = Path.cwd().resolve()
        ROOT = next(
            (
                candidate
                for candidate in (start_path, *start_path.parents)
                if (candidate / "pyproject.toml").exists()
                and (candidate / "data/caso_comun").exists()
            ),
            None,
        )
        if ROOT is None:
            raise RuntimeError("No se ha encontrado la raíz del repositorio")
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))

        from auditcase.models import PublicAlert

        CASE_ID = "AUD-2026-017"
        SOURCE_URL = "https://clientebancario.bde.es/pcb/es/blog/"
        SOURCE_ID = "bde-fraude-seleccion-2026-10-28"
        FIXTURE = ROOT / "data/caso_comun/sesion_01/bde_fraude_indice_docente.html"
        SNAPSHOT_COLLECTED_AT = datetime(2026, 10, 28, tzinfo=UTC)

        print(f"Repositorio: {ROOT}")
        print(f"Caso: {CASE_ID}")
        """,
        cell_id="setup",
        tags=["common"],
    ),
    markdown(
        """
        ## 1. Congelar el origen

        Una ejecución en directo puede cambiar durante la clase. La muestra local permite explicar
        y depurar el parser de forma reproducible. Su hash SHA-256 vincula los registros al HTML
        exacto del que proceden. El hash detecta diferencias de bytes frente a una referencia,
        pero no acredita por sí solo autoría, veracidad o fecha de publicación.
        """,
        cell_id="freeze-source",
    ),
    code(
        """
        html_bytes = FIXTURE.read_bytes()
        html = html_bytes.decode("utf-8")
        source_sha256 = hashlib.sha256(html_bytes).hexdigest()

        print(f"Bytes: {len(html_bytes):,}")
        print(f"SHA-256: {source_sha256}")
        """,
        cell_id="load-fixture",
        tags=["common"],
    ),
    markdown(
        """
        ## 2. Inspeccionar antes de seleccionar

        Buscamos un contenedor repetido y, dentro de él, campos con significado estable.
        No usamos posiciones como segundo div porque suelen romperse con cambios de diseño.
        """,
        cell_id="inspect-dom",
    ),
    code(
        """
        soup = BeautifulSoup(html, "html.parser")
        first_record = soup.select_one(".publication")

        if first_record is None:
            raise ValueError("No se encontró el contenedor esperado")

        print(first_record.prettify()[:1_200])
        """,
        cell_id="show-first-record",
        tags=["common"],
    ),
    markdown(
        """
        ## 3. Extraer y validar contra un contrato

        El parser localiza texto. Pydantic comprueba que la salida cumple el contrato común.
        Un cambio incompatible de la página se convierte así en un error visible.
        """,
        cell_id="extract-contract",
    ),
    code(
        """
        def parse_bde_alerts(
            html: str,
            *,
            base_url: str,
            source_id: str,
            collected_at: datetime,
        ) -> list[PublicAlert]:
            soup = BeautifulSoup(html, "html.parser")
            containers = soup.select(".publication")
            if not containers:
                raise ValueError("Cero registros: revisa el HTML y los selectores")

            alerts: list[PublicAlert] = []
            for position, container in enumerate(containers, start=1):
                date_node = container.select_one(".publication-date")
                link_node = container.select_one(".publication-title a[href]")
                if date_node is None or link_node is None:
                    raise ValueError(f"Registro {position} incompleto")

                published_date = datetime.strptime(
                    date_node.get_text(" ", strip=True), "%d/%m/%Y"
                ).date()
                alerts.append(
                    PublicAlert(
                        published_date=published_date,
                        title=link_node.get_text(" ", strip=True),
                        url=urljoin(base_url, link_node["href"]),
                        source_id=source_id,
                        collected_at=collected_at,
                    )
                )

            urls = {str(alert.url) for alert in alerts}
            if len(urls) != len(alerts):
                raise ValueError("La fuente contiene URLs duplicadas")
            return alerts
        """,
        cell_id="parser",
        tags=["common"],
    ),
    code(
        """
        alerts = parse_bde_alerts(
            html,
            base_url=SOURCE_URL,
            source_id=SOURCE_ID,
            collected_at=SNAPSHOT_COLLECTED_AT,
        )

        alerts_df = pd.DataFrame(
            [
                {
                    "published_date": alert.published_date,
                    "title": alert.title,
                    "url": str(alert.url),
                    "source_id": alert.source_id,
                }
                for alert in alerts
            ]
        )
        alerts_df
        """,
        cell_id="validate-and-display",
        tags=["common"],
    ),
    markdown(
        """
        ## 4. Persistir un artefacto trazable

        El JSON conserva los registros y los metadatos mínimos para que otra persona pueda
        reconstruir qué ocurrió. La conclusión de auditoría todavía no forma parte de esta salida.
        """,
        cell_id="persist-artifact",
    ),
    code(
        """
        artifact = {
            "case_id": CASE_ID,
            "session": 1,
            "artifact_type": "public_alerts",
            "source": {
                "source_id": SOURCE_ID,
                "url": SOURCE_URL,
                "snapshot_path": str(FIXTURE.relative_to(ROOT)),
                "collected_at": SNAPSHOT_COLLECTED_AT.isoformat(),
                "sha256": source_sha256,
                "terms_reviewed": True,
                "representation": "curated_teaching_index",
                "selection": "non_exhaustive",
            },
            "items": [alert.model_dump(mode="json") for alert in alerts],
        }

        output_path = ROOT / "artifacts/session_01/public_alerts.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"Artefacto: {output_path}")
        print(f"Registros: {len(artifact['items'])}")
        """,
        cell_id="write-artifact",
        tags=["common"],
    ),
    markdown(
        """
        ## 5. Acceso remoto opcional y deliberado

        La siguiente función consulta robots.txt, usa un agente identificable, limita la frecuencia
        y exige HTML. No se ejecuta por defecto. Antes de activarla hay que volver a revisar la
        fuente y las normas aplicables.

        Comprobado el 29/10/2026: el robots.txt del Portal del Cliente Bancario restringe
        las rutas del buscador, pero permite el artículo de vishing de este ejemplo.
        Un bloqueo de red, un error HTTP y una prohibición de robots son situaciones diferentes.
        Las reglas pueden cambiar: la función vuelve a consultarlas en cada ejecución.
        """,
        cell_id="remote-intro",
    ),
    code(
        """
        def robots_allows(url: str, *, user_agent: str, timeout: float = 10) -> bool:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            response = requests.get(
                robots_url,
                headers={"User-Agent": user_agent},
                timeout=timeout,
            )
            print(f"robots.txt: HTTP {response.status_code} — {robots_url}")
            # 404/410 indican ausencia de fichero, no una prohibición de rastreo.
            # Continuar exige haber revisado también el propósito y los términos del sitio.
            if response.status_code in (404, 410):
                return True
            # Política conservadora del curso para acceso denegado.
            if response.status_code in (401, 403):
                return False
            # Ante 5xx o fallo de red no asumimos permiso: se detiene la ejecución.
            response.raise_for_status()

            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(response.text.splitlines())
            return parser.can_fetch(user_agent, url)


        def fetch_html(
            url: str,
            *,
            user_agent: str,
            delay_seconds: float = 1.5,
            timeout: tuple[float, float] = (5, 20),
        ) -> bytes:
            if not robots_allows(url, user_agent=user_agent):
                raise PermissionError(f"robots.txt no permite acceder a {url}")

            time.sleep(delay_seconds)
            response = requests.get(
                url,
                headers={
                    "User-Agent": user_agent,
                    "Accept": "text/html,application/xhtml+xml",
                },
                timeout=timeout,
            )
            response.raise_for_status()
            if "text/html" not in response.headers.get("Content-Type", ""):
                raise ValueError("La respuesta no es HTML")
            print(f"Página: HTTP {response.status_code} — {len(response.content):,} bytes")
            # El parser de BeautifulSoup detecta la codificación desde bytes/metadatos.
            return response.content
        """,
        cell_id="responsible-fetch",
        tags=["common"],
    ),
    code(
        """
        RUN_REMOTE_SCRAPING = False
        USER_AGENT = "AuditEvidenceCourse/1.0 (contacto-docente@example.invalid)"

        if RUN_REMOTE_SCRAPING:
            live_url = "https://clientebancario.bde.es/pcb/es/blog/vishing.html"
            live_html = fetch_html(live_url, user_agent=USER_AGENT)
            live_soup = BeautifulSoup(live_html, "html.parser")
            heading = live_soup.select_one("h1")
            if heading is None:
                raise ValueError("La página remota no contiene el título esperado")
            print("Título remoto:", heading.get_text(" ", strip=True))
            print("Los selectores del índice docente no se aplican a esta página.")
        else:
            print("Acceso remoto desactivado. La parte común usa la copia local.")
        """,
        cell_id="remote-opt-in",
        tags=["common"],
    ),
    markdown(
        """
        ## Elige un reto

        Haz A o B, no ambos. Antes de pedir código a una IA, escribe qué evidencia quieres obtener,
        por qué la fuente es legítima y qué condición debería hacer fallar el proceso.
        """,
        cell_id="choose-challenge",
    ),
    markdown(
        """
        ## Caso A · Priorizar indicios conocidos

        Sobre las alertas de la parte común:

        1. define categorías y palabras clave para canales de fraude, como voz, SMS y correo;
        2. asigna cero o más categorías a cada título, sin usar un LLM;
        3. conserva únicamente los registros relevantes;
        4. escribe artifacts/session_01/relevant_alerts.json con los metadatos de origen;
        5. muestra la regla y palabra concreta que seleccionó cada publicación;
        6. crea una vista legible de los seleccionados y exporta un CSV;
        7. explica un falso positivo y un falso negativo posibles.

        No modifiques el artefacto común. Crea uno nuevo.
        """,
        cell_id="exercise-a",
        tags=["exercise-a"],
    ),
    code(
        """
        # TU SOLUCIÓN A
        #
        # Sugerencia de interfaz, puedes cambiarla si justificas el contrato:
        #
        # def classify_title(title: str, rules: dict[str, set[str]]) -> list[str]:
        #     ...
        #
        # relevant_alerts = ...
        """,
        cell_id="exercise-a-code",
        tags=["exercise-a"],
    ),
    markdown(
        """
        ## Caso B · Auditar una fuente elegida

        Elige una URL que puedas consultar legítimamente y que publique avisos, noticias o
        información relacionada con el ámbito financiero.

        1. documenta por qué puedes usarla y si existe una API preferible;
        2. identifica el contenedor y los campos de cada registro;
        3. implementa un parser propio, sin alterar parse_bde_alerts;
        4. normaliza la salida al contrato PublicAlert;
        5. detecta explícitamente cero resultados, campos ausentes y duplicados;
        6. guarda el HTML o una muestra mínima y su SHA-256;
        7. escribe artifacts/session_01/student_source_alerts.json;
        8. crea una vista con búsqueda y fechas, e indica qué no representa tu muestra.

        Si la fuente bloquea automatización, cambia de fuente. No intentes eludir controles.
        """,
        cell_id="exercise-b",
        tags=["exercise-b"],
    ),
    code(
        """
        # TU SOLUCIÓN B
        STUDENT_SOURCE_URL = ""
        STUDENT_RECORD_SELECTOR = ""

        # 1. Revisión de permiso y alternativa API:
        # 2. Selectores y contrato:
        # 3. Casos de fallo:
        # 4. Persistencia y hash:
        """,
        cell_id="exercise-b-code",
        tags=["exercise-b"],
    ),
    markdown(
        """
        ## Cierre y checkpoint de Git

        Antes de terminar:

        - abre el JSON generado y comprueba que no contiene una conclusión inventada;
        - revisa que no has versionado claves, cookies ni datos personales;
        - ejecuta git diff para entender exactamente qué cambiará;
        - crea un commit pequeño que describa el artefacto, no la actividad.

        En Automatización Web II repetiremos esta recogida y añadiremos un histórico de cambios.
        """,
        cell_id="close",
    ),
]

live_demo_cells = [
    markdown(
        """
        ## Mini práctica opcional · Una web creada para scraping (3–5 min)

        [Books to Scrape](https://books.toscrape.com/) es una librería ficticia del
        [Scraping Sandbox](https://toscrape.com/), creado expresamente para practicar.
        Aquí recorremos el proceso completo: robots, GET, selectores y tabla de resultados.
        Es un ejemplo técnico independiente del expediente bancario.

        Consultamos solo la primera página. Los precios y valoraciones son ficticios.
        A 29/10/2026, robots.txt responde 404: no existe un fichero con reglas publicadas.
        Eso no equivale a permiso universal; en este caso lo acompaña el propósito docente
        explícito del sitio. Un Disallow o un error de servidor detendría nuestra función.

        Cambia RUN_SANDBOX_DEMO a True para descargar y ver los datos reales de la demo.
        """,
        cell_id="sandbox-intro",
    ),
    code(
        '''
        from decimal import Decimal

        RUN_SANDBOX_DEMO = False
        SANDBOX_URL = "https://books.toscrape.com/"

        if RUN_SANDBOX_DEMO:
            sandbox_html = fetch_html(SANDBOX_URL, user_agent=USER_AGENT)
            sandbox_soup = BeautifulSoup(sandbox_html, "html.parser")
            products = sandbox_soup.select("article.product_pod")
            if not products:
                raise ValueError("La demo no contiene los productos esperados")

            books = []
            for product in products:
                link = product.select_one("h3 a[href][title]")
                price = product.select_one(".price_color")
                if link is None or price is None:
                    raise ValueError("Producto incompleto: revisa los selectores")
                books.append({
                    "título": link["title"],
                    "precio_GBP_ficticio": Decimal(price.get_text(strip=True).removeprefix("£")),
                    "url": urljoin(SANDBOX_URL, link["href"]),
                })

            books_df = pd.DataFrame(books)
            print(f"Primera página: {len(books_df)} libros. Sin recorrer paginación.")
            with pd.option_context("display.max_colwidth", None):
                display(books_df)
        else:
            print("Demo remota desactivada. Activa RUN_SANDBOX_DEMO para ver el recorrido HTTP completo.")
        ''',
        cell_id="sandbox-live",
        tags=["optional-live"],
    ),
    markdown(
        """
        **Observa:** el título visible puede estar truncado, mientras que el atributo title
        del enlace contiene el texto completo. La URL relativa se normaliza con urljoin.
        El precio se convierte a Decimal y conserva su moneda, sin atribuirle valor real.

        **Prueba rápida:** ordena books_df por precio o muestra solo cinco filas. Para cualquier
        otra fuente hay que volver a revisar acceso, selectores y significado de los campos.
        Este ejemplo no modifica public_alerts.json.
        """,
        cell_id="sandbox-observations",
    ),
]
demo_position = next(i for i, cell in enumerate(cells) if cell["id"] == "choose-challenge")
cells[demo_position:demo_position] = live_demo_cells

visual_cells = [
    markdown(
        """
        ## 3.1 Del nodo HTML a la fila

        Seguimos una sola publicación en sus dos representaciones. El parser conserva
        el significado de los campos y transforma fecha y URL. El título no demuestra
        por sí solo que la publicación sea relevante para nuestra hipótesis.
        """,
        cell_id="trace-record",
    ),
    code(
        '''
        import html as html_module
        from IPython.display import HTML, display

        first = alerts[0]
        original_node = BeautifulSoup(html, "html.parser").select_one(".publication")
        escaped_node = html_module.escape(str(original_node))
        display(HTML(f"<h4>HTML de origen</h4><pre>{escaped_node}</pre>"))
        display(pd.DataFrame([first.model_dump(mode="json")]).T.rename(columns={0: "valor"}))
        ''',
        cell_id="trace-record-code",
        tags=["common"],
    ),
    markdown(
        """
        ## 3.2 Explorar lo extraído

        La tabla muestra enlaces pulsables, títulos completos y fechas ordenadas.
        La búsqueda ignora mayúsculas y acentos y trata el texto como literal, no como regex.
        Prueba `vishing`, `llamada` y una palabra inexistente. Cambia el intervalo de fechas.
        Una búsqueda vacía devuelve todos los registros dentro del intervalo.
        """,
        cell_id="explore",
    ),
    code(
        '''
        import unicodedata


        def normalize_search(text: str) -> str:
            decomposed = unicodedata.normalize("NFKD", text.casefold())
            return "".join(c for c in decomposed if not unicodedata.combining(c))


        def filter_publications(query="", start=None, end=None):
            if start and end and start > end:
                raise ValueError("La fecha inicial debe ser anterior a la final")
            mask = alerts_df["title"].map(normalize_search).str.contains(
                normalize_search(query.strip()), regex=False
            )
            if start:
                mask &= alerts_df["published_date"] >= start
            if end:
                mask &= alerts_df["published_date"] <= end
            return alerts_df.loc[mask].sort_values("published_date", ascending=False)


        def show_publications(frame):
            rows = []
            for row in frame.itertuples():
                title = html_module.escape(row.title)
                url = html_module.escape(row.url, quote=True)
                rows.append(
                    f'<tr><td>{row.published_date}</td><td>{title}</td>'
                    f'<td><a href="{url}" target="_blank" rel="noopener">Fuente</a></td></tr>'
                )
            body = "".join(rows) or '<tr><td colspan="3">Sin coincidencias</td></tr>'
            display(HTML(
                f"<p><strong>{len(frame)} de {len(alerts_df)} publicaciones</strong></p>"
                '<table style="width:100%;text-align:left"><thead><tr>'
                '<th>Fecha</th><th>Título</th><th>Enlace</th></tr></thead>'
                f'<tbody>{body}</tbody></table>'
            ))


        show_publications(filter_publications())
        ''',
        cell_id="explorer-functions",
        tags=["common"],
    ),
    code(
        '''
        import ipywidgets as widgets

        query_input = widgets.Text(description="Buscar:", placeholder="vishing, llamada…")
        start_input = widgets.DatePicker(description="Desde:")
        end_input = widgets.DatePicker(description="Hasta:")
        results_output = widgets.Output()


        def refresh_publications(change=None):
            with results_output:
                results_output.clear_output(wait=True)
                try:
                    show_publications(filter_publications(
                        query_input.value, start_input.value, end_input.value
                    ))
                except ValueError as error:
                    print(error)


        for control in (query_input, start_input, end_input):
            control.observe(refresh_publications, names="value")
        display(widgets.VBox([query_input, widgets.HBox([start_input, end_input]), results_output]))
        refresh_publications()

        # Alternativa para un visor sin widgets:
        # show_publications(filter_publications("vishing"))
        ''',
        cell_id="explorer-controls",
        tags=["common"],
    ),
    markdown(
        """
        ## 3.3 Qué describe esta muestra

        Contamos publicaciones seleccionadas por año. Las barras describen nuestro índice,
        **no la frecuencia de estafas ni su evolución**. Los años sin publicaciones tampoco
        significan ausencia de riesgo. La selección temática no es exhaustiva ni aleatoria.
        """,
        cell_id="describe-sample",
    ),
    code(
        '''
        summary = pd.DataFrame({
            "indicador": ["Publicaciones", "URLs únicas", "Fecha más antigua", "Fecha más reciente"],
            "valor": [len(alerts_df), alerts_df["url"].nunique(),
                      str(alerts_df["published_date"].min()), str(alerts_df["published_date"].max())],
        })
        display(summary)
        by_year = alerts_df["published_date"].map(lambda d: d.year).value_counts().sort_index()
        display(by_year.rename_axis("Año").to_frame("Publicaciones seleccionadas").style.bar(
            subset=["Publicaciones seleccionadas"], color="#80cece", vmin=0
        ))
        ''',
        cell_id="sample-summary",
        tags=["common"],
    ),
    markdown(
        """
        ## 3.4 Un fallo visible antes de guardar

        Modificamos copias en memoria: una cambia el contenedor, otra elimina una fecha
        y otra duplica un registro. Observamos dónde falla cada una. El HTML original
        permanece intacto. Para reparar un selector en una fuente real, hay que volver
        a inspeccionar su estructura; cambiarlo a ciegas puede extraer datos incorrectos.
        """,
        cell_id="failure-lab",
    ),
    code(
        '''
        missing_date = BeautifulSoup(html, "html.parser")
        missing_date.select_one(".publication-date").decompose()
        duplicated = BeautifulSoup(html, "html.parser")
        import copy
        duplicated.main.append(copy.deepcopy(duplicated.select_one(".publication")))

        variants = {
            "Contenedor cambiado": html.replace('class="publication"', 'class="renamed"'),
            "Fecha ausente": str(missing_date),
            "Registro duplicado": str(duplicated),
        }
        observations = []
        for scenario, changed_html in variants.items():
            try:
                parse_bde_alerts(changed_html, base_url=SOURCE_URL,
                                 source_id=SOURCE_ID, collected_at=SNAPSHOT_COLLECTED_AT)
                message = "Sin error: revisar el contrato"
            except ValueError as error:
                message = str(error)
            observations.append({"escenario": scenario, "resultado": message})
        display(pd.DataFrame(observations))

        # Reparación del ejemplo controlado: conocemos exactamente el cambio introducido.
        restored_html = variants["Contenedor cambiado"].replace('class="renamed"', 'class="publication"')
        restored = parse_bde_alerts(restored_html, base_url=SOURCE_URL,
                                   source_id=SOURCE_ID, collected_at=SNAPSHOT_COLLECTED_AT)
        print(f"Tras restaurar el selector conocido: {len(restored)} registros válidos")
        ''',
        cell_id="failure-lab-code",
        tags=["common"],
    ),
]
insertion = next(i for i, cell in enumerate(cells) if cell["id"] == "persist-artifact")
cells[insertion:insertion] = visual_cells

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUTPUT.write_text(
    json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
    encoding="utf-8",
)
print(f"Creado: {OUTPUT}")
