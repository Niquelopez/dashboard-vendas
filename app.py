import streamlit as st
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Portal Futurista de Vendas", layout="wide")

@st.cache_data
def load_data(file_vendas, file_estab):
    df_vendas = pd.read_excel(file_vendas)
    df_estab = pd.read_excel(file_estab)

    # Normalizar nomes de colunas
    df_vendas.columns = df_vendas.columns.str.strip()
    df_estab.columns = df_estab.columns.str.strip()

    # Garantir colunas principais
    if "Cnpj" not in df_vendas.columns and "cnpj" in df_vendas.columns:
        df_vendas.rename(columns={"cnpj": "Cnpj"}, inplace=True)
    if "cnpjEmpresa" not in df_estab.columns and "cnpj" in df_estab.columns:
        df_estab.rename(columns={"cnpj": "cnpjEmpresa"}, inplace=True)

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

    # Apenas uma data inicial
    data_inicio = st.sidebar.date_input(
        "📅 Mostrar clientes instalados a partir de:",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY"
    )

    # Filtro aplicado apenas para clientes
    df_clientes_filtrados = df[df["dtInclusao"].dt.date >= data_inicio]

    # --- MÉTRICAS ---
    # Vendas únicas sem filtro de ativação
    df_vendas_unicas = df.drop_duplicates(subset=["Id_Venda"])

    total_vendas = df_vendas_unicas.shape[0]
    total_estab = df_estab["cnpjEmpresa"].nunique()  # agora pega direto da planilha

    col1, col2 = st.columns(2)
    col1.metric("🛒 Vendas Únicas", f"{total_vendas}")
    col2.metric("🏢 Estabelecimentos Avaliados", f"{total_estab}")

    # --- CLIENTES DE BAIXA PERFORMANCE ---
    st.markdown("---")
    st.subheader("⚠️ Clientes com Baixa Performance")

    limite_vendas = st.slider("Ver clientes com menos vendas que:", 0, 500, 10)
    df_perf = df_vendas_unicas.groupby(["Cnpj", "descFantasia", "dtInclusao"]).agg(
        Qtd_Vendas=("Id_Venda", "count")
    ).reset_index()

    df_baixa = df_perf[df_perf["Qtd_Vendas"] < limite_vendas]

    st.metric("Total Clientes Baixa Performance", len(df_baixa))
    st.dataframe(df_baixa, use_container_width=True)

    # --- CLIENTES INSTALADOS SEM TRANSAÇÃO ---
    st.markdown("---")
    st.subheader("🛑 Clientes Instalados sem Nenhuma Transação")

    clientes_instalados = df_estab[["cnpjEmpresa", "descFantasia", "dtInclusao"]].drop_duplicates()
    clientes_instalados = clientes_instalados[clientes_instalados["dtInclusao"].dt.date >= data_inicio]

    clientes_com_venda = df_vendas_unicas[["Cnpj"]].drop_duplicates()
    clientes_sem_venda = clientes_instalados[~clientes_instalados["cnpjEmpresa"].isin(clientes_com_venda["Cnpj"])]

    st.metric("Total Clientes sem Transação", len(clientes_sem_venda))
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

    st.metric("Total Clientes Parados", len(clientes_parados))
    st.dataframe(clientes_parados, use_container_width=True)

    # --- CHURN RATE ---
    st.markdown("---")
    st.subheader("📉 Churn Rate")

    if len(df_mensal["Venda"].unique()) > 1:
        penultimo_mes = sorted(df_mensal["Venda"].unique())[-2]
        ativos_penultimo = df_mensal[df_mensal["Venda"] == penultimo_mes]["Cnpj"].nunique()
        parados = len(clientes_parados)

        churn_rate = (parados / ativos_penultimo * 100) if ativos_penultimo > 0 else 0

        colA, colB, colC = st.columns(3)
        colA.metric("Clientes Ativos Penúltimo Mês", ativos_penultimo)
        colB.metric("Clientes Pararam Último Mês", parados)
        colC.metric("Churn Rate", f"{churn_rate:.2f}%")
    else:
        st.info("Ainda não há dados suficientes para calcular o churn rate.")

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

        st.metric("Total Clientes com Queda", len(clientes_queda))
        st.dataframe(clientes_queda, use_container_width=True)
    else:
        st.info("Ainda não há dados suficientes para comparar queda de rendimento.")
else:
    st.info("Faça upload das duas planilhas para visualizar o dashboard.")
