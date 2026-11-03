import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------
# 1. Configuración de la Aplicación y Tema Kia Dark
# ---------------------------------------------------------
st.set_page_config(
    page_title="Kia | Price Intelligence Hub", 
    page_icon="🚗", 
    layout="wide"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .stApp {
        background-color: #0B0E14;
        color: #F3F4F6;
    }
    
    /* Header Corporativo Kia */
    .kia-navbar {
        background: #05141F;
        border-bottom: 3px solid #C41425;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    }
    .kia-brand {
        font-size: 1.8rem;
        font-weight: 800;
        letter-spacing: 4px;
        color: #FFFFFF;
        margin: 0;
    }
    .kia-subhead {
        color: #9CA3AF;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-top: 4px;
    }
    .kia-tag {
        background: rgba(196, 20, 37, 0.15);
        color: #EF4444;
        border: 1px solid rgba(196, 20, 37, 0.4);
        padding: 0.35rem 0.8rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 1px;
    }

    /* Campos de Entrada */
    .stTextInput input, .stNumberInput input {
        background-color: #111827 !important;
        color: #FFFFFF !important;
        border: 1px solid #1F2937 !important;
        border-radius: 8px !important;
        padding: 0.6rem 1rem !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #C41425 !important;
        box-shadow: 0 0 0 1px #C41425 !important;
    }
    
    /* Botón Principal */
    .stButton>button {
        background: linear-gradient(135deg, #C41425 0%, #9E0F1E 100%) !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        letter-spacing: 1px !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.75rem 2rem !important;
        width: 100%;
        transition: all 0.2s ease-in-out;
        box-shadow: 0 4px 14px rgba(196, 20, 37, 0.4);
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(196, 20, 37, 0.6);
    }

    /* Métricas */
    [data-testid="stMetric"] {
        background: #111827;
        padding: 1.25rem;
        border-radius: 12px;
        border: 1px solid #1F2937;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    [data-testid="stMetricLabel"] {
        color: #9CA3AF !important;
        font-size: 0.85rem !important;
    }
    [data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* Tarjetas de Producto */
    .product-card {
        background: #111827;
        border: 1px solid #1F2937;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. Configuración de Competidores
# ---------------------------------------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Tiendas basadas en Shopify u otras plataformas
COMPETIDORES_SHOPIFY = [
    {
        "nombre": "MS Repuestos",
        "url_base": "https://www.msrepuestos.cl"
    }
    # Agrega más tiendas Shopify aquí siguiendo este mismo formato
]

# ---------------------------------------------------------
# 3. Funciones de Extracción por Plataforma
# ---------------------------------------------------------
def consultar_shopify(competidor, codigo_oem):
    """Búsqueda Ajax en tiendas basadas en Shopify."""
    url = f"{competidor['url_base']}/search/suggest.json?q={codigo_oem}&resources[type]=product"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=7)
        if resp.status_code == 200:
            data = resp.json()
            prods = data.get("resources", {}).get("results", {}).get("products", [])
            if prods:
                p = prods[0]
                url_final = competidor["url_base"] + p.get("url", "")
                return {
                    "Competidor": competidor["nombre"],
                    "Estado": "Encontrado",
                    "Producto": p.get("title", "Sin título"),
                    "Precio": float(p.get("price", 0)),
                    "URL": url_final
                }
    except Exception:
        pass
    
    return {
        "Competidor": competidor["nombre"],
        "Estado": "Sin coincidencia",
        "Producto": "N/A",
        "Precio": None,
        "URL": "#"
    }

def consultar_mercadolibre(codigo_oem, site_id="MLC"):
    """
    Búsqueda profunda en Mercado Libre (Indexa Ficha Técnica y Atributos OEM).
    Toma la opción con menor precio entre los vendedores activos.
    """
    url = f"https://api.mercadolibre.com/sites/{site_id}/search?q={codigo_oem}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=7)
        if resp.status_code == 200:
            data = resp.json()
            resultados = data.get("results", [])
            
            # Filtrar productos con precio válido
            productos_validos = [p for p in resultados if p.get("price")]
            if productos_validos:
                # Ordenar por menor precio
                productos_validos.sort(key=lambda x: x["price"])
                mejor_opcion = productos_validos[0]
                cant_vendedores = len(productos_validos)
                
                titulo = f"{mejor_opcion.get('title')} ({cant_vendedores} vendedor{'es' if cant_vendedores > 1 else ''} en MeLi)"
                
                return {
                    "Competidor": "Mercado Libre",
                    "Estado": "Encontrado",
                    "Producto": titulo,
                    "Precio": float(mejor_opcion.get("price")),
                    "URL": mejor_opcion.get("permalink", "#")
                }
    except Exception:
        pass

    return {
        "Competidor": "Mercado Libre",
        "Estado": "Sin coincidencia",
        "Producto": "N/A",
        "Precio": None,
        "URL": "#"
    }

def obtener_datos_paralelo(codigo_oem):
    """Ejecuta todas las llamadas en paralelo para máxima velocidad."""
    resultados = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = []
        
        # 1. Llamada a Mercado Libre
        futures.append(executor.submit(consultar_mercadolibre, codigo_oem))
        
        # 2. Llamadas a tiendas Shopify
        for comp in COMPETIDORES_SHOPIFY:
            futures.append(executor.submit(consultar_shopify, comp, codigo_oem))
        
        for future in as_completed(futures):
            resultados.append(future.result())
            
    return resultados

# ---------------------------------------------------------
# 4. Interface Gráfica Streamlit
# ---------------------------------------------------------
st.markdown("""
    <div class="kia-navbar">
        <div>
            <div class="kia-brand">K I A</div>
            <div class="kia-subhead">PARTS PRICE INTELLIGENCE HUB</div>
        </div>
        <div class="kia-tag">MULTI-COMPETITOR TRACKER</div>
    </div>
""", unsafe_allow_html=True)

st.markdown("##### 🔍 Consulta Multi-Mercado de Repuestos")

with st.form("busqueda_form"):
    col1, col2 = st.columns([2, 1])
    with col1:
        codigo_oem = st.text_input("Código OEM del Repuesto", value="93575-1Y000")
    with col2:
        mi_precio = st.number_input("Nuestro Precio ($ CLP)", value=54900, step=1000)
    
    boton_buscar = st.form_submit_button("ESCANEAR TODO EL MERCADO")

# ---------------------------------------------------------
# 5. Ejecución del Escaneo y Presentación de Datos
# ---------------------------------------------------------
if boton_buscar:
    codigo_limpio = codigo_oem.strip()
    if not codigo_limpio:
        st.warning("Por favor ingresa un código OEM válido.")
    else:
        with st.spinner("Escaneando Mercado Libre y tiendas del sector en paralelo..."):
            resultados = obtener_datos_paralelo(codigo_limpio)
            df_resultados = pd.DataFrame(resultados)
            
            # Filtrar competidores donde sí se encontró el repuesto
            df_encontrados = df_resultados[df_resultados["Precio"].notnull()].copy()
            
            if not df_encontrados.empty:
                precio_minimo = df_encontrados["Precio"].min()
                diferencia_min = mi_precio - precio_minimo
                pct_min = (diferencia_min / precio_minimo) * 100 if precio_minimo > 0 else 0
                
                # Fila de Métricas Principales
                m1, m2, m3 = st.columns(3)
                m1.metric("Nuestro Precio (Kia)", f"${mi_precio:,.0f}")
                m2.metric("Mínimo del Mercado", f"${precio_minimo:,.0f}")
                
                if diferencia_min <= 0:
                    m3.metric("Posición de Precio", f"${abs(diferencia_min):,.0f} más bajo", delta=f"{pct_min:.1f}% (Mejor Opción)")
                else:
                    m3.metric("Posición de Precio", f"${diferencia_min:,.0f} por encima", delta=f"+{pct_min:.1f}%", delta_color="inverse")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Gráfico y Detalle en Dos Columnas
                col_chart, col_list = st.columns([1.2, 1])
                
                with col_chart:
                    st.markdown("##### 📈 Comparativa de Precios por Competidor")
                    
                    filas_grafico = [{"Entidad": "Kia (Nosotros)", "Precio": mi_precio, "Tipo": "Propio"}]
                    for _, row in df_encontrados.iterrows():
                        filas_grafico.append({
                            "Entidad": row["Competidor"],
                            "Precio": row["Precio"],
                            "Tipo": "Competencia"
                        })
                    df_chart = pd.DataFrame(filas_grafico)
                    
                    fig = px.bar(
                        df_chart, 
                        x="Entidad", 
                        y="Precio",
                        text_auto="$,.0f",
                        color="Tipo",
                        color_discrete_map={
                            "Propio": "#3B82F6",
                            "Competencia": "#C41425"
                        }
                    )
                    fig.update_layout(
                        showlegend=False,
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter, sans-serif", size=13, color="#9CA3AF"),
                        xaxis=dict(showgrid=False, title=""),
                        yaxis=dict(showgrid=True, gridcolor="#1F2937", title=""),
                        margin=dict(l=10, r=10, t=10, b=10)
                    )
                    fig.update_traces(
                        textposition="outside",
                        textfont=dict(color="#FFFFFF", size=13)
                    )
                    st.plotly_chart(fig, use_container_width=True)
