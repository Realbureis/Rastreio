import streamlit as st
import pandas as pd
import io
import requests
import re

# Configuração da Página
st.set_page_config(page_title="Jumbo CDP - Rastreio", layout="wide", page_icon="🚚")

# Estilização Customizada
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; background-color: #007bff; color: white; border-radius: 5px; }
    </style>
    """, unsafe_allow_stdio=True)

st.title("🚚 Disparador de Rastreios | Jumbo CDP")
st.markdown("Cruze os dados de vendas com os rastreios e dispare direto para o WhatsApp via n8n.")

# --- ENTRADA DE DADOS ---
col1, col2 = st.columns(2)
with col1:
    input_vendas = st.text_area("1. Cole dados de Vendas (N. Pedido, Cliente, Fone, Detento...):", height=200, placeholder="Cole as colunas do Excel/Planilha aqui...")
with col2:
    input_rastreio = st.text_area("2. Cole dados de Rastreio (Pedido, Código de Rastreio):", height=200, placeholder="Pedido\tCódigo de Rastreio...")

if input_vendas and input_rastreio:
    try:
        # Lendo os dados (tratando Tabulação como separador padrão de colagem do Excel)
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t')
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t')

        # Padronizando coluna de ligação para o cruzamento
        if 'Pedido' in df_rastreio.columns:
            df_rastreio = df_rastreio.rename(columns={'Pedido': 'N. Pedido'})

        # Limpeza para garantir o cruzamento (Remover espaços e converter para String)
        df_vendas['N. Pedido'] = df_vendas['N. Pedido'].astype(str).str.strip()
        df_rastreio['N. Pedido'] = df_rastreio['N. Pedido'].astype(str).str.strip()

        # CRUZAMENTO (INNER MERGE)
        # Mantém apenas os pedidos que possuem código de rastreio
        df_final = pd.merge(df_vendas, df_rastreio[['N. Pedido', 'Código de Rastreio']], on='N. Pedido', how='inner')

        if not df_final.empty:
            # --- TRATAMENTO DE COLUNAS PARA O N8N ---
            # Mapeamos o nome complexo para o nome que o template beta_rastreio_4 espera
            colunas_map = {
                'Último detento cadastrado': 'Detento',
                'Cliente': 'Cliente',
                'Fone': 'Fone',
                'Código de Rastreio': 'Código de Rastreio'
            }
            
            # Renomeia apenas as colunas existentes para evitar erros
            df_processado = df_final.rename(columns=colunas_map)
            
            # Colunas que vamos exibir e enviar
            colunas_vips = ['Cliente', 'Detento', 'Código de Rastreio', 'Fone']
            
            # Verifica se todas as colunas necessárias estão presentes
            colunas_presentes = [c for c in colunas_vips if c in df_processado.columns]
            df_display = df_processado[colunas_presentes].copy()

            # Limpeza de Telefone (Apenas números)
            if 'Fone' in df_display.columns:
                df_display['Fone'] = df_display['Fone'].astype(str).apply(lambda x: re.sub(r'\D', '', x))

            # --- EXIBIÇÃO ---
            st.success(f"🔥 Sucesso! {len(df_display)} pedidos prontos para envio.")
            
            st.subheader("📋 Conferência de Dados")
            # Exibimos apenas Cliente, Detento e Rastreio para conferência limpa
            st.dataframe(
                df_display[['Cliente', 'Detento', 'Código de Rastreio']], 
                use_container_width=True
            )

            # --- INTEGRAÇÃO N8N ---
            st.divider()
            webhook_url = st.text_input("Cole sua URL de Produção do Webhook n8n:", "https://")
            
            if st.button("🚀 Confirmar e Disparar para n8n"):
                if "https://" in webhook_url and len(webhook_url) > 15:
                    # Converte para lista de dicionários (JSON)
                    payload = df_display.to_dict(orient='records')
                    
                    with st.spinner("Enviando para o n8n..."):
                        try:
                            # Envio em lote para o Webhook
                            response = requests.post(webhook_url, json=payload, timeout=20)
                            
                            if response.status_code == 200:
                                st.balloons()
                                st.success(f"Excelente, Victor! {len(payload)} mensagens enviadas para a fila do n8n.")
                            else:
                                st.error(f"Erro no n8n (Status {response.status_code}): {response.text}")
                        except Exception as e:
                            st.error(f"Erro na conexão com o servidor: {e}")
                else:
                    st.warning("Por favor, insira uma URL de Webhook válida.")
        else:
            st.warning("⚠️ Nenhum pedido coincidente encontrado entre as duas listas.")

    except Exception as e:
        st.error(f"Erro ao processar os dados: {e}. Verifique se você copiou os cabeçalhos corretamente.")
