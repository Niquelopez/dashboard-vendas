import streamlit as st
import pandas as pd
import plotly.express as px

# Configuração da página
st.set_page_config(page_title="Portal Futurista de Vendas", layout="wide")

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

    return df, df_estab

st.title("🌌 TDS Analise de Performance + ")

file_vendas = st.file_uploader("Upload da Planilha A (Vendas)", type=["xlsx"])
file_estab = st.file_uploader("Upload da Planilha B (Estabelecimentos)", type=["xlsx"])

if file_vendas and file_estab:
    df, df_estab = load_data(file_vendas, file_estab)

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

    # --- MÉTRICAS ---
    total_vendas = df_vendas_unicas.shape[0]
    volume_total = df_vendas_unicas["Bruto"].sum()
    ticket_medio = volume_total / total_vendas if total_vendas > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("🛒 Vendas Únicas", f"{total_vendas}")
    col2.metric("💰 Volume Bruto", f"R$ {volume_total:,.2f}")
    col3.metric("📊 Ticket Médio", f"R$ {ticket_medio:,.2f}")

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

    # --- CLIENTES DE BAIXA PERFORMANCE ---
    st.markdown("---")
    st.subheader("⚠️ Clientes com Baixa Performance")

    limite_vendas = st.slider("Ver clientes com menos vendas que:", 0, 500, 10)
    df_baixa = df_perf[df_perf["Qtd_Vendas"] < limite_vendas]

    st.dataframe(df_baixa[["Cnpj", "descFantasia", "dtInclusao", "Qtd_Vendas"]], use_container_width=True)

    # --- CLIENTES INSTALADOS SEM TRANSAÇÃO ---
    st.markdown("---")
    st.subheader("🛑 Clientes Instalados sem Nenhuma Transação")

    clientes_instalados = df_estab[["cnpjEmpresa", "descFantasia", "dtInclusao"]].drop_duplicates()
    clientes_com_venda = df_vendas_unicas[["Cnpj"]].drop_duplicates()
    clientes_sem_venda = clientes_instalados[~clientes_instalados["cnpjEmpresa"].isin(clientes_com_venda["Cnpj"])]

    st.dataframe(clientes_sem_venda, use_container_width=True)

    # --- CLIENTES QUE PARARAM DE OPERAR ---
    st.markdown("---")
    st.subheader("⏸️ Clientes que Pararam de Operar")

    df_mensal = df_vendas_unicas.groupby(
        [df_vendas_unicas["Venda"].dt.to_period("M"), "Cnpj", "descFantasia"]
    ).agg(Qtd_Vendas=("Id_Venda", "count")).reset_index()

    ultimo_mes = df_mensal["Venda"].max()
    ultimo_mes_cliente = df_mensal.groupby(["Cnpj", "descFantasia"])["Venda"].max().reset_index()
    clientes_parados = ultimo_mes_cliente[ultimo_mes_cliente["Venda"] < ultimo_mes]

    st.dataframe(clientes_parados, use_container_width=True)

    # --- CLIENTES COM QUEDA DE RENDIMENTO ---
    st.markdown("---")
    st.subheader("📉 Clientes com Queda de Rendimento")

    if len(df_mensal["Venda"].unique()) > 1:
        penultimo_mes = sorted(df_mensal["Venda"].unique())[-2]

        vendas_penultimo = df_mensal[df_mensal["Venda"] == penultimo_mes][["Cnpj", "Qtd_Vendas"]]
        vendas_ultimo = df_mensal[df_mensal["Venda"] == ultimo_mes][["Cnpj", "Qtd_Vendas"]]

        comparativo = pd.merge(vendas_penultimo, vendas_ultimo, on="Cnpj", how="left", suffixes=("_penultimo", "_ultimo"))
        comparativo = comparativo.fillna(0)

        clientes_queda = comparativo[comparativo["Qtd_Vendas_ultimo"] < comparativo["Qtd_Vendas_penultimo"]]

        st.dataframe(clientes_queda, use_container_width=True)
    else:
        st.info("Ainda não há dados suficientes para comparar queda de rendimento.")

    # --- DADOS BRUTOS ---
    with st.expander("🔍 Ver dados brutos filtrados"):
        st.write(df_vendas_unicas)
else:
    st.info("Faça upload das duas planilhas para visualizar o dashboard.")
