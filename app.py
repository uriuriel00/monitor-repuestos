import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------
# 1. Configuración de página
# ---------------------------------------------------------
st.set_page_config(
    page_title="Kia | Price Intelligence Hub", 
    page_icon="🚗", 
    layout="wide"
)

# ---------------------------------------------------------
# 2. Inyección de CSS Personalizado (Estética Kia Dark)
# ---------------------------------------------------------
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

    .stTextInput input, .stNumberInput input {
        background-color: #111827 !important;
        color: #FFFFFF !important;
        border: 1px solid #1F2937 !important;
        border-radius: 8px !important;
        padding: 0.6rem 1rem !important;
    }
    
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
# 3. Configuración del Catálogo de Competidores
# ---------------------------------------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

COMPETIDORES = [
    {
        "nombre": "MS Repuestos",
        "tipo": "shopify",
        "url_base": "https://www.msrepuestos.cl"
    },
    {
        "nombre": "Competidor B (Ejemplo Shopify)",
        "tipo": "shopify",
        "url_base": "https://tiendaejemplo.cl" # Reemplazar con URL real de tienda Shopify
    },
    # Agrega aquí más competidores que usen Shopify o APIs personalizadas
]

# ---------------------------------------------------------
# 4. Funciones de Extracción Móduclares & Concurrencia
# ---------------------------------------------------------
def consultar_shopify(competidor, codigo_oem):
    """Consulta la API Ajax estándar de tiendas construidas sobre Shopify."""
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
        "Estado": "No disponible / Sin stock",
        "Producto": "N/A",
        "Precio": None,
        "URL": "#"
    }

def obtener_datos_competidores_paralelo(codigo_oem):
    """Ejecuta consultas concurrentes para no bloquear la interfaz."""
    resultados = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for comp in COMPETIDORES:
            if comp["tipo"] == "shopify":
                futures.append(executor.submit(consultar_shopify, comp, codigo_oem))
        
        for future in as_completed(futures):
            resultados.append(future.result())
            
    return resultados

# ---------------------------------------------------------
# 5. Encabezado Corporativo
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

# ---------------------------------------------------------
# 6. Formulario de Búsqueda
# ---------------------------------------------------------
st.markdown("##### 🔍 Consulta Multi-Mercado de Repuestos")

with st.form("busqueda_form"):
    col1, col2 = st.columns([2, 1])
    with col1:
        codigo_oem = st.text_input("Código OEM del Repuesto", value="641011M000")
    with col2:
        mi_precio = st.number_input("Nuestro Precio ($ CLP)", value=54900, step=1000)
    
    boton_buscar = st.form_submit_button("ESCANEAR TODO EL MERCADO")

# ---------------------------------------------------------
# 7. Procesamiento y Resultados
# ---------------------------------------------------------
if boton_buscar:
    codigo_limpio = codigo_oem.strip()
    if not codigo_limpio:
        st.warning("Por favor ingresa un código OEM válido.")
    else:
        with st.spinner("Escaneando catálogos de competidores en paralelo..."):
            resultados = obtener_datos_competidores_paralelo(codigo_limpio)
            df_resultados = pd.DataFrame(resultados)
            
            # Filtrar competidores con coincidencia
            df_encontrados = df_resultados[df_resultados["Precio"].notnull()].copy()
            
            if not df_encontrados.empty:
                precio_minimo = df_encontrados["Precio"].min()
                precio_promedio = df_encontrados["Precio"].mean()
                diferencia_min = mi_precio - precio_minimo
                pct_min = (diferencia_min / precio_minimo) * 100 if precio_minimo > 0 else 0
                
                # Métricas Resumen
                m1, m2, m3 = st.columns(3)
                m1.metric("Nuestro Precio (Kia)", f"${mi_precio:,.0f}")
                m2.metric("Mínimo del Mercado", f"${precio_minimo:,.0f}")
                
                if diferencia_min <= 0:
                    m3.metric("Posición de Liderazgo", f"${abs(diferencia_min):,.0f} más bajo", delta=f"{pct_min:.1f}% (Mejor opción)")
                else:
                    m3.metric("Brecha vs Mínimo", f"${diferencia_min:,.0f} por encima", delta=f"+{pct_min:.1f}%", delta_color="inverse")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Gráfico Comparativo Multicompetidor
                col_chart, col_list = st.columns([1.2, 1])
                
                with col_chart:
                    st.markdown("##### 📈 Comparativa de Precios por Competidor")
                    
                    # Estructurar DataFrame para Plotly
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
                
                with col_list:
                    st.markdown("##### 🛒 Detalle por Tienda")
                    for _, r in df_resultados.iterrows():
                        if r["Precio"] is not None:
                            st.markdown(f"""
                                <div class="product-card">
                                    <div style="display: flex; justify-content: space-between; align-items: center;">
                                        <strong style="color: #FFFFFF;">{r['Competidor']}</strong>
                                        <span style="color: #EF4444; font-weight: 700;">${r['Precio']:,.0f}</span>
                                    </div>
                                    <div style="color: #9CA3AF; font-size: 0.85rem; margin-top: 4px;">{r['Producto']}</div>
                                    <a href="{r['URL']}" target="_blank" style="color: #60A5FA; font-size: 0.8rem; text-decoration: none;">Ver repuesto ↗</a>
                                </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                                <div class="product-card" style="opacity: 0.5;">
                                    <div style="display: flex; justify-content: space-between;">
                                        <strong style="color: #9CA3AF;">{r['Competidor']}</strong>
                                        <span style="color: #6B7280;">Sin Coincidencia</span>
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)
            else:
                st.warning(f"No se encontraron coincidencias para el código OEM '{codigo_limpio}' en ninguno de los competidores registrados.")
