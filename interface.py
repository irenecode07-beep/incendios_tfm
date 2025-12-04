import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, HeatMap
from streamlit_folium import st_folium
import plotly.express as px
import zipfile

# ------------------------------------------------------
# 0. CONFIGURACIÓN INICIAL
# ------------------------------------------------------
st.set_page_config(page_title="Monitor de Incendios Forestales", page_icon="🔥", layout="wide")

# ------------------------------------------------------
# 1. FUNCIONES AUXILIARES
# ------------------------------------------------------
def detect_column(df, candidates):
    """
    Devuelve la primera columna existente de la lista candidates.
    """
    for col in candidates:
        if col in df.columns:
            return col
    return None

@st.cache_data
def load_csv_from_zip(zip_file):
    with zipfile.ZipFile(zip_file, "r") as z:
        csv_name = [f for f in z.namelist() if f.endswith('.csv')][0]
        return pd.read_csv(z.open(csv_name))

@st.cache_data
def clean_dataset(df):
    """Normaliza nombres de columnas y prepara datos esenciales."""

    # Detectar columnas lat/lng
    lat_col = detect_column(df, ["lat", "latitude", "latitud", "Lat", "LAT"])
    lng_col = detect_column(df, ["lng", "long", "longitude", "longitud", "Lon", "LNG"])

    if lat_col and lng_col:
        df = df.dropna(subset=[lat_col, lng_col])
        df.rename(columns={lat_col: "lat", lng_col: "lng"}, inplace=True)

    # Detectar columna temporal
    time_col = detect_column(df, ["fecha", "date", "Fecha", "FECHA", "datetime", "time"])
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df = df.set_index(time_col)

    # Superficie
    superficie_col = detect_column(df, ["superficie", "ha", "hectareas", "area"])
    if superficie_col:
        df.rename(columns={superficie_col: "superficie"}, inplace=True)

    # Causa
    causa_col = detect_column(df, ["causa", "idcausa", "causa_desc", "causas"])
    if causa_col:
        df.rename(columns={causa_col: "causa"}, inplace=True)
    else:
        df["causa"] = "Desconocida"

    return df

# ------------------------------------------------------
# 2. FUNCIONES VISUALES
# ------------------------------------------------------
def make_map(df):
    if df.empty or "lat" not in df.columns or "lng" not in df.columns:
        return None

    m = folium.Map(location=[40.4, -3.7], zoom_start=6)
    cluster = MarkerCluster().add_to(m)

    for _, row in df.iterrows():
        folium.Marker(
            location=[row["lat"], row["lng"]],
            popup=f"{row.get('municipio', 'Sin municipio')} - {row.get('superficie', '?')} ha",
        ).add_to(cluster)

    HeatMap(df[["lat", "lng"]].values.tolist(), radius=10, blur=15).add_to(m)
    return m


def plot_trend(df):
    if not isinstance(df.index, pd.DatetimeIndex):
        return None

    temp = df.groupby(df.index.year)["superficie"].sum()

    return px.line(
        temp,
        title="Superficie quemada por año",
        labels={"value": "Hectáreas", "index": "Año"}
    )

# ------------------------------------------------------
# 3. INTERFAZ STREAMLIT
# ------------------------------------------------------
st.title("🔥 Monitor de Incendios Forestales en España")
st.write("Explora datos históricos, mapas y tendencias.")

uploaded_zip = st.sidebar.file_uploader("Sube un archivo ZIP con un CSV dentro", type=["zip"])

if uploaded_zip:
    df = load_csv_from_zip(uploaded_zip)
    df = clean_dataset(df)

    st.sidebar.header("Filtros")

    # Filtro por año
    if isinstance(df.index, pd.DatetimeIndex):
        min_y, max_y = int(df.index.year.min()), int(df.index.year.max())
        years = st.sidebar.slider("Años", min_y, max_y, (min_y, max_y))
        df = df[(df.index.year >= years[0]) & (df.index.year <= years[1])]

    # Filtro superficie
    if "superficie" in df.columns:
        max_sup = int(df["superficie"].max())
        sup_min = st.sidebar.slider("Superficie mínima (ha)", 0, max_sup, 10)
        df = df[df["superficie"] >= sup_min]

    # Filtro causa
    causas_disponibles = sorted(df["causa"].unique())
    causas_select = st.sidebar.multiselect("Causas", causas_disponibles, default=causas_disponibles)
    df = df[df["causa"].isin(causas_select)]

    # ------------------------
    # MAPA
    # ------------------------
    st.subheader("📌 Mapa de incendios")
    mapa = make_map(df)
    if mapa:
        st_folium(mapa, width=1200, height=600)
    else:
        st.info("No hay datos suficientes para mostrar un mapa.")

    # ------------------------
    # TENDENCIA
    # ------------------------
    st.subheader("📈 Tendencia temporal")
    fig = plot_trend(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("El dataset no tiene información temporal válida.")

    # ------------------------
    # DATOS
    # ------------------------
    st.subheader("📄 Datos filtrados")
    st.dataframe(df, use_container_width=True)

else:
    st.info("Sube un archivo ZIP con un CSV para comenzar.")
