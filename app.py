import streamlit as st
import requests

# Configuración básica de la pantalla
st.set_page_config(page_title="Buscador de Precios OEM", layout="centered")

st.title("🚗 Consulta de Precios vs. Competencia")
st.write("Escribe el código OEM del repuesto para consultar el precio actual en la web del competidor.")

# Formulario de entrada de datos
with st.form("busqueda_form"):
    codigo_oem = st.text_input("🔍 Código OEM del repuesto:", value="641011M000")
    mi_precio = st.number_input("💰 Nuestro Precio ($):", value=54900, step=1000)
    boton_buscar = st.form_submit_button("Consultar Precio Competidor")

# Lógica de búsqueda al presionar el botón
if boton_buscar:
    codigo_limpio = codigo_oem.strip()
    if not codigo_limpio:
        st.warning("Por favor ingresa un código OEM válido.")
    else:
        with st.spinner(f"Buscando el código '{codigo_limpio}' en la competencia..."):
            # Consulta a la API de sugerencias de búsqueda de Shopify
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
                        
                        st.success("¡Producto encontrado!")
                        st.markdown(f"📦 **[{titulo_prod}]({url_prod})**")
                        
                        # Mostrar métricas comparativas
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Nuestro Precio", f"${mi_precio:,.0f}")
                        col2.metric("MS Repuestos", f"${precio_competidor:,.0f}")
                        
                        diferencia = mi_precio - precio_competidor
                        porcentaje = (diferencia / precio_competidor) * 100 if precio_competidor > 0 else 0
                        
                        if diferencia < 0:
                            col3.metric("Diferencia", f"${abs(diferencia):,.0f} más baratos", delta=f"{porcentaje:.1f}%")
                        else:
                            col3.metric("Diferencia", f"${diferencia:,.0f} más caros", delta=f"+{porcentaje:.1f}%", delta_color="inverse")
                    else:
                        st.warning(f"No se encontraron productos coincidentes para el código '{codigo_limpio}' en la competencia.")
                else:
                    st.error(f"Error en el servidor de la competencia ({res.status_code}).")
            except Exception as e:
                st.error(f"Error en la conexión: {e}")
