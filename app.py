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

    /* Contenedores de Ficha Producto */
    .product-card {
        background: #111827;
        border: 1px solid #1F2937;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Encabezado corporativo
st.markdown("""
    <div class="kia-navbar">
        <div>
            <div class="kia-brand">K I A</div>
            <div class="kia-subhead">MULTI-COMPETITOR PRICE INTELLIGENCE HUB</div>
        </div>
        <div class="kia-tag">LIVE TRACKER (MS + MERCADO LIBRE)</div>
    </div>
""", unsafe_allow_html=True)

# 4. Formulario de Búsqueda Multi-Competidor
st.markdown("##### 🔍 Consulta de Coincidencia de Precios")

with st.form("busqueda_form"):
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        codigo_oem = st.text_input("Código OEM del Repuesto", value="641011M000")
    with col2:
        mi_precio = st.number_input("Nuestro Precio ($ CLP)", value=54900, step=1000)
    with col3:
        vendedor_meli_filtro = st.text_input("Vendedor MeLi (Opcional)", value="", placeholder="Ej: REPUESTOS_EXPRESS")
    
    boton_buscar = st.form_submit_button("ANALIZAR COMPETIDORES")

# 5. Ejecución y Renderizado
if boton_buscar:
    codigo_limpio = codigo_oem.strip()
    if not codigo_limpio:
        st.warning("Por favor ingresa un código OEM válido.")
    else:
        with st.spinner("Escaneando catálogos de MS Repuestos y Mercado Libre..."):
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            # --- COMPETIDOR 1: MS REPUESTOS (Shopify API) ---
            precio_ms = None
            titulo_ms = None
            url_ms = None
            
            try:
                url_ms_suggest = f"https://www.msrepuestos.cl/search/suggest.json?q={codigo_limpio}&resources[type]=product"
                res_ms = requests.get(url_ms_suggest, headers=headers, timeout=10)
                if res_ms.status_code == 200:
                    prods_ms = res_ms.json().get("resources", {}).get("results", {}).get("products", [])
                    if prods_ms:
                        prod_ms = prods_ms[0]
                        precio_ms = float(prod_ms.get("price", 0))
                        titulo_ms = prod_ms.get("title", "Producto MS")
                        url_ms = "https://www.msrepuestos.cl" + prod_ms.get("url", "")
            except Exception as e:
                st.error(f"Error al consultar MS Repuestos: {e}")

            # --- COMPETIDOR 2: MERCADO LIBRE CHILE (MLC API) ---
            precio_meli = None
            titulo_meli = None
            url_meli = None
            vendedor_nombre = "Mercado Libre"
            
            try:
                url_meli_search = f"https://api.mercadolibre.com/sites/MLC/search?q={codigo_limpio}"
                res_meli = requests.get(url_meli_search, headers=headers, timeout=10)
                if res_meli.status_code == 200:
                    prods_meli = res_meli.json().get("results", [])
                    if prods_meli:
                        prod_seleccionado = None
                        
                        # Si el usuario especificó un vendedor, buscar coincidencia
                        if vendedor_meli_filtro.strip():
                            filtro_str = vendedor_meli_filtro.strip().lower()
                            for item in prods_meli:
                                nickname = item.get("seller", {}).get("nickname", "").lower()
                                if filtro_str in nickname:
                                    prod_seleccionado = item
                                    vendedor_nombre = f"MeLi ({item.get('seller', {}).get('nickname')})"
                                    break
                        
                        # Si no hay filtro o no se encontró el vendedor específico, tomar el primer resultado (mejor/más relevante)
                        if not prod_seleccionado:
                            prod_seleccionado = prods_meli[0]
                            seller_nick = prod_seleccionado.get("seller", {}).get("nickname", "Vendedor MeLi")
                            vendedor_nombre = f"MeLi ({seller_nick})"
                        
                        precio_meli = float(prod_seleccionado.get("price", 0))
                        titulo_meli = prod_seleccionado.get("title", "Producto MeLi")
                        url_meli = prod_seleccionado.get("permalink", "")
            except Exception as e:
                st.error(f"Error al consultar Mercado Libre: {e}")

            # --- DESPLIEGUE DE RESULTADOS ---
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 📦 Coincidencias Detectadas")
            
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                if precio_ms:
                    st.markdown(f"""
                        <div class="product-card">
                            <span style="color: #EF4444; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">MS Repuestos</span>
                            <h4 style="color: #FFFFFF; margin-top: 4px; margin-bottom: 6px; font-size: 1rem;">{titulo_ms}</h4>
                            <a href="{url_ms}" target="_blank" style="color: #9CA3AF; text-decoration: none; font-size: 0.85rem;"> Ver en sitio web ↗</a>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning("Sin coincidencia en MS Repuestos")

            with col_info2:
                if precio_meli:
                    st.markdown(f"""
                        <div class="product-card">
                            <span style="color: #F59E0B; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">{vendedor_nombre}</span>
                            <h4 style="color: #FFFFFF; margin-top: 4px; margin-bottom: 6px; font-size: 1rem;">{titulo_meli}</h4>
                            <a href="{url_meli}" target="_blank" style="color: #9CA3AF; text-decoration: none; font-size: 0.85rem;"> Ver en Mercado Libre ↗</a>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning("Sin coincidencia en Mercado Libre")

            # --- MÉTRICAS COMPARATIVAS ---
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 💰 Comparativa de Precios")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Kia (Nuestro Precio)", f"${mi_precio:,.0f}")
            
            if precio_ms:
                dif_ms = mi_precio - precio_ms
                pct_ms = (dif_ms / precio_ms) * 100
                m2.metric("MS Repuestos", f"${precio_ms:,.0f}", delta=f"{pct_ms:+.1f}% vs Kia", delta_color="inverse" if dif_ms > 0 else "normal")
            else:
                m2.metric("MS Repuestos", "N/D")
                
            if precio_meli:
                dif_meli = mi_precio - precio_meli
                pct_meli = (dif_meli / precio_meli) * 100
                m3.metric(vendedor_nombre, f"${precio_meli:,.0f}", delta=f"{pct_meli:+.1f}% vs Kia", delta_color="inverse" if dif_meli > 0 else "normal")
            else:
                m3.metric("Mercado Libre", "N/D")

            # --- GRÁFICO COMPARATIVO VISUAL ---
            datos_grafico = [{"Entidad": "Kia (Nosotros)", "Precio": mi_precio}]
            color_map = {"Kia (Nosotros)": "#3B82F6"}
            
            if precio_ms:
                datos_grafico.append({"Entidad": "MS Repuestos", "Precio": precio_ms})
                color_map["MS Repuestos"] = "#C41425"
                
            if precio_meli:
                datos_grafico.append({"Entidad": vendedor_nombre, "Precio": precio_meli})
                color_map[vendedor_nombre] = "#F59E0B"
                
            df_grafico = pd.DataFrame(datos_grafico)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 📈 Gráfico Comparativo Multi-Competidor")
            
            fig = px.bar(
                df_grafico, 
                x="Entidad", 
                y="Precio",
                text_auto="$,.0f",
                color="Entidad",
                color_discrete_map=color_map
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
