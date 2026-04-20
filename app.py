import streamlit as st
import pandas as pd
import io
import requests  # Importante para o Webhook

st.set_page_config(page_title="Streamlit + n8n", layout="wide")

# URL do seu Webhook no n8n (Substitua pela sua)
N8N_WEBHOOK_URL = "https://seu-n8n.webhook.com/rastreio-vendas"

st.title("🤖 Automação Vendas -> n8n")

col1, col2 = st.columns(2)
with col1:
    input_vendas = st.text_area("1. Cole dados de Vendas:", height=200)
with col2:
    input_rastreio = st.text_area("2. Cole dados de Rastreio:", height=200)

if input_vendas and input_rastreio:
    try:
        # --- LÓGICA DE PROCESSAMENTO (IGUAL ANTERIOR) ---
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t')
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t')

        if 'Pedido' in df_rastreio.columns:
            df_rastreio = df_rastreio.rename(columns={'Pedido': 'N. Pedido'})

        df_vendas['N. Pedido'] = df_vendas['N. Pedido'].astype(str).str.strip()
        df_rastreio['N. Pedido'] = df_rastreio['N. Pedido'].astype(str).str.strip()

        # Cruzamento
        df_final = pd.merge(df_vendas, df_rastreio[['N. Pedido', 'Código de Rastreio']], on='N. Pedido', how='left')
        
        # Filtra apenas quem REALMENTE tem rastreio para não enviar lixo pro n8n
        df_com_rastreio = df_final[df_final['Código de Rastreio'].notna()]

        st.success(f"Tabela gerada! {len(df_com_rastreio)} pedidos prontos para envio.")
        st.dataframe(df_com_rastreio.head())

        # --- NOVO: BOTÃO PARA n8n ---
        st.divider()
        st.subheader("Integração n8n")
        
        if st.button("🚀 Disparar Mensagens via n8n"):
            # Converte o DataFrame para uma lista de dicionários (JSON)
            payload = df_com_rastreio.to_dict(orient='records')
            
            with st.spinner("Enviando dados para o n8n..."):
                try:
                    response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=10)
                    
                    if response.status_code == 200:
                        st.balloons()
                        st.success("✅ Enviado com sucesso! O n8n recebeu os dados.")
                    else:
                        st.error(f"❌ Erro no n8n: Status {response.status_code}")
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
