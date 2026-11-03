import base64
import html
import json
import os
import re
import time
from urllib.parse import quote, urljoin

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from bs4 import BeautifulSoup

# 1. Configuración de página
st.set_page_config(
    page_title="Kia | Price Intelligence Hub",
    page_icon="🚗",
    layout="wide",
)

LOGO_NEGRO = "assets/logo_kia_negro.png"
LOGO_BLANCO = "assets/logo_kia_blanco.png"

NEGRO = "#05141F"
ROJO = "#BB162B"
GRIS = "#64748B"

MAX_CODIGOS = 20   # máximo de códigos por consulta masiva
PAUSA = 0.5        # segundos entre códigos, para no saturar a los competidores

# Repuestos Boston (parece una tienda Magento; ajusta esta URL si su buscador es distinto).
# {q} se reemplaza por el código buscado.
BOSTON_BASE = "https://www.repuestosboston.cl"
BOSTON_BUSQUEDA = BOSTON_BASE + "/catalogsearch/result/?q={q}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CL,es;q=0.9",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def logo_html(path: str, alto: int, color_fallback: str) -> str:
    """Devuelve el logo embebido en base64, o un texto simple si no existe el archivo."""
    if os.path.exists(path):
        ext = os.path.splitext(path)[1].lower().replace(".", "")
        mime = "image/svg+xml" if ext == "svg" else f"image/{ext}"
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:{mime};base64,{b64}" alt="Kia" style="height:{alto}px;display:block;">'
    return f'<span style="font-weight:800;font-size:{alto}px;color:{color_fallback};letter-spacing:1px;">Kia</span>'


def fmt(n) -> str:
    """Formato CLP con punto como separador de miles: $54.900"""
    if n is None:
        return "—"
    return f"${n:,.0f}".replace(",", ".")


def fmt_signed(n) -> str:
    if n is None:
        return "—"
    if n > 0:
        return f"+{fmt(n)}"
    if n < 0:
        return f"-{fmt(abs(n))}"
    return fmt(0)


def kpi(label: str, valor: str, delta: str = "", clase: str = "") -> str:
    delta_html = f'<div class="delta {clase}">{delta}</div>' if delta else ""
    return (
        f'<div class="kpi"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{valor}</div>{delta_html}</div>'
    )


def normalizar(texto: str) -> str:
    """Mayúsculas y solo letras/números, para comparar códigos sin guiones ni espacios."""
    return re.sub(r"[^A-Z0-9]", "", str(texto).upper())


def limpiar_precio(valor):
    """Convierte '54900', '$54.900', '54900.0' o '54,900' en un entero. None si no hay precio."""
    if valor is None:
        return None
    s = str(valor).strip().replace("$", "").replace(" ", "")
    if not s or s.lower() in ("nan", "none"):
        return None
    m = re.fullmatch(r"(\d+)[.,]\d{1,2}", s)  # decimales, ej. 54900.00
    if m:
        return int(m.group(1))
    digitos = re.sub(r"[^\d]", "", s)  # separadores de miles, ej. 54.900
    return int(digitos) if digitos else None


# ---------------------------------------------------------------------------
# HTTP y lectura de fichas de producto
# ---------------------------------------------------------------------------
def _get(url: str, params=None):
    """GET con errores legibles. Si el sitio bloquea la consulta, se informa (no se intenta evadir)."""
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=12)
    except requests.RequestException as e:
        raise RuntimeError(f"No se pudo conectar ({e.__class__.__name__})")
    if res.status_code in (403, 429, 503):
        raise RuntimeError(f"El sitio bloqueó la consulta ({res.status_code})")
    if res.status_code != 200:
        raise RuntimeError(f"Respuesta inesperada del servidor ({res.status_code})")
    return res


def _iter_json(obj):
    """Recorre un JSON anidado devolviendo todos los diccionarios."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _iter_json(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_json(v)


def extraer_producto(soup: BeautifulSoup) -> dict:
    """Lee título, precio y disponibilidad desde los datos estructurados de una ficha de producto."""
    titulo, precio, disponible = None, None, None

    # 1) JSON-LD (schema.org/Product)
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except ValueError:
            continue
        for nodo in _iter_json(data):
            tipo = nodo.get("@type")
            tipos = tipo if isinstance(tipo, list) else [tipo]
            if "Product" not in tipos:
                continue
            titulo = titulo or nodo.get("name")
            ofertas = nodo.get("offers") or []
            if isinstance(ofertas, dict):
                ofertas = [ofertas]
            for o in ofertas:
                if not isinstance(o, dict):
                    continue
                if precio is None:
                    precio = limpiar_precio(o.get("price", o.get("lowPrice")))
                disp = str(o.get("availability", ""))
                if disponible is None:
                    if "InStock" in disp:
                        disponible = True
                    elif "OutOfStock" in disp:
                        disponible = False

    # 2) Metadatos y microdatos
    if not precio:
        for selector, attr in (
            ('meta[property="product:price:amount"]', "content"),
            ('meta[property="og:price:amount"]', "content"),
            ('[itemprop="price"]', "content"),
            ("[data-price-amount]", "data-price-amount"),
        ):
            el = soup.select_one(selector)
            if el is not None:
                precio = limpiar_precio(el.get(attr) or el.get_text())
                if precio:
                    break

    if not titulo:
        og = soup.select_one('meta[property="og:title"]')
        h1 = soup.find("h1")
        titulo = (og.get("content") if og else None) or (h1.get_text(strip=True) if h1 else None)

    return {
        "titulo": (titulo or "Producto encontrado").strip(),
        "precio": precio if precio and precio > 0 else None,
        "disponible": disponible,
    }


# ---------------------------------------------------------------------------
# Competidores. Cada función devuelve:
#   {"estado": "sin_resultados"}  o
#   {"estado": "ok", "exacto", "titulo", "url", "precio", "disponible"}
# y lanza RuntimeError si la consulta falla (los errores no se cachean).
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def consultar_ms(codigo: str) -> dict:
    res = _get(
        "https://www.msrepuestos.cl/search/suggest.json",
        params={"q": codigo, "resources[type]": "product"},
    )
    try:
        data = res.json()
    except ValueError:
        raise RuntimeError("Respuesta no válida del servidor")

    productos = data.get("resources", {}).get("results", {}).get("products", [])
    if not productos:
        return {"estado": "sin_resultados"}

    # Primer producto cuyo título/handle/tags contenga el código buscado
    clave = normalizar(codigo)
    elegido, exacto = None, False
    for p in productos:
        texto = normalizar(f"{p.get('title', '')} {p.get('handle', '')} {p.get('tags', '')}")
        if clave and clave in texto:
            elegido, exacto = p, True
            break
    if elegido is None:
        elegido = productos[0]

    try:
        precio = float(elegido.get("price", 0))
    except (TypeError, ValueError):
        precio = 0.0

    return {
        "estado": "ok",
        "exacto": exacto,
        "titulo": elegido.get("title", "Producto encontrado"),
        "url": "https://www.msrepuestos.cl" + elegido.get("url", ""),
        "precio": precio,
        "disponible": elegido.get("available"),
    }


@st.cache_data(ttl=600, show_spinner=False)
def consultar_boston(codigo: str) -> dict:
    clave = normalizar(codigo)
    res = _get(BOSTON_BUSQUEDA.format(q=quote(codigo)))
    soup = BeautifulSoup(res.text, "html.parser")

    # Si el buscador redirige directo a la ficha, la usamos tal cual
    if res.url.split("?")[0].endswith(".html") and "catalogsearch" not in res.url:
        url_producto, soup_producto = res.url, soup
    else:
        # Enlaces a productos cuyo URL o texto contengan el código
        candidatos = []
        for a in soup.find_all("a", href=True):
            href = urljoin(BOSTON_BASE + "/", a["href"]).split("?")[0].split("#")[0]
            if not href.startswith(BOSTON_BASE) or not href.endswith(".html"):
                continue
            if clave and clave in normalizar(href + " " + a.get_text()) and href not in candidatos:
                candidatos.append(href)
        if not candidatos:
            return {"estado": "sin_resultados"}

        url_producto = candidatos[0]
        time.sleep(0.3)
        res_p = _get(url_producto)
        soup_producto = BeautifulSoup(res_p.text, "html.parser")

    prod = extraer_producto(soup_producto)
    if prod["precio"] is None:
        raise RuntimeError("Encontré la ficha pero no pude leer el precio")

    exacto = bool(clave) and clave in normalizar(prod["titulo"] + " " + url_producto)
    return {
        "estado": "ok",
        "exacto": exacto,
        "titulo": prod["titulo"],
        "url": url_producto,
        "precio": float(prod["precio"]),
        "disponible": prod["disponible"],
    }


# Para agregar otro competidor: crea su función y súmala aquí.
COMPETIDORES = {
    "MS Repuestos": consultar_ms,
    "Repuestos Boston": consultar_boston,
}


def consultar_todos(codigo: str) -> dict:
    comps = {}
    for nombre, fn in COMPETIDORES.items():
        try:
            comps[nombre] = fn(codigo)
        except Exception as e:
            comps[nombre] = {"estado": "error", "error": str(e)}
    return comps


def elegir_referencia(comps: dict):
    """Competidor más barato (prefiere coincidencias exactas). Devuelve (nombre, datos) o None."""
    ok = {n: c for n, c in comps.items() if c["estado"] == "ok" and c.get("precio") and c["precio"] > 0}
    exactos = {n: c for n, c in ok.items() if c.get("exacto")}
    pool = exactos or ok
    if not pool:
        return None
    nombre = min(pool, key=lambda n: pool[n]["precio"])
    return nombre, pool[nombre]


def etiqueta_coincidencia(c: dict) -> str:
    if c["estado"] == "error":
        return "Error"
    if c["estado"] == "sin_resultados":
        return "Sin resultado"
    return "Exacta" if c.get("exacto") else "Revisar"


def comparar(codigo: str, mi_precio) -> dict:
    """Consulta un código en todos los competidores y arma la fila de resultado."""
    comps = consultar_todos(codigo)
    fila = {
        "Código": codigo,
        "Nuestro precio": mi_precio,
        "comp": comps,
        "Referencia": None,
        "Dif $": None,
        "Dif %": None,
        "Posición": "Sin resultado",
        "Coincidencia": "Sin resultado",
    }

    ref = elegir_referencia(comps)
    if ref is None:
        if any(c["estado"] == "error" for c in comps.values()):
            fila["Posición"] = "Error"
            fila["Coincidencia"] = "Error"
        return fila

    nombre, c = ref
    fila["Referencia"] = nombre
    fila["Coincidencia"] = "Exacta" if c.get("exacto") else "Revisar"

    if mi_precio is None:
        fila["Posición"] = "Sin precio propio"
        return fila

    dif = mi_precio - c["precio"]
    fila["Dif $"] = dif
    fila["Dif %"] = dif / c["precio"] * 100
    fila["Posición"] = "Más barato" if dif < 0 else ("Más caro" if dif > 0 else "Igual")
    return fila


# ---------------------------------------------------------------------------
# Lectura de la lista de códigos (texto pegado o archivo)
# ---------------------------------------------------------------------------
def parsear_texto(texto: str):
    items = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        partes = re.split(r"[\t;,\s]+", linea, maxsplit=1)
        codigo = partes[0].strip()
        precio = limpiar_precio(partes[1]) if len(partes) > 1 else None
        if codigo:
            items.append((codigo, precio))
    return items


def parsear_archivo(archivo):
    nombre = archivo.name.lower()
    if nombre.endswith(".csv"):
        df = pd.read_csv(archivo, sep=None, engine="python", dtype=str)
    else:
        df = pd.read_excel(archivo, dtype=str)
    if df.empty:
        return [], False

    nombres = {c: str(c).strip().lower() for c in df.columns}
    col_codigo = next(
        (c for c, n in nombres.items() if any(k in n for k in ("codigo", "código", "oem", "sku"))),
        df.columns[0],
    )
    col_precio = next((c for c, n in nombres.items() if "precio" in n or "price" in n), None)

    items = []
    for _, fila in df.iterrows():
        codigo = str(fila[col_codigo]).strip()
        if not codigo or codigo.lower() == "nan":
            continue
        precio = limpiar_precio(fila[col_precio]) if col_precio is not None else None
        items.append((codigo, precio))
    return items, col_precio is not None


# ---------------------------------------------------------------------------
# CSS (estilo claro, inspirado en kia.cl)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
.stApp { background-color: #FFFFFF; color: #05141F; }

/* Ocultar elementos por defecto de Streamlit */
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.block-container { padding-top: 1rem; padding-bottom: 0; max-width: 1200px; }

/* Header */
.kia-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.9rem 0; border-bottom: 1px solid #E5E7EB; margin-bottom: 1.5rem;
}
.kia-nav { display: flex; gap: 2rem; align-items: center; }
.kia-nav a {
    color: #05141F; text-decoration: none; font-size: 0.9rem; font-weight: 500;
    padding-bottom: 4px; border-bottom: 2px solid transparent; transition: border-color .2s;
}
.kia-nav a:hover { border-bottom-color: #05141F; }
.kia-nav a.active { border-bottom-color: #BB162B; font-weight: 700; }

/* Hero */
.kia-hero {
    background: #05141F; color: #FFFFFF; border-radius: 8px;
    padding: 2.5rem 2.5rem; margin-bottom: 2rem;
    display: flex; justify-content: space-between; align-items: center; gap: 1rem;
}
.kia-hero h1 { font-size: 2rem; font-weight: 700; margin: 0 0 .4rem 0; color: #FFFFFF; letter-spacing: -0.5px; }
.kia-hero p { margin: 0; color: #C7CCD3; font-size: 1rem; font-weight: 300; }
.kia-tag {
    border: 1px solid rgba(255,255,255,.35); color: #FFFFFF; padding: .4rem .9rem;
    border-radius: 999px; font-size: .72rem; font-weight: 600; letter-spacing: 1.5px;
    white-space: nowrap; text-transform: uppercase;
}
.kia-tag::before {
    content: ""; display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: #BB162B; margin-right: 8px;
}

/* Pestañas */
.stTabs [data-baseweb="tab"] { font-weight: 600; }
.stTabs [data-baseweb="tab-highlight"] { background-color: #BB162B; }

/* Títulos de sección */
.kia-section { font-size: 1.15rem; font-weight: 700; margin: .5rem 0 .8rem 0; color: #05141F; }

/* Formulario */
[data-testid="stForm"] {
    border: 1px solid #E5E7EB; border-radius: 8px; padding: 1.5rem;
    background: #FFFFFF; box-shadow: 0 2px 12px rgba(5, 20, 31, 0.05);
}
.stTextInput input, .stNumberInput input, .stTextArea textarea {
    background-color: #F4F5F7 !important; color: #05141F !important;
    border: 1px solid #E5E7EB !important; border-radius: 6px !important;
}
.stTextInput input, .stNumberInput input { padding: .65rem 1rem !important; }
.stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
    border-color: #05141F !important; box-shadow: 0 0 0 1px #05141F !important;
}
label, .stTextInput label p, .stNumberInput label p, .stTextArea label p {
    font-weight: 600 !important; color: #05141F !important;
}

/* Botones */
.stButton > button, [data-testid="stFormSubmitButton"] > button, .stDownloadButton > button {
    background: #05141F !important; color: #FFFFFF !important;
    font-weight: 600 !important; letter-spacing: .5px !important;
    border: none !important; border-radius: 6px !important;
    padding: .75rem 2rem !important; width: 100%; transition: background .2s;
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover, .stDownloadButton > button:hover {
    background: #BB162B !important; color: #FFFFFF !important;
}

/* Tarjeta de producto */
.product-card {
    background: #F4F5F7; border-left: 4px solid #BB162B; border-radius: 6px;
    padding: 1.25rem 1.5rem; margin: 1rem 0;
}
.product-card .eyebrow { color: #6B7280; font-size: .75rem; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 600; }
.product-card h3 { color: #05141F; margin: 4px 0 8px 0; font-size: 1.25rem; font-weight: 700; }
.product-card a { color: #BB162B; text-decoration: none; font-size: .9rem; font-weight: 600; }
.product-card a:hover { text-decoration: underline; }

/* Tarjetas KPI */
.kpi {
    background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px;
    padding: 1.25rem; box-shadow: 0 2px 12px rgba(5, 20, 31, 0.05); height: 100%;
}
.kpi .label { color: #6B7280; font-size: .85rem; font-weight: 500; }
.kpi .value { color: #05141F; font-size: 1.7rem; font-weight: 700; margin: .25rem 0; line-height: 1.2; }
.kpi .delta { font-size: .85rem; font-weight: 600; }
.kpi .delta.good { color: #16A34A; }
.kpi .delta.bad { color: #BB162B; }

/* Tabla de resultados */
.tbl-wrap { overflow-x: auto; border: 1px solid #E5E7EB; border-radius: 8px; margin: 1rem 0; }
.tbl { width: 100%; border-collapse: collapse; font-size: .88rem; }
.tbl th {
    background: #05141F; color: #FFFFFF; text-align: left; padding: .75rem 1rem;
    font-weight: 600; font-size: .78rem; letter-spacing: .5px; text-transform: uppercase; white-space: nowrap;
}
.tbl td { padding: .7rem 1rem; border-top: 1px solid #E5E7EB; color: #05141F; vertical-align: middle; }
.tbl tr:nth-child(even) td { background: #F9FAFB; }
.tbl td.num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.tbl td.best { background: #F0FDF4 !important; font-weight: 700; }
.tbl a { color: #BB162B; text-decoration: none; font-weight: 600; }
.tbl a:hover { text-decoration: underline; }
.badge {
    display: inline-block; padding: .2rem .6rem; border-radius: 999px;
    font-size: .74rem; font-weight: 600; white-space: nowrap;
}
.badge.good { background: #DCFCE7; color: #166534; }
.badge.bad { background: #FDE2E4; color: #9B1022; }
.badge.neutral { background: #E5E7EB; color: #374151; }
.badge.warn { background: #FEF3C7; color: #92400E; }

/* Footer */
.kia-footer {
    background: #05141F; color: #C7CCD3; border-radius: 8px 8px 0 0;
    padding: 2rem 2.5rem; margin-top: 3rem;
}
.kia-footer-top {
    display: flex; justify-content: space-between; align-items: center;
    padding-bottom: 1.25rem; border-bottom: 1px solid rgba(255,255,255,.12); margin-bottom: 1rem;
}
.kia-footer-links { display: flex; gap: 1.75rem; flex-wrap: wrap; }
.kia-footer-links a { color: #C7CCD3; text-decoration: none; font-size: .85rem; }
.kia-footer-links a:hover { color: #FFFFFF; }
.kia-footer small { color: #8B93A0; font-size: .75rem; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Vista: consulta individual
# ---------------------------------------------------------------------------
def vista_individual():
    st.markdown('<div class="kia-section">Consulta de coincidencia de precios</div>', unsafe_allow_html=True)

    with st.form("busqueda_form"):
        col1, col2 = st.columns([2, 1])
        with col1:
            codigo_oem = st.text_input("Código OEM del repuesto", value="641011M000")
        with col2:
            mi_precio = st.number_input("Nuestro precio ($ CLP)", value=54900, step=1000)
        boton_buscar = st.form_submit_button("ANALIZAR PRECIO COMPETIDOR")

    if not boton_buscar:
        return

    codigo = codigo_oem.strip()
    if not codigo:
        st.warning("Por favor ingresa un código OEM válido.")
        return

    with st.spinner("Escaneando catálogos de la competencia..."):
        comps = consultar_todos(codigo)

    # Estado y ficha por competidor
    hay_resultado = False
    for nombre, c in comps.items():
        if c["estado"] == "error":
            st.warning(f"{nombre}: no se pudo consultar ({c['error']}).")
        elif c["estado"] == "sin_resultados":
            st.info(f"{nombre}: sin resultados para el código '{codigo}'.")
        else:
            hay_resultado = True
            if not c["exacto"]:
                st.warning(
                    f"{nombre}: el producto encontrado no contiene el código buscado en su título. "
                    "Verifica la ficha original antes de usar este dato."
                )
            st.markdown(f"""
<div class="product-card">
<div class="eyebrow">Coincidencia detectada · {html.escape(nombre)}</div>
<h3>{html.escape(c["titulo"])}</h3>
<a href="{html.escape(c["url"])}" target="_blank">Ver ficha original en la web del competidor ↗</a>
</div>
""", unsafe_allow_html=True)

    if not hay_resultado:
        return

    # Métricas
    cols = st.columns(len(comps) + 2)
    cols[0].markdown(kpi("Nuestro precio", fmt(mi_precio)), unsafe_allow_html=True)
    for i, (nombre, c) in enumerate(comps.items(), 1):
        valor = fmt(c["precio"]) if c["estado"] == "ok" and c.get("precio") else "—"
        cols[i].markdown(kpi(nombre, valor), unsafe_allow_html=True)

    ref = elegir_referencia(comps)
    if ref is None:
        cols[-1].markdown(kpi("Posición de precio", "—"), unsafe_allow_html=True)
    else:
        nombre_ref, c_ref = ref
        diferencia = mi_precio - c_ref["precio"]
        porcentaje = diferencia / c_ref["precio"] * 100
        etiqueta = f"Posición vs. {nombre_ref}"
        if diferencia < 0:
            cols[-1].markdown(
                kpi(etiqueta, f"{fmt(abs(diferencia))} más económicos",
                    f"▼ {abs(porcentaje):.1f}% (ventaja)", "good"),
                unsafe_allow_html=True,
            )
        else:
            cols[-1].markdown(
                kpi(etiqueta, f"{fmt(diferencia)} por encima", f"▲ +{porcentaje:.1f}%", "bad"),
                unsafe_allow_html=True,
            )

    # Gráfico
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="kia-section">Gráfico comparativo</div>', unsafe_allow_html=True)

    entidades = ["Kia (nosotros)"] + [n for n, c in comps.items() if c["estado"] == "ok" and c.get("precio")]
    precios = [mi_precio] + [c["precio"] for n, c in comps.items() if c["estado"] == "ok" and c.get("precio")]
    df_grafico = pd.DataFrame({"Entidad": entidades, "Precio": precios})

    fig = px.bar(
        df_grafico, x="Entidad", y="Precio", text_auto="$,.0f", color="Entidad",
        color_discrete_map={"Kia (nosotros)": NEGRO, "MS Repuestos": ROJO, "Repuestos Boston": GRIS},
    )
    fig.update_layout(
        template="plotly_white", showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=13, color=NEGRO),
        xaxis=dict(showgrid=False, title=""),
        yaxis=dict(showgrid=True, gridcolor="#E5E7EB", title=""),
        margin=dict(l=20, r=20, t=20, b=20), bargap=0.55,
    )
    fig.update_traces(textposition="outside", textfont=dict(color=NEGRO, size=14), marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Vista: consulta masiva
# ---------------------------------------------------------------------------
def celda_competidor(c: dict, es_ref: bool) -> str:
    clase = "num best" if es_ref else "num"
    if c["estado"] == "error":
        motivo = html.escape(c.get("error", ""))
        return f'<td class="num"><span class="badge warn" title="{motivo}">Error</span></td>'
    if c["estado"] == "sin_resultados":
        return '<td class="num">—</td>'
    texto = fmt(c["precio"]) + ("" if c.get("exacto") else " ⚠")
    titulo = html.escape(c.get("titulo", ""))
    url = html.escape(c.get("url", ""))
    return f'<td class="{clase}"><a href="{url}" target="_blank" title="{titulo}">{texto}</a></td>'


def tabla_html(resultados) -> str:
    clases_pos = {"Más barato": "good", "Más caro": "bad", "Igual": "neutral"}
    filas = []
    for r in resultados:
        pos = r["Posición"]
        pos_badge = f'<span class="badge {clases_pos.get(pos, "warn")}">{html.escape(pos)}</span>'
        coin = r["Coincidencia"]
        coin_badge = f'<span class="badge {"good" if coin == "Exacta" else "warn"}">{html.escape(coin)}</span>'
        dif_pct = f'{r["Dif %"]:+.1f}%' if r["Dif %"] is not None else "—"

        celdas_comp = "".join(
            celda_competidor(r["comp"][nombre], r["Referencia"] == nombre) for nombre in COMPETIDORES
        )
        filas.append(
            "<tr>"
            f'<td><b>{html.escape(r["Código"])}</b></td>'
            f'<td class="num">{fmt(r["Nuestro precio"])}</td>'
            f"{celdas_comp}"
            f'<td class="num">{fmt_signed(r["Dif $"])}</td>'
            f'<td class="num">{dif_pct}</td>'
            f"<td>{pos_badge}</td>"
            f"<td>{coin_badge}</td>"
            "</tr>"
        )

    encabezado = (
        "<tr><th>Código</th><th>Nuestro</th>"
        + "".join(f"<th>{html.escape(n)}</th>" for n in COMPETIDORES)
        + "<th>Dif $</th><th>Dif %</th><th>Posición</th><th>Coincidencia</th></tr>"
    )
    return f'<div class="tbl-wrap"><table class="tbl">{encabezado}{"".join(filas)}</table></div>'


def fila_csv(r: dict) -> dict:
    out = {"Código": r["Código"], "Nuestro precio": r["Nuestro precio"]}
    for nombre, c in r["comp"].items():
        out[f"{nombre} - precio"] = c.get("precio")
        out[f"{nombre} - producto"] = c.get("titulo") or c.get("error") or ""
        out[f"{nombre} - coincidencia"] = etiqueta_coincidencia(c)
        out[f"{nombre} - stock"] = (
            "Disponible" if c.get("disponible") is True else "Agotado" if c.get("disponible") is False else ""
        )
        out[f"{nombre} - url"] = c.get("url", "")
    out["Competidor de referencia"] = r["Referencia"] or ""
    out["Dif $"] = r["Dif $"]
    out["Dif %"] = None if r["Dif %"] is None else round(r["Dif %"], 2)
    out["Posición"] = r["Posición"]
    return out


def mostrar_resultados(resultados):
    total = len(resultados)
    caros = sum(1 for r in resultados if r["Posición"] == "Más caro")
    baratos = sum(1 for r in resultados if r["Posición"] == "Más barato")
    sin_dato = sum(1 for r in resultados if r["Posición"] in ("Sin resultado", "Error"))
    difs_exactas = [r["Dif %"] for r in resultados if r["Dif %"] is not None and r["Coincidencia"] == "Exacta"]
    promedio = sum(difs_exactas) / len(difs_exactas) if difs_exactas else None

    st.markdown('<div class="kia-section">Resumen</div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(kpi("Códigos consultados", str(total)), unsafe_allow_html=True)
    c2.markdown(kpi("Más caros que el mercado", str(caros)), unsafe_allow_html=True)
    c3.markdown(kpi("Más baratos que el mercado", str(baratos)), unsafe_allow_html=True)
    c4.markdown(kpi("Sin coincidencia", str(sin_dato)), unsafe_allow_html=True)
    if promedio is None:
        c5.markdown(kpi("Diferencia promedio", "—"), unsafe_allow_html=True)
    else:
        c5.markdown(
            kpi("Diferencia promedio", f"{promedio:+.1f}%", "coincidencias exactas",
                "bad" if promedio > 0 else "good"),
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="kia-section">Detalle por código</div>', unsafe_allow_html=True)
    st.markdown(tabla_html(resultados), unsafe_allow_html=True)
    st.caption(
        "La comparación (Dif $, Dif %, Posición) es contra el competidor más barato con coincidencia, "
        "resaltado en verde. Cada precio enlaza a la ficha del competidor. "
        "Un ⚠ indica que el título del producto no contiene el código buscado: confirma que sea el mismo repuesto."
    )

    # Gráfico de diferencia porcentual
    con_dif = [
        {"Código": r["Código"], "Dif %": r["Dif %"], "Posición": r["Posición"]}
        for r in resultados if r["Dif %"] is not None
    ]
    if con_dif:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="kia-section">Diferencia de precio vs. el mercado</div>', unsafe_allow_html=True)
        df_g = pd.DataFrame(con_dif).sort_values("Dif %", ascending=False)
        df_g["Etiqueta"] = df_g["Dif %"].map(lambda v: f"{v:+.1f}%")
        fig = px.bar(
            df_g, x="Dif %", y="Código", orientation="h", color="Posición", text="Etiqueta",
            color_discrete_map={"Más barato": NEGRO, "Más caro": ROJO, "Igual": "#9CA3AF"},
        )
        fig.update_layout(
            template="plotly_white", showlegend=True, legend_title_text="",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", size=13, color=NEGRO),
            xaxis=dict(showgrid=True, gridcolor="#E5E7EB", title="Diferencia (%)", zeroline=True, zerolinecolor=NEGRO),
            yaxis=dict(title="", autorange="reversed"),
            margin=dict(l=20, r=20, t=20, b=20),
            height=max(260, 42 * len(df_g) + 100), bargap=0.35,
        )
        fig.update_traces(textposition="outside", textfont=dict(color=NEGRO, size=12), marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    # Descarga
    df_csv = pd.DataFrame([fila_csv(r) for r in resultados])
    st.download_button(
        "DESCARGAR RESULTADOS (CSV)",
        data=df_csv.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="comparacion_precios.csv",
        mime="text/csv",
    )


def vista_masiva():
    st.markdown('<div class="kia-section">Consulta masiva</div>', unsafe_allow_html=True)
    st.caption(
        f"Pega hasta {MAX_CODIGOS} códigos, uno por línea, con su precio opcional al lado "
        "(separado por coma, tabulación o punto y coma; puedes copiar dos columnas desde Excel). "
        "O sube un Excel/CSV con una columna de código y otra cuyo nombre contenga «precio». "
        "Si subes un archivo, se usa en vez del texto."
    )

    with st.form("form_masivo"):
        texto = st.text_area(
            "Códigos OEM y precio",
            height=180,
            placeholder="641011M000, 54900\n29110C5500, 61900\n...",
        )
        archivo = st.file_uploader("…o sube un archivo", type=["xlsx", "csv"])
        enviar = st.form_submit_button("ANALIZAR LISTA")

    if enviar:
        items, hay_precio = [], True
        try:
            if archivo is not None:
                items, hay_precio = parsear_archivo(archivo)
            else:
                items = parsear_texto(texto)
        except Exception as e:
            st.error(f"No pude leer el archivo: {e}")
            items = []

        # Quitar duplicados conservando el orden
        vistos, unicos = set(), []
        for codigo, precio in items:
            k = normalizar(codigo)
            if k and k not in vistos:
                vistos.add(k)
                unicos.append((codigo, precio))
        items = unicos

        if not items:
            st.warning("No encontré códigos para consultar.")
        else:
            if archivo is not None and not hay_precio:
                st.info("No encontré una columna de precio en el archivo: se consultará solo el precio de la competencia.")
            if len(items) > MAX_CODIGOS:
                st.warning(f"Se encontraron {len(items)} códigos; se analizarán solo los primeros {MAX_CODIGOS}.")
                items = items[:MAX_CODIGOS]

            barra = st.progress(0.0, text="Iniciando consulta...")
            resultados = []
            for i, (codigo, precio) in enumerate(items, 1):
                barra.progress((i - 1) / len(items), text=f"Consultando {codigo} ({i}/{len(items)})")
                resultados.append(comparar(codigo, precio))
                if i < len(items):
                    time.sleep(PAUSA)
            barra.empty()
            st.session_state["resultados_masivos"] = resultados

    resultados = st.session_state.get("resultados_masivos")
    if resultados:
        mostrar_resultados(resultados)


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------
# Header
st.markdown(f"""
<div class="kia-header">
<div>{logo_html(LOGO_NEGRO, 28, NEGRO)}</div>
<div class="kia-nav">
<a href="https://www.kia.cl/postventa/servicios.html" target="_blank">Postventa</a>
<a href="https://www.kia.cl/postventa/repuestos.html" target="_blank">Repuestos</a>
<a href="https://www.kia.cl/postventa/accesorios.html" target="_blank">Accesorios</a>
<a class="active" href="#">Price Intelligence</a>
</div>
</div>
""", unsafe_allow_html=True)

# Hero
st.markdown("""
<div class="kia-hero">
<div>
<h1>Price Intelligence Hub</h1>
<p>Compara el precio de tus repuestos con el mercado en segundos.</p>
</div>
<div class="kia-tag">Competitor tracker</div>
</div>
""", unsafe_allow_html=True)

# Contenido
tab1, tab2 = st.tabs(["Consulta individual", f"Consulta masiva (hasta {MAX_CODIGOS})"])
with tab1:
    vista_individual()
with tab2:
    vista_masiva()

# Footer
st.markdown(f"""
<div class="kia-footer">
<div class="kia-footer-top">
<div>{logo_html(LOGO_BLANCO, 24, "#FFFFFF")}</div>
<div class="kia-footer-links">
<a href="https://www.kia.cl/postventa/repuestos.html" target="_blank">Repuestos</a>
<a href="https://www.kia.cl/postventa/accesorios.html" target="_blank">Accesorios</a>
<a href="https://www.kia.cl/postventa/mantenciones.html" target="_blank">Mantenciones</a>
<a href="https://www.kia.cl/postventa/garantia.html" target="_blank">Garantía Kia</a>
<a href="https://www.kia.cl/quiero-un-kia/red-de-concesionarios.html" target="_blank">Red de concesionarios</a>
</div>
</div>
<small>Herramienta interna de análisis de precios. Uso exclusivo del equipo autorizado.</small>
</div>
""", unsafe_allow_html=True)
