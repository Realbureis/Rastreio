import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Vincular Rastreio", layout="wide", page_icon="📦")

st.title("📦 Sistema de Vinculação de Rastreios")
st.markdown("Copie os dados do seu sistema e cole abaixo para gerar a planilha final.")

# --- INTERFACE DE ENTRADA ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Dados de Vendas")
    st.caption("Deve conter a coluna 'N. Pedido'")
    input_vendas = st.text_area("Cole aqui os dados de Vendas:", height=300)

with col2:
    st.subheader("2. Dados de Rastreio")
    st.caption("Deve conter a coluna 'Pedido' e 'Código de Rastreio'")
    input_rastreio = st.text_area("Cole aqui os dados de Rastreio:", height=300)

# --- PROCESSAMENTO ---
if input_vendas and input_rastreio:
    try:
        # 1. Transformar o texto colado em DataFrames (Pandas)
        # O Excel usa o separador '\t' (Tab) quando copiamos e colamos
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t')
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t')

        # 2. Padronização: Renomear 'Pedido' para 'N. Pedido' na segunda tabela se necessário
        if 'Pedido' in df_rastreio.columns:
            df_rastreio = df_rastreio.rename(columns={'Pedido': 'N. Pedido'})

        # 3. Limpeza de dados (remover espaços em branco e garantir que IDs sejam texto)
        df_vendas['N. Pedido'] = df_vendas['N. Pedido'].astype(str).str.strip()
        df_rastreio['N. Pedido'] = df_rastreio['N. Pedido'].astype(str).str.strip()

        # 4. A Mágica: Cruzar as tabelas (Merge)
        # O 'how=left' garante que nenhuma venda suma, mesmo que ainda não tenha rastreio
        df_final = pd.merge(df_vendas, df_rastreio, on='N. Pedido', how='left')

        # 5. Organização: Mover o Código de Rastreio para o início (opcional)
        cols = list(df_final.columns)
        if 'Código de Rastreio' in df_final.columns:
            rastreio_col = cols.pop(cols.index('Código de Rastreio'))
            cols.insert(1, rastreio_col) # Insere na segunda posição
            df_final = df_final[cols]

        # --- RESULTADO ---
        st.success(f"✅ Processado! Foram encontrados {df_final['Código de Rastreio'].notna().sum()} rastreios para os pedidos colados.")
        
        st.subheader("Visualização Prévia (Top 10)")
        st.dataframe(df_final.head(10))

        # Gerar o arquivo Excel para Download
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, index=False, sheet_name='Relatorio_Final')
        
        st.download_button(
            label="📥 Baixar Planilha Completa (Excel)",
            data=output.getvalue(),
            file_name="vendas_com_rastreio_atualizado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"Ocorreu um erro no processamento: {e}")
        st.info("Verifique se você copiou os cabeçalhos das colunas corretamente.")
