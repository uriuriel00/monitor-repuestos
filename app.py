import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# 1. Configuración de página
st.set_page_config(page_title="Kia | Price Intelligence Hub", page_icon="🚗", layout="wide")

# 2. Estilos CSS (Kia Dark)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #0B0E14; color: #F3F4F6; }
    .kia-navbar { background: #05141F; border-bottom: 3px solid #C41425; padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: center; }
    .kia-brand { font-size: 1.8rem; font-weight: 800; letter-spacing: 4px; color: #FFFFFF; margin: 0; }
    .stButton>button { background: linear-gradient(135deg, #C41425 0%, #9E0F1E 100%) !important; color: #FFFFFF !important; border: none !important; border-radius: 8px !important; padding: 0.75rem 2rem !important; width: 100%; font-weight: 700; }
    [data-testid="stMetric"] { background: #111827; padding: 1.25rem; border-radius: 12px; border: 1px solid #1F2937; }
    .product-card { background: #111827; border: 1px solid #1F2937; border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem; }
    .badge-oem { background: rgba(16, 185, 129, 0.2); color: #10B981; border: 1px solid #10B981; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

# 3. Encabezado
st.markdown("""
    <div class="kia-navbar">
        <div>
            <div class="kia-brand">K I A</div>
            <div style="color: #9CA3AF; font-size: 0.8rem; text-transform: uppercase;">MULTI-COMPETITOR PRICE INTELLIGENCE HUB</div>
        </div>
        <div style="background: rgba(196, 20, 37, 0.15); color: #EF4444; border: 1px solid rgba(196, 20, 37, 0.4); padding: 0.35rem 0.8rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600;">LIVE TRACKER (MS + MERCADO LIBRE)</div>
    </div>
""", unsafe_allow_html=True)

# 4. Formulario de Búsqueda
st.markdown("##### 🔍 Consulta de Coincidencia de Precios")
with st.form("busqueda_form"):
    col1, col2 = st.columns([2, 1])
    with col1:
        codigo_oem_input = st.text_input("Código OEM del Repuesto", value="93575-1Y000")
    with col2:
        mi_precio = st.number_input("Nuestro Precio ($ CLP)", value=25900, step=1000)
    
    boton_buscar = st.form_submit_button("ANALIZAR COMPETIDORES")

# 5. Función de búsqueda e inspección de Ficha Técnica en Mercado Libre
def buscar_mercadolibre_por_ficha(raw_code):
    clean_code = raw_code.replace("-", "").replace(" ", "").upper()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    queries = [raw_code, clean_code, f"Kia {raw_code}", f"Kia {clean_code}"]
    candidatos = []
    
    for q in queries:
        try:
            url = f"https://api.mercadolibre.com/sites/MLC/search?q={q}"
            res = requests.get(url, headers=headers, timeout=6)
            if res.status_code == 200:
                results = res.json().get("results", [])
                if results:
                    candidatos.extend(results)
                    break
        except Exception:
            continue

    prod_seleccionado = None
    oem_verificado = False
    
    # Inspección de atributos (Ficha técnica)
    for item in candidatos:
        attributes = item.get("attributes", [])
        for attr in attributes:
            val_attr = str(attr.get("value_name", "")).replace("-", "").replace(" ", "").upper()
            if clean_code in val_attr and len(clean_code) > 3:
                prod_seleccionado = item
                oem_verificado = True
                break
        if oem_verificado:
            break
            
    if not prod_seleccionado and candidatos:
        prod_seleccionado = candidatos[0]
        
    return prod_seleccionado, oem_verificado, headers

# 6. Ejecución del análisis
if boton_buscar:
    raw_code = codigo_oem_input.strip()
    clean_code = raw_code.replace("-", "").replace(" ", "")
    
    if not raw_code:
        st.warning("Por favor ingresa un código OEM válido.")
    else:
        with st.spinner("Escaneando catálogos y fichas técnicas..."):
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            
            # --- MS REPUESTOS ---
            precio_ms, titulo_ms, url_ms = None, None, None
            try:
                url_ms_suggest = f"https://www.msrepuestos.cl/search/suggest.json?q={clean_code}&resources[type]=product"
                res_ms = requests.get(url_ms_suggest, headers=headers, timeout=8)
                if res_ms.status_code == 200:
                    prods_ms = res_ms.json().get("resources", {}).get("results", {}).get("products", [])
                    if prods_ms:
                        prod_ms = prods_ms[0]
                        precio_ms = float(prod_ms.get("price", 0))
                        titulo_ms = prod_ms.get("title", "Producto MS")
                        url_ms = "https://www.msrepuestos.cl" + prod_ms.get("url", "")
            except Exception as e:
                st.error(f"Error en MS Repuestos: {e}")

            # --- MERCADO LIBRE ---
            precio_meli, titulo_meli, url_meli = None, None, None
            vendedor_nombre = "Mercado Libre"
            
            prod_sel, es_verificado, meli_headers = buscar_mercadolibre_por_ficha(raw_code)

            if prod_sel:
                s_id = prod_sel.get("seller", {}).get("id")
                if s_id:
                    try:
                        u_res = requests.get(f"https://api.mercadolibre.com/users/{s_id}", headers=meli_headers, timeout=4)
                        if u_res.status_code == 200:
                            nick = u_res.json().get("nickname", "")
                            if nick:
                                vendedor_nombre = f"MeLi ({nick})"
                    except Exception:
                        vendedor_nombre = f"MeLi (ID: {s_id})"

                precio_meli = float(prod_sel.get("price", 0))
                titulo_meli = prod_sel.get("title", "Producto MeLi")
                url_meli = prod_sel.get("permalink", "")

            # --- PRESENTACIÓN DE RESULTADOS ---
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 📦 Coincidencias Detectadas")
            
            c_info1, c_info2 = st.columns(2)
            with c_info1:
                if precio_ms:
                    st.markdown(f"""
                        <div class="product-card">
                            <span style="color: #EF4444; font-size: 0.75rem; font-weight: 700;">MS REPUESTOS</span>
                            <h4 style="color: #FFFFFF; margin: 4px 0;">{titulo_ms}</h4>
                            <a href="{url_ms}" target="_blank" style="color: #9CA3AF; font-size: 0.85rem;">Ver en sitio web ↗</a>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning("Sin coincidencia en MS Repuestos")

            with c_info2:
                if precio_meli:
                    badge_html = '<span class="badge-oem">OEM Verificado en Ficha Técnica</span>' if es_verificado else ''
                    st.markdown(f"""
                        <div class="product-card">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="color: #F59E0B; font-size: 0.75rem; font-weight: 700;">{vendedor_nombre.upper()}</span>
                                {badge_html}
                            </div>
                            <h4 style="color: #FFFFFF; margin: 6px 0 4px 0;">{titulo_meli}</h4>
                            <a href="{url_meli}" target="_blank" style="color: #9CA3AF; font-size: 0.85rem;">Ver publicación original ↗</a>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning("Sin coincidencia detectada en Mercado Libre.")

            # --- MÉTRICAS ---
            st.markdown("<br>", unsafe_allow_html=True)
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

            # --- GRÁFICO COMPARATIVO ---
            datos_grafico = [{"Entidad": "Kia (Nosotros)", "Precio": mi_precio}]
            color_map = {"Kia (Nosotros)": "#3B82F6"}
            
            if precio_ms:
                datos_grafico.append({"Entidad": "MS Repuestos", "Precio": precio_ms})
                color_map["MS Repuestos"] = "#C41425"
            if precio_meli:
                datos_grafico.append({"Entidad": vendedor_nombre, "Precio": precio_meli})
                color_map[vendedor_nombre] = "#F59E0B"
                
            df_grafico = pd.DataFrame(datos_grafico)
            
            fig = px.bar(df_grafico, x="Entidad", y="Precio", text_auto="$,.0f", color="Entidad", color_discrete_map=color_map)
            fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#9CA3AF"))
            fig.update_traces(textposition="outside", textfont=dict(color="#FFFFFF"))
            st.plotly_chart(fig, use_container_width=True)
