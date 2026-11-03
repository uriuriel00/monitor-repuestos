import base64
import html
import os

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


def logo_html(path: str, alto: int, color_fallback: str) -> str:
    """Devuelve el logo embebido en base64, o un texto simple si no existe el archivo."""
    if os.path.exists(path):
        ext = os.path.splitext(path)[1].lower().replace(".", "")
        mime = "image/svg+xml" if ext == "svg" else f"image/{ext}"
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:{mime};base64,{b64}" alt="Kia" style="height:{alto}px;display:block;">'
    return f'<span style="font-weight:800;font-size:{alto}px;color:{color_fallback};letter-spacing:1px;">Kia</span>'


# 2. CSS personalizado (estilo claro, inspirado en kia.cl)
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

/* Títulos de sección */
.kia-section { font-size: 1.15rem; font-weight: 700; margin: 0 0 .8rem 0; color: #05141F; }

/* Formulario */
[data-testid="stForm"] {
    border: 1px solid #E5E7EB; border-radius: 8px; padding: 1.5rem;
    background: #FFFFFF; box-shadow: 0 2px 12px rgba(5, 20, 31, 0.05);
}
.stTextInput input, .stNumberInput input {
    background-color: #F4F5F7 !important; color: #05141F !important;
    border: 1px solid #E5E7EB !important; border-radius: 6px !important;
    padding: .65rem 1rem !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #05141F !important; box-shadow: 0 0 0 1px #05141F !important;
}
label, .stTextInput label p, .stNumberInput label p { font-weight: 600 !important; color: #05141F !important; }

/* Botón principal */
.stButton > button, [data-testid="stFormSubmitButton"] > button {
    background: #05141F !important; color: #FFFFFF !important;
    font-weight: 600 !important; letter-spacing: .5px !important;
    border: none !important; border-radius: 6px !important;
    padding: .75rem 2rem !important; width: 100%; transition: background .2s;
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
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

/* Métricas */
[data-testid="stMetric"] {
    background: #FFFFFF; padding: 1.25rem; border-radius: 8px;
    border: 1px solid #E5E7EB; box-shadow: 0 2px 12px rgba(5, 20, 31, 0.05);
}
[data-testid="stMetricLabel"] { color: #6B7280 !important; font-size: .85rem !important; font-weight: 500; }
[data-testid="stMetricValue"] { color: #05141F !important; font-weight: 700 !important; }

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

# 3. Header
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

# 4. Hero
st.markdown("""
<div class="kia-hero">
<div>
<h1>Price Intelligence Hub</h1>
<p>Compara el precio de tus repuestos con el mercado en segundos.</p>
</div>
<div class="kia-tag">Competitor tracker</div>
</div>
""", unsafe_allow_html=True)

# 5. Formulario
st.markdown('<div class="kia-section">Consulta de coincidencia de precios</div>', unsafe_allow_html=True)

with st.form("busqueda_form"):
    col1, col2 = st.columns([2, 1])
    with col1:
        codigo_oem = st.text_input("Código OEM del repuesto", value="641011M000")
    with col2:
        mi_precio = st.number_input("Nuestro precio ($ CLP)", value=54900, step=1000)

    boton_buscar = st.form_submit_button("ANALIZAR PRECIO COMPETIDOR")

# 6. Ejecución y render
if boton_buscar:
    codigo_limpio = codigo_oem.strip()
    if not codigo_limpio:
        st.warning("Por favor ingresa un código OEM válido.")
    else:
        with st.spinner("Escaneando catálogo del competidor..."):
            url_suggest = (
                f"https://www.msrepuestos.cl/search/suggest.json"
                f"?q={codigo_limpio}&resources[type]=product"
            )
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            }

            try:
                res = requests.get(url_suggest, headers=headers, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    productos = data.get("resources", {}).get("results", {}).get("products", [])

                    if productos:
                        prod = productos[0]
                        precio_competidor = float(prod.get("price", 0))
                        titulo_prod = html.escape(prod.get("title", "Producto encontrado"))
                        url_prod = html.escape("https://www.msrepuestos.cl" + prod.get("url", ""))

                        diferencia = mi_precio - precio_competidor
                        porcentaje = (diferencia / precio_competidor) * 100 if precio_competidor > 0 else 0

                        # Ficha del repuesto
                        st.markdown(f"""
<div class="product-card">
<div class="eyebrow">Coincidencia detectada</div>
<h3>{titulo_prod}</h3>
<a href="{url_prod}" target="_blank">Ver ficha original en la web del competidor ↗</a>
</div>
""", unsafe_allow_html=True)

                        # Métricas
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Nuestro precio", f"${mi_precio:,.0f}")
                        m2.metric("MS Repuestos", f"${precio_competidor:,.0f}")

                        # delta_color="inverse": bajar el precio vs. la competencia = verde
                        if diferencia < 0:
                            m3.metric(
                                "Posición de precio",
                                f"${abs(diferencia):,.0f} más económicos",
                                delta=f"{porcentaje:.1f}% (ventaja)",
                                delta_color="inverse",
                            )
                        else:
                            m3.metric(
                                "Posición de precio",
                                f"${diferencia:,.0f} por encima",
                                delta=f"+{porcentaje:.1f}%",
                                delta_color="inverse",
                            )

                        # Gráfico
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown('<div class="kia-section">Gráfico comparativo</div>', unsafe_allow_html=True)

                        df_grafico = pd.DataFrame({
                            "Entidad": ["Kia (nosotros)", "MS Repuestos"],
                            "Precio": [mi_precio, precio_competidor],
                        })

                        fig = px.bar(
                            df_grafico,
                            x="Entidad",
                            y="Precio",
                            text_auto="$,.0f",
                            color="Entidad",
                            color_discrete_map={
                                "Kia (nosotros)": NEGRO,
                                "MS Repuestos": ROJO,
                            },
                        )
                        fig.update_layout(
                            template="plotly_white",
                            showlegend=False,
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(family="Inter, sans-serif", size=13, color=NEGRO),
                            xaxis=dict(showgrid=False, title=""),
                            yaxis=dict(showgrid=True, gridcolor="#E5E7EB", title=""),
                            margin=dict(l=20, r=20, t=20, b=20),
                            bargap=0.55,
                        )
                        fig.update_traces(
                            textposition="outside",
                            textfont=dict(color=NEGRO, size=14),
                            marker_line_width=0,
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning(f"No se encontraron productos coincidentes para el código OEM '{codigo_limpio}'.")
                else:
                    st.error(f"Respuesta inesperada del servidor ({res.status_code}).")
            except Exception as e:
                st.error(f"Error en la ejecución de la consulta: {e}")

# 7. Footer
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
              
