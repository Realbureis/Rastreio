import streamlit as st
import pandas as pd
import io
import requests
import re

# 1. Configuração da Página
st.set_page_config(page_title="Jumbo CDP - Rastreio", layout="wide", page_icon="🚚")

# 2. Estilização do Botão
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
    """Extrai apenas o primeiro nome e coloca em Title Case"""
    if pd.isna(texto) or str(texto).strip() == "":
        return "N/A"
    partes = str(texto).split()
    return partes[0].strip().title() if partes else "N/A"

st.title("🚚 Disparador de Rastreios | Jumbo CDP")
st.markdown("---")

# --- ENTRADA DE DADOS ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("1. Dados de Vendas")
    input_vendas = st.text_area("Cole aqui (N. Pedido, Cliente, Fone Fixo, Último detento...):", height=200)
with col2:
    st.subheader("2. Dados de Rastreio")
    input_rastreio = st.text_area("Cole aqui (Pedido, Código de Rastreio):", height=200)

if input_vendas and input_rastreio:
    try:
        # Lendo os dados com separador de tabulação (Excel)
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t')
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t')

        # Padronizando coluna de ligação
        if 'Pedido' in df_rastreio.columns:
            df_rastreio = df_rastreio.rename(columns={'Pedido': 'N. Pedido'})

        df_vendas['N. Pedido'] = df_vendas['N. Pedido'].astype(str).str.strip()
        df_rastreio['N. Pedido'] = df_rastreio['N. Pedido'].astype(str).str.strip()

        # CRUZAMENTO
        df_final = pd.merge(df_vendas, df_rastreio[['N. Pedido', 'Código de Rastreio']], on='N. Pedido', how='inner')

        if not df_final.empty:
            # --- MAPEAMENTO DE COLUNAS (Ajustado para Fone Fixo) ---
            mapeamento = {
                'Último detento cadastrado': 'Detento',
                'Fone Fixo': 'Fone'
            }
            
            # Renomeia as colunas se elas existirem na planilha colada
            df_final = df_final.rename(columns=lambda x: mapeamento.get(x, x))
            
            # Garantimos que as colunas essenciais existam no DataFrame processado
            colunas_esperadas = ['Cliente', 'Detento', 'Fone', 'Código de Rastreio']
            colunas_existentes = [c for c in colunas_esperadas if c in df_final.columns]
            
            df_envio = df_final[colunas_existentes].copy()

            # --- FORMATAÇÃO: Primeiro Nome e Title Case ---
            if 'Cliente' in df_envio.columns:
                df_envio['Cliente'] = df_envio['Cliente'].apply(tratar_primeiro_nome)
            
            if 'Detento' in df_envio.columns:
                df_envio['Detento'] = df_envio['Detento'].apply(tratar_primeiro_nome)

            # --- LIMPEZA DE TELEFONE ---
            if 'Fone' in df_envio.columns:
                df_envio['Fone'] = df_envio['Fone'].astype(str).apply(lambda x: re.sub(r'\D', '', x))

            # --- EXIBIÇÃO ---
            st.success(f"✅ {len(df_envio)} jumbos prontos para envio!")
            
            st.subheader("📋 Conferência (Apenas primeiro nome)")
            # Exibe a tabela sem mostrar o Fone para ficar mais limpo
            st.dataframe(df_envio[['Cliente', 'Detento', 'Código de Rastreio']], use_container_width=True)

            # --- DISPARO ---
            st.divider()
            webhook_url = st.text_input("URL do Webhook n8n:", placeholder="https://...")
            
            if st.button("🚀 Confirmar e Enviar para o WhatsApp"):
                if webhook_url.startswith("https://"):
                    payload = df_envio.to_dict(orient='records')
                    with st.spinner("Enviando dados formatados..."):
                        try:
                            response = requests.post(webhook_url, json=payload, timeout=25)
                            if response.status_code == 200:
                                st.balloons()
                                st.success(f"Show! {len(payload)} envios entregues com sucesso.")
                            else:
                                st.error(f"Erro no n8n: {response.status_code}")
                        except Exception as e:
                            st.error(f"Erro na conexão: {e}")
                else:
                    st.warning("Insira uma URL de Webhook válida.")
        else:
            st.warning("⚠️ Nenhum pedido coincidente encontrado entre as listas.")

    except Exception as e:
        st.error(f"Erro ao processar dados: {e}")
