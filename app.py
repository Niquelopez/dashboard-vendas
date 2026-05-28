import streamlit as st
import pandas as pd
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Portal Futurista de Vendas", layout="wide")


# CORREÇÃO 1: Removido @st.cache_data — objetos UploadedFile não são
# serializáveis de forma confiável pelo Streamlit, causando exibição
# de dados desatualizados após novo upload.
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


st.title("🌌 TDS Analise de Performance +")

file_vendas = st.file_uploader("Upload da Planilha A (Vendas)", type=["xlsx"])
file_estab = st.file_uploader("Upload da Planilha B (Estabelecimentos)", type=["xlsx"])

if file_vendas and file_estab:
    df, df_estab = load_data(file_vendas, file_estab)

    # --- FILTROS ---
    st.sidebar.header("Filtros")
    min_date = df["dtInclusao"].min()
    max_date = df["dtInclusao"].max()

    data_inicio = st.sidebar.date_input(
        "📅 Mostrar clientes instalados a partir de:",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY"
    )

    # Vendas únicas sem filtro de data (base global)
    df_vendas_unicas = df.drop_duplicates(subset=["Id_Venda"])

    # CORREÇÃO 2: df_clientes_filtrados agora é usado em todas as seções
    # que devem respeitar o filtro de data de instalação.
    df_filtrado = df[df["dtInclusao"].dt.date >= data_inicio]
    df_vendas_unicas_filtradas = df_filtrado.drop_duplicates(subset=["Id_Venda"])

    # --- MÉTRICAS ---
    total_vendas = df_vendas_unicas.shape[0]

    # CORREÇÃO 5: total_estab agora respeita o filtro de data,
    # tornando a métrica coerente com o restante do dashboard.
    total_estab = df_estab[
        pd.to_datetime(df_estab["dtInclusao"], errors="coerce").dt.date >= data_inicio
    ]["cnpjEmpresa"].nunique()

    col1, col2 = st.columns(2)
    col1.metric("🛒 Vendas Únicas", f"{total_vendas}")
    col2.metric("🏢 Estabelecimentos no Período", f"{total_estab}")

    # --- CLIENTES DE BAIXA PERFORMANCE ---
    st.markdown("---")
    st.subheader("⚠️ Clientes com Baixa Performance")

    limite_vendas = st.slider("Ver clientes com menos vendas que:", 0, 500, 10)

    # CORREÇÃO 2 (aplicada): usa df_vendas_unicas_filtradas respeitando a data
    df_perf = df_vendas_unicas_filtradas.groupby(["Cnpj", "descFantasia", "dtInclusao"]).agg(
    Qtd_Vendas=("Id_Venda", "count"),
    Ultima_Transacao=("Venda", "max")
).reset_index()

    df_baixa = df_perf[df_perf["Qtd_Vendas"] < limite_vendas]

    st.metric("Total Clientes Baixa Performance", len(df_baixa))
    st.dataframe(df_baixa, use_container_width=True)

    # --- CLIENTES INSTALADOS SEM TRANSAÇÃO ---
    st.markdown("---")
    st.subheader("🛑 Clientes Instalados sem Nenhuma Transação")

    clientes_instalados = df_estab[["cnpjEmpresa", "descFantasia", "dtInclusao"]].drop_duplicates()
    clientes_instalados = clientes_instalados[
        pd.to_datetime(clientes_instalados["dtInclusao"], errors="coerce").dt.date >= data_inicio
    ]

    clientes_com_venda = df_vendas_unicas[["Cnpj"]].drop_duplicates()
    clientes_sem_venda = clientes_instalados[
        ~clientes_instalados["cnpjEmpresa"].isin(clientes_com_venda["Cnpj"])
    ]

    st.metric("Total Clientes sem Transação", len(clientes_sem_venda))
    st.dataframe(clientes_sem_venda, use_container_width=True)

    # --- CLIENTES QUE PARARAM DE OPERAR ---
    st.markdown("---")
    st.subheader("⏸️ Clientes que Pararam de Operar")

    # CORREÇÃO 2 (aplicada): usa df_vendas_unicas_filtradas
    df_mensal = df_vendas_unicas_filtradas.groupby(
        [df_vendas_unicas_filtradas["Venda"].dt.to_period("M"), "Cnpj", "descFantasia"]
    ).agg(Qtd_Vendas=("Id_Venda", "count")).reset_index()

    # CORREÇÃO 4: usa o mês atual real como referência, não o último mês do dado.
    # Assim, clientes que não venderam no mês corrente são corretamente sinalizados.
    mes_atual = pd.Period(datetime.today(), "M")

    ultimo_mes_cliente = df_mensal.groupby(["Cnpj", "descFantasia"])["Venda"].max().reset_index()
    clientes_parados = ultimo_mes_cliente[ultimo_mes_cliente["Venda"] < mes_atual]

    st.metric("Total Clientes Parados", len(clientes_parados))
    st.dataframe(clientes_parados, use_container_width=True)

    # --- CLIENTES COM QUEDA DE RENDIMENTO ---
    st.markdown("---")
    st.subheader("📉 Clientes com Queda de Rendimento")

    periodos_unicos = sorted(df_mensal["Venda"].unique())

    if len(periodos_unicos) > 1:
        ultimo_mes = periodos_unicos[-1]
        penultimo_mes = periodos_unicos[-2]

        # CORREÇÃO 3: inclui descFantasia no merge para exibir o nome do estabelecimento
        vendas_penultimo = df_mensal[df_mensal["Venda"] == penultimo_mes][
            ["Cnpj", "descFantasia", "Qtd_Vendas"]
        ]
        vendas_ultimo = df_mensal[df_mensal["Venda"] == ultimo_mes][
            ["Cnpj", "Qtd_Vendas"]
        ]

        comparativo = pd.merge(
            vendas_penultimo,
            vendas_ultimo,
            on="Cnpj",
            how="left",
            suffixes=("_penultimo", "_ultimo")
        )
        comparativo = comparativo.fillna(0)

        clientes_queda = comparativo[
            comparativo["Qtd_Vendas_ultimo"] < comparativo["Qtd_Vendas_penultimo"]
        ].copy()

        # Coluna auxiliar mostrando a variação percentual
        clientes_queda["Variação (%)"] = (
            (clientes_queda["Qtd_Vendas_ultimo"] - clientes_queda["Qtd_Vendas_penultimo"])
            / clientes_queda["Qtd_Vendas_penultimo"].replace(0, 1)
            * 100
        ).round(1)

        st.metric("Total Clientes com Queda", len(clientes_queda))
        st.dataframe(clientes_queda, use_container_width=True)
    else:
        st.info("Ainda não há dados suficientes para comparar queda de rendimento.")

else:
    st.info("Faça upload das duas planilhas para visualizar o dashboard.")
