import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# 1. Configuración de página
st.set_page_config(
    page_title="Kia OEM Price Monitor", 
    page_icon="🚗", 
    layout="centered"
)

# 2. Estilos CSS personalizados (Identidad Corporativa Kia)
st.markdown("""
    <style>
    /* Estilo general del fondo y fuente */
    .stApp {
        background-color: #F8F9FA;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Encabezado principal */
    .kia-header {
        background: linear-gradient(135deg, #05141F 0%, #111827 100%);
        padding: 2rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        border-bottom: 4px solid #C41425;
    }
    .kia-header h1 {
        color: #FFFFFF !important;
        font-weight: 700;
        letter-spacing: 1px;
        margin-bottom: 0.2rem;
    }
    .kia-header p {
        color: #9CA3AF;
        font-size: 0.95rem;
    }

    /* Estilo del botón de búsqueda */
    .stButton>button {
        background-color: #C41425 !important;
        color: white !important;
        font-weight: 600 !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.6rem 1.5rem !important;
        width: 100%;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #9E0F1E !important;
        box-shadow: 0 4px 8px rgba(196, 20, 37, 0.3);
    }

    /* Tarjetas de Métricas */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        border: 1px solid #E5E7EB;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Encabezado visual tipo Kia
st.markdown("""
    <div class="kia-header">
        <h1>KIA | MONITOR DE REPUESTOS</h1>
        <p>Inteligencia de Precios & Análisis Comparativo vs. Competencia</p>
    </div>
""", unsafe_allow_html=True)

# 4. Formulario de Búsqueda
with st.form("busqueda_form"):
    col_a, col_b = st.columns([2, 1])
    with col_a:
        codigo_oem = st.text_input("🔍 Código OEM Repuesto", value="641011M000")
    with col_b:
        mi_precio = st.number_input("💰 Nuestro Precio ($)", value=54900, step=1000)
    
    boton_buscar = st.form_submit_button("COMPARAR PRECIO")

# 5. Lógica de consulta e interfaz gráfica
if boton_buscar:
    codigo_limpio = codigo_oem.strip()
    if not codigo_limpio:
        st.warning("Por favor ingresa un código OEM válido.")
    else:
        with st.spinner("Consultando base de datos de competencia..."):
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
                        
                        st.markdown(f"### 📦 Repuesto: [{titulo_prod}]({url_prod})")
                        st.caption(f"OEM Referencia: **{codigo_limpio}**")
                        
                        # Tarjetas comparativas de precios
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Nuestro Precio", f"${mi_precio:,.0f}")
                        m2.metric("Competidor (MS)", f"${precio_competidor:,.0f}")
                        
                        diferencia = mi_precio - precio_competidor
                        porcentaje = (diferencia / precio_competidor) * 100 if precio_competidor > 0 else 0
                        
                        if diferencia < 0:
                            m3.metric("Diferencia", f"${abs(diferencia):,.0f} más baratos", delta=f"{porcentaje:.1f}%")
                        else:
                            m3.metric("Diferencia", f"${diferencia:,.0f} más caros", delta=f"+{porcentaje:.1f}%", delta_color="inverse")
                        
                        # Gráfico comparativo visual (Estilo Kia Plotly)
                        st.markdown("---")
                        st.subheader("📊 Comparativa Visual de Precios")
                        
                        df_grafico = pd.DataFrame({
                            "Empresa": ["Nuestra Empresa", "Competidor (MS)"],
                            "Precio ($)": [mi_precio, precio_competidor]
                        })
                        
                        fig = px.bar(
                            df_grafico, 
                            x="Empresa", 
                            y="Precio ($)",
                            text_auto="$,.0f",
                            color="Empresa",
                            color_discrete_map={
                                "Nuestra Empresa": "#05141F",
                                "Competidor (MS)": "#C41425"
                            }
                        )
                        fig.update_layout(
                            showlegend=False,
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            font=dict(family="Segoe UI, sans-serif", size=13, color="#05141F"),
                            yaxis=dict(showgrid=True, gridcolor="#E5E7EB", title="")
                        )
                        fig.update_traces(textposition="outside", marker_line_color="#05141F", marker_line_width=1)
                        st.plotly_chart(fig, use_container_width=True)

                    else:
                        st.warning(f"No se encontraron coincidencias para el código '{codigo_limpio}'.")
                else:
                    st.error(f"Error de conexión con la fuente externa ({res.status_code}).")
            except Exception as e:
                st.error(f"Error de ejecución: {e}")
