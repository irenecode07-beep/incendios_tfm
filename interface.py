import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, HeatMap, Fullscreen
from streamlit_folium import st_folium
import zipfile
import plotly.express as px

# ------------------------------------------------------
# 1. CONFIGURACIÓN DE LA PÁGINA
# ------------------------------------------------------
st.set_page_config(
    page_title="Monitor de Incendios Forestales",
    page_icon="🔥",
    layout="wide"
)

# ------------------------------------------------------
# 2. CARGA DE DATOS INTELIGENTE
# ------------------------------------------------------

@st.cache_data
def cargar_maestros():
    """Carga master_data.xlsx para traducir códigos a texto."""
    archivo_meta = 'master_data.xlsx'
    maestros = {}
    
    try:
        df_meta = pd.read_excel(archivo_meta)
        
        # Diccionarios de mapeo (asegurando limpieza)
        if {'idcomunidad', 'comunidad'}.issubset(df_meta.columns):
            temp = df_meta[['idcomunidad', 'comunidad']].dropna()
            maestros['comunidades'] = dict(zip(temp['idcomunidad'], temp['comunidad']))
            
        if {'idprovincia', 'provincia'}.issubset(df_meta.columns):
            temp = df_meta[['idprovincia', 'provincia']].dropna()
            maestros['provincias'] = dict(zip(temp['idprovincia'], temp['provincia']))
            
        if {'causa', 'causa_label'}.issubset(df_meta.columns):
            temp = df_meta[['causa', 'causa_label']].dropna()
            maestros['causas'] = dict(zip(temp['causa'], temp['causa_label']))
            
    except Exception as e:
        st.warning(f"⚠️ No se pudo cargar master_data.xlsx: {e}")
        return {}
        
    return maestros

@st.cache_data
def cargar_datos():
    """Carga y limpia los datos automáticamente desde el ZIP local."""
    archivo_zip = 'fires-all.csv.zip'
    
    try:
        # 1. Cargar diccionarios
        diccionarios = cargar_maestros()
        
        # 2. Abrir ZIP
        with zipfile.ZipFile(archivo_zip) as z:
            archivos_csv = [f for f in z.namelist() if f.endswith('.csv') and '__MACOSX' not in f]
            if not archivos_csv: return pd.DataFrame()

            with z.open(archivos_csv[0]) as f:
                df = pd.read_csv(f)

        # 3. Limpieza y Tipos de Datos
        # Fechas
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower() or 'date' in c.lower()), None)
        if col_fecha:
            df['fecha'] = pd.to_datetime(df[col_fecha], errors='coerce')
            df.set_index('fecha', inplace=True)
            df.sort_index(inplace=True)

        # Coordenadas
        df.rename(columns={'lat': 'lat', 'lng': 'lng'}, inplace=True) # Asegurar nombres
        cols_num = ['superficie', 'gastos', 'perdidas', 'lat', 'lng', 'idcomunidad', 'idprovincia']
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 4. Traducción (IDs -> Nombres) usando los diccionarios
        # Comunidades
        if 'idcomunidad' in df.columns and 'comunidades' in diccionarios:
            df['nombre_comunidad'] = df['idcomunidad'].map(diccionarios['comunidades']).fillna("Desconocido")
        else:
            df['nombre_comunidad'] = "N/A"

        # Provincias
        if 'idprovincia' in df.columns and 'provincias' in diccionarios:
            df['nombre_provincia'] = df['idprovincia'].map(diccionarios['provincias']).fillna("Desconocido")
        else:
            df['nombre_provincia'] = "N/A"
            
        # Causas (Mapeo robusto)
        col_causa = 'causa' if 'causa' in df.columns else 'idcausa'
        if col_causa in df.columns and 'causas' in diccionarios:
             df['causa_texto'] = df[col_causa].map(diccionarios['causas']).fillna("No especificado")
        else:
             df['causa_texto'] = "Sin datos"

        return df

    except FileNotFoundError:
        st.error(f"❌ No encuentro el archivo '{archivo_zip}'. Asegúrate de que está en la carpeta.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error crítico cargando datos: {e}")
        return pd.DataFrame()

# Cargar datos al inicio
df = cargar_datos()

if df.empty:
    st.stop()

# ------------------------------------------------------
# 3. BARRA LATERAL (FILTROS)
# ------------------------------------------------------
st.sidebar.title("🔍 Filtros")

# A. Años
years = sorted(df.index.year.unique())
rango_anos = st.sidebar.select_slider("Periodo", options=years, value=(min(years), max(years)))
df_filtrado = df[(df.index.year >= rango_anos[0]) & (df.index.year <= rango_anos[1])]

# B. Comunidad
opts_com = ["Todas"] + sorted(df_filtrado['nombre_comunidad'].unique().tolist())
sel_com = st.sidebar.selectbox("Comunidad", opts_com)
if sel_com != "Todas":
    df_filtrado = df_filtrado[df_filtrado['nombre_comunidad'] == sel_com]

# C. Provincia
opts_prov = ["Todas"] + sorted(df_filtrado['nombre_provincia'].unique().tolist())
sel_prov = st.sidebar.selectbox("Provincia", opts_prov)
if sel_prov != "Todas":
    df_filtrado = df_filtrado[df_filtrado['nombre_provincia'] == sel_prov]

# D. Superficie Mínima (Slider para quitar incendios pequeños del mapa)
min_sup = st.sidebar.slider("Superficie mínima (ha)", 0, 500, 0, help="Filtra incendios pequeños")
df_filtrado = df_filtrado[df_filtrado['superficie'] >= min_sup]

# ------------------------------------------------------
# 4. DASHBOARD
# ------------------------------------------------------
st.title("🔥 Monitor de Incendios Forestales")
st.markdown(f"Visualizando **{len(df_filtrado):,}** incendios entre **{rango_anos[0]}** y **{rango_anos[1]}**.")

# KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("Incendios", f"{len(df_filtrado):,}")
k2.metric("Hectáreas Quemadas", f"{df_filtrado['superficie'].sum():,.0f} ha")
k3.metric("Gastos Extinción", f"{df_filtrado['gastos'].fillna(0).sum():,.0f} €")
k4.metric("Pérdidas Estimadas", f"{df_filtrado['perdidas'].fillna(0).sum():,.0f} €")

st.divider()

# --- MAPA AVANZADO ---
st.subheader("🗺️ Análisis Geoespacial")

# Pestañas para elegir tipo de mapa
tab1, tab2 = st.tabs(["🔥 Mapa de Calor (Densidad)", "📍 Puntos Agrupados (Clusters)"])

df_geo = df_filtrado.dropna(subset=['lat', 'lng'])

if not df_geo.empty:
    # Calculamos centro
    centro = [df_geo['lat'].mean(), df_geo['lng'].mean()]
    
    # -- Pestaña 1: HEATMAP --
    with tab1:
        m1 = folium.Map(location=centro, zoom_start=6, tiles="CartoDB positron")
        # El mapa de calor es genial para ver "zonas calientes" sin saturar
        HeatMap(
            data=df_geo[['lat', 'lng', 'superficie']].values.tolist(),
            radius=15,
            blur=20,
            max_zoom=10
        ).add_to(m1)
        Fullscreen().add_to(m1)
        st_folium(m1, width="100%", height=500)

    # -- Pestaña 2: CLUSTERS --
    with tab2:
        m2 = folium.Map(location=centro, zoom_start=6)
        marker_cluster = MarkerCluster().add_to(m2)
        
        # Limitamos a 2000 puntos para que no explote el navegador si hay muchos
        # Si hay más, mostramos aviso
        limit = 2000
        df_display = df_geo.head(limit)
        
        if len(df_geo) > limit:
            st.warning(f"⚠️ Mostrando los {limit} incendios más recientes en este modo para mantener fluidez.")
        
        for idx, row in df_display.iterrows():
            # Color dinámico
            sup = row['superficie']
            color = "red" if sup > 100 else "orange" if sup > 10 else "green"
            
            folium.CircleMarker(
                location=[row['lat'], row['lng']],
                radius=5,
                color=color,
                fill=True,
                fill_color=color,
                popup=f"<b>{row.get('municipio','?')}</b><br>Sup: {sup:.1f} ha<br>{row.get('causa_texto','')}"
            ).add_to(marker_cluster)
            
        Fullscreen().add_to(m2)
        st_folium(m2, width="100%", height=500)
else:
    st.info("No hay datos geográficos para esta selección.")

st.divider()

# --- GRÁFICOS ---
c1, c2 = st.columns(2)

with c1:
    st.subheader("📈 Tendencia Temporal")
    df_anual = df_filtrado.resample('YE')['superficie'].sum().reset_index()
    if not df_anual.empty:
        fig_line = px.line(df_anual, x='fecha', y='superficie', markers=True, 
                           labels={'superficie': 'Hectáreas', 'fecha': 'Año'})
        st.plotly_chart(fig_line, width="stretch")

with c2:
    st.subheader("📋 Causas Principales")
    if 'causa_texto' in df_filtrado.columns:
        conteo = df_filtrado['causa_texto'].value_counts().reset_index()
        conteo.columns = ['Causa', 'Incidentes']
        fig_pie = px.pie(conteo.head(10), values='Incidentes', names='Causa', hole=0.4)
        st.plotly_chart(fig_pie, width="stretch")

# --- TABLA ---
with st.expander("📂 Ver Datos Detallados"):
    st.dataframe(df_filtrado.sort_index(ascending=False).head(1000), use_container_width=True)
