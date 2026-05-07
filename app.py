import streamlit as st
import pandas as pd
import plotly.express as px

# Configuração da página
st.set_page_config(page_title="Portal Futurista de Vendas", layout="wide")

# --- CSS customizado para cards ---
st.markdown("""
    <style>
    .card {
        background-color: #1c1c1c;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        margin: 10px;
    }
    .card h2 {
        color: #00f5d4;
        font-size: 32px;
        margin: 0;
    }
    .card p {
        color: white;
        font-size: 16px;
        margin: 0;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data(file_vendas, file_estab):
    df_vendas = pd.read_excel(file_vendas)
    df_estab = pd.read_excel(file_estab)

    df_vendas["Cnpj"] = df_vendas["Cnpj"].astype(str)
    df_estab["cnpjEmpresa"] = df_estab["cnpjEmpresa"].astype(str)

    df = pd.merge(
        df_vendas,
        df_estab[["cnpjEmpresa", "descFantasia", "dtInclusao"]],
        left_on="Cnpj",
        right_on="cnpjEmpresa",
        how="left"
    )

    df["Venda"] = pd.to_datetime(df["Venda"], errors="coerce")
    df["dtInclusao"] = pd.to_datetime(df["dtInclusao"], errors="coerce")

    return df

st.title("🌌 Dashboard de Performance TDS")

file_vendas = st.file_uploader("Upload da Planilha A (Vendas)", type=["xlsx"])
file_estab = st.file_uploader("Upload da Planilha B (Estabelecimentos)", type=["xlsx"])

if file_vendas and file_estab:
    df = load_data(file_vendas, file_estab)

    # --- FILTROS ---
    st.sidebar.header("Filtros")
    min_date = df["dtInclusao"].min()
    max_date = df["dtInclusao"].max()

    date_range = st.sidebar.date_input(
        "Data de Ativação do Cliente",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    if len(date_range) == 2:
        mask = (df["dtInclusao"].dt.date >= date_range[0]) & (df["dtInclusao"].dt.date <= date_range[1])
        df_filtered = df.loc[mask]
    else:
        df_filtered = df

    df_vendas_unicas = df_filtered.drop_duplicates(subset=["Id_Venda"])

    # --- MÉTRICAS EM CARDS ---
    total_vendas = df_vendas_unicas.shape[0]
    volume_total = df_vendas_unicas["Bruto"].sum()
    ticket_medio = volume_total / total_vendas if total_vendas > 0 else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="card"><h2>🛒 {total_vendas}</h2><p>Vendas Únicas</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="card"><h2>💰 R$ {volume_total:,.2f}</h2><p>Volume Bruto</p></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="card"><h2>📊 R$ {ticket_medio:,.2f}</h2><p>Ticket Médio</p></div>', unsafe_allow_html=True)

    # --- PERFORMANCE POR EMPRESA ---
    st.subheader("🚀 Performance por Estabelecimento")
    df_perf = df_vendas_unicas.groupby(["Cnpj", "descFantasia", "dtInclusao"]).agg(
        Qtd_Vendas=("Id_Venda", "count"),
        Total_Bruto=("Bruto", "sum")
    ).reset_index()

    df_perf = df_perf.sort_values(by="Qtd_Vendas", ascending=False)

    fig = px.bar(
        df_perf.head(20),
        x="descFantasia",
        y="Qtd_Vendas",
        color="Total_Bruto",
        title="Top 20 Clientes por Quantidade de Vendas",
        labels={"descFantasia": "Estabelecimento", "Qtd_Vendas": "Quantidade de Vendas"},
        color_continuous_scale="turbo"
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- EVOLUÇÃO TEMPORAL ---
    st.subheader("📈 Evolução Mensal de Vendas")
    df_tempo = df_vendas_unicas.groupby(df_vendas_unicas["Venda"].dt.to_period("M")).agg(
        Qtd_Vendas=("Id_Venda", "count"),
        Total_Bruto=("Bruto", "sum")
    ).reset_index()
    df_tempo["Venda"] = df_tempo["Venda"].astype(str)

    fig_line = px.line(
        df_tempo,
        x="Venda",
        y="Qtd_Vendas",
        title="📈 Evolução Mensal de Vendas",
        markers=True,
        line_shape="spline",
        color_discrete_sequence=["#00f5d4"]
    )
    st.plotly_chart(fig_line, use_container_width=True)

    # --- CLIENTES DE BAIXA PERFORMANCE ---
    st.markdown("---")
    st.subheader("⚠️ Clientes com Baixa Performance")

    limite_vendas = st.slider("Ver clientes com menos vendas que:", 0, 500, 10)
    df_baixa = df_perf[df_perf["Qtd_Vendas"] < limite_vendas]

    st.dataframe(df_baixa[["Cnpj", "descFantasia", "dtInclusao", "Qtd_Vendas"]], use_container_width=True)

    # --- DADOS BRUTOS ---
    with st.expander("🔍 Ver dados brutos filtrados"):
        st.write(df_vendas_unicas)
else:
    st.info("Faça upload das duas planilhas para visualizar o dashboard.")
