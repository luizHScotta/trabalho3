# -*- coding: utf-8 -*-
"""
Streamlit Dashboard – Amazônia: Clima × Produção × Saúde
=======================================================

Execute localmente com:
    streamlit run streamlit_dashboard.py

Requisitos (coloque em requirements.txt):
    streamlit
    pandas
    plotly
    numpy

O app lê o arquivo `dados_integrados.csv` (mesma pasta) e oferece filtros
interativos + CINCO visualizações principais:
  1. Linha temporal – chuva vs. produção (médias móveis)
  2. Dispersão – anomalia de chuva × produção
  3. Boxplot – doenças vs. acesso à água
  4. Heatmap – correlação entre variáveis numéricas
  5. Radar – componentes médios da vulnerabilidade
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

# ------------------------------------------------------------------
# Configurações da página
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Dashboard Amazônia – Clima & Vulnerabilidade",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🌎📊 Dashboard Amazônia – Clima, Produção e Saúde")

# ------------------------------------------------------------------
# Função utilitária para carregar dados
# ------------------------------------------------------------------
@st.cache_data(show_spinner=True)
def carregar_dados(path_csv: str) -> pd.DataFrame:
    """Lê CSV e converte a coluna 'data' para datetime."""
    return pd.read_csv(path_csv, parse_dates=["data"])

# ------------------------------------------------------------------
# Carregamento dos dados
# ------------------------------------------------------------------
DATA_PATH = Path(__file__).with_name("dados_integrados.csv")
if not DATA_PATH.exists():
    st.error("Arquivo 'dados_integrados.csv' não encontrado na pasta do app.")
    st.stop()

_df = carregar_dados(str(DATA_PATH))

# ------------------------------------------------------------------
# Sidebar – filtros
# ------------------------------------------------------------------
st.sidebar.header("⚙️ Filtros")

# Período
data_min, data_max = _df["data"].min().date(), _df["data"].max().date()
periodo = st.sidebar.date_input(
    "Período",
    value=(data_min, data_max),
    min_value=data_min,
    max_value=data_max,
)
if isinstance(periodo, tuple):
    dt_ini, dt_fim = pd.to_datetime(periodo[0]), pd.to_datetime(periodo[1])
else:
    dt_ini = dt_fim = pd.to_datetime(periodo)

if dt_ini > dt_fim:
    st.sidebar.error("Data inicial não pode ser maior que final.")

# Faixa do índice de vulnerabilidade
faixa_vul = st.sidebar.slider(
    "Faixa do Índice de Vulnerabilidade",
    min_value=0.0,
    max_value=1.0,
    value=(
        float(_df["indice_vulnerabilidade"].min()),
        float(_df["indice_vulnerabilidade"].max()),
    ),
    step=0.01,
)

# Acesso à água
agua_opcao = st.sidebar.selectbox(
    "Acesso à Água Potável",
    options=["Todos", "Sim", "Não"],
    index=0,
)
map_agua = {"Sim": 1, "Não": 0}

# Tipo de evento
tipo_opcao = st.sidebar.selectbox(
    "Foco do evento",
    options=["Todos", "Climáticos", "Socioeconômicos"],
    index=0,
)

# ------------------------------------------------------------------
# Aplicação dos filtros
# ------------------------------------------------------------------
df = _df.copy()
df = df[(df["data"] >= dt_ini) & (df["data"] <= dt_fim)]
df = df[
    (df["indice_vulnerabilidade"] >= faixa_vul[0])
    & (df["indice_vulnerabilidade"] <= faixa_vul[1])
]
if agua_opcao != "Todos":
    df = df[df["acesso_agua_potavel"] == map_agua[agua_opcao]]

if tipo_opcao == "Climáticos" and "variacao_climatica" in df.columns:
    df = df[df["variacao_climatica"] == 1]
elif tipo_opcao == "Socioeconômicos" and "flag_incidente_alta" in df.columns:
    df = df[df["flag_incidente_alta"] == 1]

if df.empty:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
    st.stop()

# ------------------------------------------------------------------
# Visualização 1 – Linha temporal
# ------------------------------------------------------------------
st.subheader("📈 Chuva (30 d) × Produção (7 d) – Médias Móveis")

df_sorted = df.sort_values("data")
chuva_rol = (
    df_sorted["chuva_rol_30d"]
    if "chuva_rol_30d" in df_sorted.columns
    else df_sorted["chuvas_reais_mm"].rolling(30, min_periods=1).mean()
)
producao_rol = (
    df_sorted["producao_rol_7d"]
    if "producao_rol_7d" in df_sorted.columns
    else df_sorted["volume_producao_tons"].rolling(7, min_periods=1).mean()
)

fig_line = make_subplots(specs=[[{"secondary_y": True}]])
fig_line.add_trace(
    go.Scatter(
        x=df_sorted["data"],
        y=chuva_rol,
        name="Chuva 30 d (mm)",
        mode="lines",
        line=dict(color="#1f77b4"),
    ),
    secondary_y=False,
)
fig_line.add_trace(
    go.Scatter(
        x=df_sorted["data"],
        y=producao_rol,
        name="Produção 7 d (ton)",
        mode="lines",
        line=dict(color="#ff7f0e"),
    ),
    secondary_y=True,
)
fig_line.update_yaxes(title_text="Chuva (mm)", secondary_y=False)
fig_line.update_yaxes(title_text="Produção (ton)", secondary_y=True)
fig_line.update_xaxes(title_text="Data")
fig_line.update_layout(height=400, legend_title_text="Série")
st.plotly_chart(fig_line, use_container_width=True)

# ------------------------------------------------------------------
# Visualização 2 – Scatter
# ------------------------------------------------------------------
st.subheader("🔄 Anomalia de Chuva × Produção")

fig_scatter = px.scatter(
    df,
    x="anomalia_chuva_mm",
    y="volume_producao_tons",
    color=df["acesso_agua_potavel"].map({0: "Sem água", 1: "Com água"}),
    labels={
        "anomalia_chuva_mm": "Anomalia de Chuva (mm)",
        "volume_producao_tons": "Produção (ton)",
        "color": "Acesso à água",
    },
    hover_data=["data", "indice_vulnerabilidade"],
)
fig_scatter.update_layout(height=420)
st.plotly_chart(fig_scatter, use_container_width=True)

# ------------------------------------------------------------------
# Visualização 3 – Boxplot de doenças
# ------------------------------------------------------------------
st.subheader("💧 Incidência de Doenças vs. Acesso à Água Potável")

df["agua_label"] = df["acesso_agua_potavel"].map({0: "Sem acesso", 1: "Com acesso"})
fig_box = px.box(
    df,
    x="agua_label",
    y="incidencia_doencas",
    color="agua_label",
    labels={
        "agua_label": "Acesso à Água",
        "incidencia_doencas": "Casos por dia",
    },
    title="Distribuição da Incidência de Doenças",
)
fig_box.update_layout(height=420, showlegend=False)
st.plotly_chart(fig_box, use_container_width=True)

# ------------------------------------------------------------------
# Visualização 4 – Heatmap de correlação
# ------------------------------------------------------------------
st.subheader("📊 Heatmap de Correlação entre Variáveis Numéricas")

numeric_cols = df.select_dtypes(include=[np.number]).columns
corr_matrix = df[numeric_cols].corr()
fig_heat = px.imshow(
    corr_matrix,
    text_auto=True,
    aspect="auto",
    color_continuous_scale="RdBu_r",
    zmin=-1,
    zmax=1,
)
fig_heat.update_layout(height=500, margin=dict(l=40, r=40, t=40, b=40))
st.plotly_chart(fig_heat, use_container_width=True)

# ------------------------------------------------------------------
# Visualização 5 – Radar dos componentes de vulnerabilidade
# ------------------------------------------------------------------
st.subheader("🕸️ Radar – Componentes Médios da Vulnerabilidade")

comp_clima = np.mean(np.clip(np.abs(df["anomalia_chuva_mm"]) / 200.0, 0, 1))
comp_prod = np.mean(np.clip(1 - (df["volume_producao_tons"] / 20.0), 0, 1))
comp_doencas = np.mean(np.clip(df["incidencia_doencas"] / 6.0, 0, 1))
comp_agua = 1 - (df["acesso_agua_potavel"].sum() / len(df))
comp_food = np.mean(np.clip(1 - (df["indicador_seguranca_alimentar"] / 100.0), 0, 1))

radar_categories = ["Clima", "Produção", "Doenças", "Água", "Alimentação"]
radar_values = [comp_clima, comp_prod, comp_doencas, comp_agua, comp_food]
radar_categories += radar_categories[:1]
radar_values += radar_values[:1]

fig_radar = go.Figure()
fig_radar.add_trace(
    go.Scatterpolar(
        r=radar_values,
        theta=radar_categories,
        fill="toself",
        name="Vulnerabilidade",
    )
)
fig_radar.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
    showlegend=False,
    height=430,
)
st.plotly_chart(fig_radar, use_container_width=True)

# ------------------------------------------------------------------
# Rodapé
# ------------------------------------------------------------------
st.markdown("---")
st.caption("Desenvolvido com ❤️ usando Streamlit | Dados: Projeto Amazônia 2025")
