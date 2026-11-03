import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# 1. Configuración de página
st.set_page_config(
    page_title="Kia | Price Intelligence Hub", 
    page_icon="🚗", 
    layout="wide"
)

# 2. Inyección de CSS Personalizado (Estética Kia Dark)
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
    
    /* Header Kia Corporate */
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

    /* Entradas del Formulario */
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

    /* Tarjetas de Métricas */
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
        font-weight: 500;
        letter-spacing: 0.5px;
    }
    [data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* Contenedor Ficha Producto */
    .product-card {
        background: #111827;
        border: 1px solid #1F2937;
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1.5rem;
        margin-bottom: 1.5rem;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Encabezado corporativo
st.markdown("""
    <div class="kia-navbar">
        <div>
            <div class="kia-brand">K I A</div>
            <div class="kia-subhead">PARTS PRICE INTELLIGENCE HUB</div>
        </div>
        <div class="kia-tag">LIVE COMPETITOR TRACKER</div>
    </div>
""", unsafe_allow_html=True)

# 4. Formulario de Búsqueda
st.markdown("##### 🔍 Consulta de Coincidencia de Precios")

with st.form("busqueda_form"):
    col1, col2 = st.columns([2, 1])
    with col1:
        codigo_oem = st.text_input("Código OEM del Repuesto", value="641011M000")
    with col2:
        mi_precio = st.number_input("Nuestro Precio ($ CLP)", value=54900, step=1000)
    
    boton_buscar = st.form_submit_button("ANALIZAR PRECIO COMPETIDOR")

# 5. Ejecución y Renderizado
if boton_buscar:
    codigo_limpio = codigo_oem.strip()
    if not codigo_limpio:
        st.warning("Por favor ingresa un código OEM válido.")
    else:
        with st.spinner("Escaneando catálogo del competidor en tiempo real..."):
            url_suggest = f"https://www.msrepuestos.cl/search/suggest.json?q={codigo_limpio}&resources[type]=product"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            try:
                res = requests.get(url_suggest, headers=headers, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    productos = data.get("resources", {}).get("results", {}).get("products", [])
                    
                    if productos:
                        prod = productos[0]
                        precio_competidor = float(prod.get("price", 0))
                        titulo_prod = prod.get("title", "Producto encontrado")
                        url_prod = "https://www.msrepuestos.cl" + prod.get("url", "")
                        
                        diferencia = mi_precio - precio_competidor
                        porcentaje = (diferencia / precio_competidor) * 100 if precio_competidor > 0 else 0
                        
                        # Ficha del Repuesto
                        st.markdown(f"""
                            <div class="product-card">
                                <span style="color: #9CA3AF; font-size: 0.8rem; text-transform: uppercase;">Coincidencia Detectada</span>
                                <h3 style="color: #FFFFFF; margin-top: 4px; margin-bottom: 8px;">{titulo_prod}</h3>
                                <a href="{url_prod}" target="_blank" style="color: #EF4444; text-decoration: none; font-size: 0.9rem; font-weight: 600;"> Ver ficha original en la web del competidor ↗</a>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        # Métricas Comparativas
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Nuestro Precio", f"${mi_precio:,.0f}")
                        m2.metric("MS Repuestos", f"${precio_competidor:,.0f}")
                        
                        if diferencia < 0:
                            m3.metric("Posición de Precio", f"${abs(diferencia):,.0f} más económicos", delta=f"{porcentaje:.1f}% (Ventaja)")
                        else:
                            m3.metric("Posición de Precio", f"${diferencia:,.0f} por encima", delta=f"+{porcentaje:.1f}%", delta_color="inverse")
                        
                        # Gráfico Interactivo Visual
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown("##### 📈 Gráfico Comparativo")
                        
                        df_grafico = pd.DataFrame({
                            "Entidad": ["Kia (Nosotros)", "Competencia (MS)"],
                            "Precio": [mi_precio, precio_competidor]
                        })
                        
                        fig = px.bar(
                            df_grafico, 
                            x="Entidad", 
                            y="Precio",
                            text_auto="$,.0f",
                            color="Entidad",
                            color_discrete_map={
                                "Kia (Nosotros)": "#3B82F6",
                                "Competencia (MS)": "#C41425"
                            }
                        )
                        fig.update_layout(
                            showlegend=False,
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(family="Inter, sans-serif", size=13, color="#9CA3AF"),
                            xaxis=dict(showgrid=False, title=""),
                            yaxis=dict(showgrid=True, gridcolor="#1F2937", title=""),
                            margin=dict(l=20, r=20, t=20, b=20)
                        )
                        fig.update_traces(
                            textposition="outside",
                            textfont=dict(color="#FFFFFF", size=14),
                            marker_line_width=0
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning(f"No se encontraron productos coincidentes para el código OEM '{codigo_limpio}'.")
                else:
                    st.error(f"Respuesta inesperada del servidor ({res.status_code}).")
            except Exception as e:
                st.error(f"Error en la ejecución de la consulta: {e}")
