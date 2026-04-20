import streamlit as st
import pandas as pd
import io
import requests

st.set_page_config(page_title="Rastreio Inteligente", layout="wide", page_icon="🚚")

st.title("🚚 Disparador de Rastreios (Somente Cruzados)")
st.markdown("Este sistema filtra automaticamente apenas os pedidos que possuem código de rastreio para envio ao n8n.")

# --- ENTRADA DE DADOS ---
col1, col2 = st.columns(2)
with col1:
    input_vendas = st.text_area("1. Cole dados de Vendas:", height=200, placeholder="N. Pedido\tData\tCliente...")
with col2:
    input_rastreio = st.text_area("2. Cole dados de Rastreio:", height=200, placeholder="Pedido\tCódigo de Rastreio...")

if input_vendas and input_rastreio:
    try:
        # Lendo os dados
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t')
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t')

        # Padronizando coluna de ligação
        if 'Pedido' in df_rastreio.columns:
            df_rastreio = df_rastreio.rename(columns={'Pedido': 'N. Pedido'})

        # Limpeza para garantir o cruzamento
        df_vendas['N. Pedido'] = df_vendas['N. Pedido'].astype(str).str.strip()
        df_rastreio['N. Pedido'] = df_rastreio['N. Pedido'].astype(str).str.strip()

        # Cruzamento (Merge)
        # Usamos how='inner' para manter APENAS o que existe em AMBAS as tabelas
        df_final = pd.merge(df_vendas, df_rastreio[['N. Pedido', 'Código de Rastreio']], on='N. Pedido', how='inner')

        # --- EXIBIÇÃO ---
        if not df_final.empty:
            st.success(f"🔥 Sucesso! Encontramos {len(df_final)} pedidos prontos para envio.")
            
            # Reorganizar para o rastreio aparecer na frente
            cols = list(df_final.columns)
            rastreio_col = cols.pop(cols.index('Código de Rastreio'))
            cols.insert(1, rastreio_col)
            df_final = df_final[cols]

            st.subheader("📋 Lista de Envio (Apenas com Rastreio)")
            st.dataframe(df_final)

            # --- INTEGRAÇÃO N8N ---
            st.divider()
            webhook_url = st.text_input("Cole sua URL do Webhook n8n aqui:", "https://")
            
            if st.button("🚀 Disparar para n8n agora"):
                if webhook_url == "https://":
                    st.warning("Por favor, insira uma URL válida do n8n.")
                else:
                    payload = df_final.to_dict(orient='records')
                    with st.spinner("Enviando dados..."):
                        try:
                            response = requests.post(webhook_url, json=payload, timeout=15)
                            if response.status_code == 200:
                                st.balloons()
                                st.success(f"Enviado! {len(df_final)} mensagens estão sendo processadas pelo n8n.")
                            else:
                                st.error(f"O n8n retornou erro {response.status_code}")
                        except Exception as e:
                            st.error(f"Erro na conexão com o Webhook: {e}")
        else:
            st.warning("⚠️ Nenhum pedido coincidente encontrado. Verifique se os números dos pedidos nas duas colagens são os mesmos.")

    except Exception as e:
        st.error(f"Erro ao processar dados: {e}")
