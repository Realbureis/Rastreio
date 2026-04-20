import streamlit as st
import pandas as pd
import io
import requests

st.set_page_config(page_title="Streamlit to n8n", layout="wide")

st.title("🚀 Automação de Rastreios")

col1, col2 = st.columns(2)
with col1:
    input_vendas = st.text_area("1. Cole dados de Vendas (N. Pedido):", height=200)
with col2:
    input_rastreio = st.text_area("2. Cole dados de Rastreio (Pedido):", height=200)

if input_vendas and input_rastreio:
    try:
        # Lendo e limpando
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t')
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t')

        # Padroniza coluna de busca
        if 'Pedido' in df_rastreio.columns:
            df_rastreio = df_rastreio.rename(columns={'Pedido': 'N. Pedido'})

        # Limpeza pesada para garantir o match (remove espaços e vira string)
        df_vendas['N. Pedido'] = df_vendas['N. Pedido'].astype(str).str.strip()
        df_rastreio['N. Pedido'] = df_rastreio['N. Pedido'].astype(str).str.strip()

        # Merge (União)
        # Usamos how='inner' se você só quiser quem tem rastreio 
        # Ou how='left' se quiser ver todos, mesmo os sem rastreio
        df_final = pd.merge(df_vendas, df_rastreio[['N. Pedido', 'Código de Rastreio']], on='N. Pedido', how='left')

        # Estatísticas para você conferir
        total_vendas = len(df_vendas)
        com_rastreio = df_final['Código de Rastreio'].notna().sum()

        st.info(f"📊 Resumo: {total_vendas} vendas coladas | {com_rastreio} rastreios encontrados.")

        # REMOVIDO O .head() - Agora mostra a tabela inteira (Streamlit cria barra de rolagem)
        st.subheader("Dados Processados")
        st.dataframe(df_final) 

        # --- ENVIO PARA N8N ---
        st.divider()
        webhook_url = st.text_input("URL do Webhook n8n:", "SUA_URL_AQUI")
        
        if st.button("🚀 Enviar TODOS para o n8n"):
            # Filtramos para enviar apenas quem tem rastreio (para não gastar API atoa)
            dados_para_enviar = df_final[df_final['Código de Rastreio'].notna()].to_dict(orient='records')
            
            if len(dados_para_enviar) > 0:
                response = requests.post(webhook_url, json=dados_para_enviar)
                if response.status_code == 200:
                    st.success(f"Enviado! {len(dados_para_enviar)} itens disparados.")
                else:
                    st.error(f"Erro no n8n: {response.status_code}")
            else:
                st.warning("Nenhum dado com rastreio para enviar.")

    except Exception as e:
        st.error(f"Erro: {e}")
