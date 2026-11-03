import base64
import html
import os
import re
import time

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

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

MAX_CODIGOS = 20   # máximo de códigos por consulta masiva
PAUSA = 0.5        # segundos entre consultas, para no saturar al competidor

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
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
        f'<div class="kpi"><div class="label">{label}</div>'
        f'<div class="value">{valor}</div>{delta_html}</div>'
    )


def normalizar(texto: str) -> str:
    """Mayúsculas y solo letras/números, para comparar códigos sin guiones ni espacios."""
    return re.sub(r"[^A-Z0-9]", "", str(texto).upper())


def limpiar_precio(valor):
    """Convierte '54900', '$54.900', '54900.0' o '54,900' en un entero. None si no hay precio."""
    s = str(valor).strip().replace("$", "").replace(" ", "")
    if not s or s.lower() == "nan":
        return None
    m = re.fullmatch(r"(\d+)[.,]\d{1,2}", s)  # decimales, ej. 54900.00
    if m:
        return int(m.group(1))
    digitos = re.sub(r"[^\d]", "", s)  # separadores de miles, ej. 54.900
    return int(digitos) if digitos else None


# ---------------------------------------------------------------------------
# Consulta al competidor
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def consultar_competidor(codigo: str) -> dict:
    """
    Consulta MS Repuestos. Lanza RuntimeError si falla la consulta (los errores no se cachean).
    Devuelve {"estado": "sin_resultados"} o {"estado": "ok", ...}.
    """
    try:
        res = requests.get(
            "https://www.msrepuestos.cl/search/suggest.json",
            params={"q": codigo, "resources[type]": "product"},
            headers=HEADERS,
            timeout=10,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"No se pudo conectar ({e.__class__.__name__})")

    if res.status_code != 200:
        raise RuntimeError(f"Respuesta inesperada del servidor ({res.status_code})")

    try:
        data = res.json()
    except ValueError:
        raise RuntimeError("Respuesta no válida del servidor")

    productos = data.get("resources", {}).get("results", {}).get("products", [])
    if not productos:
        return {"estado": "sin_resultados"}

    # Buscar el primer producto cuyo título/handle/tags contenga el código buscado
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


def comparar(codigo: str, mi_precio) -> dict:
    """Consulta un código y arma la fila de resultado."""
    fila = {
        "Código": codigo,
        "Producto": "",
        "Nuestro precio": mi_precio,
        "MS Repuestos": None,
        "Dif $": None,
        "Dif %": None,
        "Posición": "Sin resultado",
        "Coincidencia": "—",
        "Stock": "—",
        "URL": "",
    }
    try:
        r = consultar_competidor(codigo)
    except Exception as e:
        fila["Posición"] = "Error"
        fila["Producto"] = str(e)
        fila["Coincidencia"] = "Error"
        return fila

    if r["estado"] == "sin_resultados":
        fila["Coincidencia"] = "Sin resultado"
        return fila

    fila["Producto"] = r["titulo"]
    fila["URL"] = r["url"]
    fila["MS Repuestos"] = r["precio"]
    fila["Coincidencia"] = "Exacta" if r["exacto"] else "Revisar"
    if r["disponible"] is True:
        fila["Stock"] = "Disponible"
    elif r["disponible"] is False:
        fila["Stock"] = "Agotado"

    if mi_precio is None:
        fila["Posición"] = "Sin precio propio"
    elif r["precio"] > 0:
        dif = mi_precio - r["precio"]
        fila["Dif $"] = dif
        fila["Dif %"] = dif / r["precio"] * 100
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
    padding: 1.25rem 1.5rem; margin: 1.5rem 0;
}
.product-card .eyebrow { color: #6B7280; font-size: .75rem; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 600; }
.product-card h3 { color: #05141F; margin: 4px 0 8px 0; font-size: 1.25rem; font-weight: 700; }
.product-card a { color: #BB162B; text-decoration: none; font-size: .9rem; font-weight: 600; }
.product-card a:hover { text-decoration: underline; }

/* Tarjetas KPI */
.kpi {
    background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px;
    padding: 1.25rem; box-shadow: 0 2px 12px rgba(5, 20, 31, 0.05);
}
.kpi .label { color: #6B7280; font-size: .85rem; font-weight: 500; }
.kpi .value { color: #05141F; font-size: 1.9rem; font-weight: 700; margin: .25rem 0; line-height: 1.2; }
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

    with st.spinner("Escaneando catálogo del competidor..."):
        try:
            r = consultar_competidor(codigo)
        except Exception as e:
            st.error(f"Error en la ejecución de la consulta: {e}")
            return

    if r["estado"] == "sin_resultados":
        st.warning(f"No se encontraron productos coincidentes para el código OEM '{codigo}'.")
        return

    if not r["exacto"]:
        st.warning(
            "El producto encontrado no contiene el código buscado en su título. "
            "Verifica la ficha original antes de usar este dato."
        )

    precio_competidor = r["precio"]
    titulo_prod = html.escape(r["titulo"])
    url_prod = html.escape(r["url"])

    diferencia = mi_precio - precio_competidor
    porcentaje = (diferencia / precio_competidor) * 100 if precio_competidor > 0 else 0

    st.markdown(f"""
<div class="product-card">
<div class="eyebrow">Coincidencia detectada</div>
<h3>{titulo_prod}</h3>
<a href="{url_prod}" target="_blank">Ver ficha original en la web del competidor ↗</a>
</div>
""", unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    m1.markdown(kpi("Nuestro precio", fmt(mi_precio)), unsafe_allow_html=True)
    m2.markdown(kpi("MS Repuestos", fmt(precio_competidor)), unsafe_allow_html=True)

    if diferencia < 0:
        m3.markdown(
            kpi("Posición de precio", f"{fmt(abs(diferencia))} más económicos",
                f"▼ {abs(porcentaje):.1f}% (ventaja)", "good"),
            unsafe_allow_html=True,
        )
    else:
        m3.markdown(
            kpi("Posición de precio", f"{fmt(diferencia)} por encima",
                f"▲ +{porcentaje:.1f}%", "bad"),
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="kia-section">Gráfico comparativo</div>', unsafe_allow_html=True)

    df_grafico = pd.DataFrame({
        "Entidad": ["Kia (nosotros)", "MS Repuestos"],
        "Precio": [mi_precio, precio_competidor],
    })
    fig = px.bar(
        df_grafico, x="Entidad", y="Precio", text_auto="$,.0f", color="Entidad",
        color_discrete_map={"Kia (nosotros)": NEGRO, "MS Repuestos": ROJO},
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
def tabla_html(resultados) -> str:
    clases_pos = {"Más barato": "good", "Más caro": "bad", "Igual": "neutral"}
    filas = []
    for r in resultados:
        pos = r["Posición"]
        pos_badge = f'<span class="badge {clases_pos.get(pos, "warn")}">{html.escape(pos)}</span>'

        coin = r["Coincidencia"]
        coin_badge = f'<span class="badge {"good" if coin == "Exacta" else "warn"}">{html.escape(coin)}</span>'

        producto = html.escape(r["Producto"]) if r["Producto"] else "—"
        if r["URL"]:
            producto = f'<a href="{html.escape(r["URL"])}" target="_blank">{producto} ↗</a>'

        dif_pct = f'{r["Dif %"]:+.1f}%' if r["Dif %"] is not None else "—"

        filas.append(
            "<tr>"
            f'<td><b>{html.escape(r["Código"])}</b></td>'
            f"<td>{producto}</td>"
            f'<td class="num">{fmt(r["Nuestro precio"])}</td>'
            f'<td class="num">{fmt(r["MS Repuestos"])}</td>'
            f'<td class="num">{fmt_signed(r["Dif $"])}</td>'
            f'<td class="num">{dif_pct}</td>'
            f"<td>{pos_badge}</td>"
            f"<td>{coin_badge}</td>"
            f'<td>{html.escape(r["Stock"])}</td>'
            "</tr>"
        )

    encabezado = (
        "<tr><th>Código</th><th>Producto (MS Repuestos)</th><th>Nuestro</th><th>MS</th>"
        "<th>Dif $</th><th>Dif %</th><th>Posición</th><th>Coincidencia</th><th>Stock</th></tr>"
    )
    return f'<div class="tbl-wrap"><table class="tbl">{encabezado}{"".join(filas)}</table></div>'


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
    c2.markdown(kpi("Más caros que MS", str(caros)), unsafe_allow_html=True)
    c3.markdown(kpi("Más baratos que MS", str(baratos)), unsafe_allow_html=True)
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

    if any(r["Coincidencia"] == "Revisar" for r in resultados):
        st.caption(
            "Las filas marcadas «Revisar» no contienen el código buscado en el título del producto "
            "encontrado: abre el enlace y confirma que sea el mismo repuesto antes de usar ese dato."
        )

    # Gráfico de diferencia porcentual
    con_dif = [r for r in resultados if r["Dif %"] is not None]
    if con_dif:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="kia-section">Diferencia de precio vs. MS Repuestos</div>', unsafe_allow_html=True)
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
    df_csv = pd.DataFrame(resultados)
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
            placeholder="641011M000, 54900\n641012M000, 61900\n...",
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
                st.info("No encontré una columna de precio en el archivo: se consultará solo el precio del competidor.")
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
