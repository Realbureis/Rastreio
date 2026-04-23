import streamlit as st
import pandas as pd
import io
import requests
import re

# 1. Configuração da Página (Sempre a primeira função Streamlit)
st.set_page_config(page_title="Jumbo CDP - Rastreio", layout="wide", page_icon="🚚")

# 2. Estilização do Botão (CORRIGIDO: unsafe_allow_html)
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        background-color: #007bff;
        color: white;
        font-weight: bold;
        height: 3em;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

def tratar_primeiro_nome(texto):
    """Extrai apenas o primeiro nome, garantindo que o dado seja String"""
    if pd.isna(texto) or str(texto).strip() == "" or str(texto).lower() == "nan":
        return "N/A"
    
    nome_completo = str(texto).strip()
    partes = nome_completo.split()
    
    if partes:
        return partes[0].title()
    return "N/A"

st.title("🚚 Disparador de Rastreios | Jumbo CDP")
st.markdown("---")

# --- ENTRADA DE DADOS ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("1. Dados de Vendas")
    input_vendas = st.text_area("Cole as colunas do Excel:", height=200, placeholder="N. Pedido, Cliente, Fone Fixo, Último detento cadastrado...")
with col2:
    st.subheader("2. Dados de Rastreio")
    input_rastreio = st.text_area("Cole as colunas de Rastreio:", height=200, placeholder="Pedido\tCódigo de Rastreio")

if input_vendas and input_rastreio:
    try:
        # Lendo os dados como string para evitar erro de float
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t', dtype=str)
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t', dtype=str)

        # Padronizando coluna de ligação
        if 'Pedido' in df_rastreio.columns:
            df_rastreio = df_rastreio.rename(columns={'Pedido': 'N. Pedido'})

        df_vendas['N. Pedido'] = df_vendas['N. Pedido'].str.strip()
        df_rastreio['N. Pedido'] = df_rastreio['N. Pedido'].str.strip()

        # CRUZAMENTO (INNER JOIN)
        df_final = pd.merge(df_vendas, df_rastreio[['N. Pedido', 'Código de Rastreio']], on='N. Pedido', how='inner')

        if not df_final.empty:
            # --- MAPEAMENTO DE COLUNAS ---
            mapeamento = {
                'Último detento cadastrado': 'Detento',
                'Fone Fixo': 'Fone'
            }
            df_final = df_final.rename(columns=lambda x: mapeamento.get(x.strip(), x.strip()))
            
            # Colunas essenciais para o envio
            colunas_esperadas = ['Cliente', 'Detento', 'Fone', 'Código de Rastreio']
            colunas_existentes = [c for c in colunas_esperadas if c in df_final.columns]
            
            df_envio = df_final[colunas_existentes].copy()

            # --- TRATAMENTO DOS DADOS ---
            if 'Cliente' in df_envio.columns:
                df_envio['Cliente'] = df_envio['Cliente'].apply(tratar_primeiro_nome)
            
            if 'Detento' in df_envio.columns:
                df_envio['Detento'] = df_envio['Detento'].apply(tratar_primeiro_nome)

            if 'Fone' in df_envio.columns:
                df_envio['Fone'] = df_envio['Fone'].apply(lambda x: re.sub(r'\D', '', str(x)) if pd.notna(x) else "")

            # --- EXIBIÇÃO ---
            st.success(f"✅ {len(df_envio)} jumbos prontos para envio!")
            
            st.subheader("📋 Conferência Final")
            st.dataframe(df_envio[['Cliente', 'Detento', 'Código de Rastreio']], use_container_width=True)

            # --- DISPARO ---
            st.divider()
            webhook_url = st.text_input("URL do Webhook n8n:", placeholder="https://...")
            
            if st.button("🚀 Confirmar e Enviar para o WhatsApp"):
                if webhook_url.startswith("https://"):
                    payload = df_envio.to_dict(orient='records')
                    with st.spinner("Enviando dados para o n8n..."):
                        try:
                            response = requests.post(webhook_url, json=payload, timeout=30)
                            if response.status_code == 200:
                                st.balloons()
                                st.success("Sucesso! O n8n recebeu a lista formatada.")
                            else:
                                st.error(f"Erro no n8n: {response.status_code}")
                        except Exception as e:
                            st.error(f"Erro na conexão: {e}")
                else:
                    st.warning("Insira uma URL válida.")
        else:
            st.warning("⚠️ Nenhum pedido coincidente encontrado entre as listas.")

    except Exception as e:
        st.error(f"Erro ao processar dados: {e}")
