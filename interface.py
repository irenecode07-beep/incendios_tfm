import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, HeatMap
from streamlit_folium import st_folium
import plotly.express as px

# ------------------------------------------------------
# 0. CONFIGURACIÓN INICIAL
# ------------------------------------------------------
st.set_page_config(page_title="Monitor de Incendios Forestales", page_icon="🔥", layout="wide")

# ------------------------------------------------------
# 1. FUNCIONES AUXILIARES
# ------------------------------------------------------
def detect_column(df, candidates):
"""Devuelve la primera columna existente de la lista candidates."""
for col in candidates:
if col in df.columns:
return col
return None

@st.cache_data
def load_csv_from_zip(zip_file):
import zipfile
with zipfile.ZipFile(zip_file, "r") as z:
csv_name = [f for f in z.namelist() if f.endswith('.csv')][0]
return pd.read_csv(z.open(csv_name))

@st.cache_data
def clean_dataset(df):
"""Normaliza nombres de columnas y prepara datos esenciales."""
# Detectar columnas de lat/lng
lat_col = detect_column(df, ["lat", "latitude", "latitud"])
lng_col = detect_column(df, ["lng", "long", "longitude", "longitud"])

if lat_col and lng_col:
df = df.dropna(subset=[lat_col, lng_col])
df.rename(columns={lat_col: "lat", lng_col: "lng"}, inplace=True)

# Índice temporal si procede
if detect_column(df, ["fecha", "date", "Fecha", "FECHA"]):
time_col = detect_column(df, ["fecha", "date", "Fecha", "FECHA"])
df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
df = df.set_index(time_col)

# Superficie quemada
superficie_col = detect_column(df, ["superficie", "ha", "hectareas"])
if superficie_col:
df.rename(columns={superficie_col: "superficie"}, inplace=True)

# Causa
causa_col = detect_column(df, ["causa", "idcausa", "causa_desc"])
if causa_col:
df.rename(columns={causa_col: "causa"}, inplace=True)
else:
df["causa"] = "Desconocida"

return df

# ------------------------------------------------------
# 2. FUNCIONES VISUALES
# ------------------------------------------------------
def make_map(df):
if df.empty:
return None

m = folium.Map(location=[40.4, -3.7], zoom_start=6)
cluster = MarkerCluster().add_to(m)

for _, row in df.iterrows():
folium.Marker(
location=[row["lat"], row["lng"]],
popup=f"{row.get('municipio', 'Sin municipio')} - {row['superficie']} ha",
).add_to(cluster)

# Heatmap opcional
HeatMap(df[["lat", "lng"]].values.tolist(), radius=10, blur=15).add_to(m)

return m


def plot_trend(df):
if not isinstance(df.index, pd.DatetimeIndex):
return None
temp = df.groupby(df.index.year)["superficie"].sum()
return px.line(temp, title="Superficie quemada por año", labels={"value": "Hectáreas", "index": "Año"})

# ------------------------------------------------------
# 3. INTERFAZ STREAMLIT
st.info("Sube un archivo ZIP con un CSV para comenzar.")
