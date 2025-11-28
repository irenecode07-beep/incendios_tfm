import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import zipfile

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Incendios Coruña", layout="wide")
st.title("🔥 Análisis de Incendios en A Coruña")
st.markdown("Esta aplicación muestra la ubicación de los incendios en la provincia.")

# --- 2. CARGA DE DATOS OPTIMIZADA (MEMORIA Y CACHÉ) ---
@st.cache_data
def cargar_datos_coruna():
    """
    Lee el ZIP, extrae solo columnas necesarias y filtra por Coruña (15).
    Usa caché para que esto solo se ejecute una vez y vaya rápido.
    """
    # Solo leemos lo necesario para ahorrar memoria RAM
    cols = ['fecha', 'lat', 'lng', 'municipio', 'superficie', 'idprovincia']
    archivo_zip = 'fires-all.csv.zip'
    
    try:
        with zipfile.ZipFile(archivo_zip) as z:
            # Truco para evitar la carpeta __MACOSX oculta
            nombre_csv = [f for f in z.namelist() if f.endswith('.csv') and '__MACOSX' not in f][0]
            
            with z.open(nombre_csv) as f:
                df = pd.read_csv(f, usecols=cols, parse_dates=['fecha'], index_col='fecha')
                
        # Filtramos por A Coruña (ID 15) y devolvemos solo eso
        return df[df['idprovincia'] == 15].copy()
        
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame() # Devuelve vacío si falla

# Cargamos los datos
df_coruna = cargar_datos_coruna()

# Si no hay datos, paramos aquí
if df_coruna.empty:
    st.stop()

# --- 3. FILTROS INTERACTIVOS ---
# Barra lateral para elegir el año (mucho mejor que cambiar el código a mano)
anos_disponibles = sorted(df_coruna.index.year.unique())
ano_seleccionado = st.sidebar.selectbox("Selecciona un año:", anos_disponibles, index=len(anos_disponibles)-1)

# Filtramos los datos por el año elegido
df_filtrado = df_coruna[df_coruna.index.year == ano_seleccionado]
# Limpiamos los que no tienen coordenadas
df_mapa = df_filtrado.dropna(subset=['lat', 'lng'])

# --- 4. GENERACIÓN DEL MAPA ---
st.subheader(f"📍 Mapa de Incendios - Año {ano_seleccionado}")
st.write(f"Se encontraron **{len(df_mapa)}** incendios geolocalizados en este periodo.")

if not df_mapa.empty:
    # A. Centramos el mapa
    centro = [df_mapa['lat'].mean(), df_mapa['lng'].mean()]
    m = folium.Map(location=centro, zoom_start=9, tiles='CartoDB Voyager')

    # B. Pintamos los puntos (OPTIMIZACIÓN: Si son más de 1000, limitamos para no colgar el navegador)
    limit = 2000
    if len(df_mapa) > limit:
        st.warning(f"⚠️ Hay muchos incendios ({len(df_mapa)}). Mostrando solo los primeros {limit} para mantener la fluidez.")
        df_mapa = df_mapa.head(limit)

    for index, row in df_mapa.iterrows():
        # HTML en el popup para que se vea bonito
        info = f"""
        <b>Municipio:</b> {row['municipio']}<br>
        <b>Superficie:</b> {row['superficie']} ha<br>
        <b>Fecha:</b> {index.date()}
        """
        
        folium.CircleMarker(
            location=[row['lat'], row['lng']],
            radius=3,
            popup=folium.Popup(info, max_width=200),
            color="#d63031",      # Rojo oscuro borde
            fill=True,
            fill_color="#ff7675", # Rojo claro relleno
            fill_opacity=0.7
        ).add_to(m)

    # C. MOSTRAR EL MAPA (¡IMPORTANTE: ESTO VA FUERA DEL BUCLE!)
    st_folium(m, width=1000, height=600)

else:
    st.info("No hay datos de ubicación para el año seleccionado.")
