import streamlit as st
import pandas as pd
import io
import requests
import re

# 1. Configuração da Página
st.set_page_config(page_title="Jumbo CDP - Rastreio", layout="wide", page_icon="🚚")

# 2. Estilização do Botão e Layout
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
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

def tratar_primeiro_nome(texto):
    """Extrai apenas o primeiro nome e coloca em Title Case"""
    if pd.isna(texto) or str(texto).strip() == "":
        return texto
    # Pega a primeira parte antes do espaço e formata
    primeiro_nome = str(texto).split()[0]
    return primeiro_nome.strip().title()

st.title("🚚 Disparador de Rastreios | Jumbo CDP")
st.markdown("---")

# --- ENTRADA DE DADOS ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("1. Dados de Vendas")
    input_vendas = st.text_area("Cole as colunas (Pedido, Cliente, Fone, Detento...):", height=200, placeholder="Copie do Excel com os cabeçalhos")
with col2:
    st.subheader("2. Dados de Rastreio")
    input_rastreio = st.text_area("Cole as colunas (Pedido, Código de Rastreio):", height=200, placeholder="Pedido\tCódigo de Rastreio")

if input_vendas and input_rastreio:
    try:
        # Lendo os dados (Excel usa tabulação '\t')
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t')
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t')

        # Padronizando coluna de ligação
        if 'Pedido' in df_rastreio.columns:
            df_rastreio = df_rastreio.rename(columns={'Pedido': 'N. Pedido'})

        # Limpeza para garantir o cruzamento
        df_vendas['N. Pedido'] = df_vendas['N. Pedido'].astype(str).str.strip()
        df_rastreio['N. Pedido'] = df_rastreio['N. Pedido'].astype(str).str.strip()

        # CRUZAMENTO (INNER JOIN)
        df_final = pd.merge(df_vendas, df_rastreio[['N. Pedido', 'Código de Rastreio']], on='N. Pedido', how='inner')

        if not df_final.empty:
            # --- TRATAMENTO E FORMATAÇÃO ---
            
            # Mapeamento para o template beta_rastreio_4
            colunas_map = {
                'Último detento cadastrado': 'Detento',
                'Cliente': 'Cliente',
                'Fone': 'Fone',
                'Código de Rastreio': 'Código de Rastreio'
            }
            
            df_processado = df_final.rename(columns=colunas_map)
            
            # Filtrando apenas o necessário
            colunas_vips = ['Cliente', 'Detento', 'Código de Rastreio', 'Fone']
            colunas_presentes = [c for c in colunas_vips if c in df_processado.columns]
            df_display = df_processado[colunas_presentes].copy()

            # EXTRAÇÃO DE PRIMEIRO NOME (Sua solicitação estratégica)
            if 'Cliente' in df_display.columns:
                df_display['Cliente'] = df_display['Cliente'].apply(tratar_primeiro_nome)
            if 'Detento' in df_display.columns:
                df_display['Detento'] = df_display['Detento'].apply(tratar_primeiro_nome)

            # Limpeza de Telefone (Apenas números para a API)
            if 'Fone' in df_display.columns:
                df_display['Fone'] = df_display['Fone'].astype(str).apply(lambda x: re.sub(r'\D', '', x))

            # --- INTERFACE DE CONFERÊNCIA ---
            st.success(f"✅ {len(df_display)} pedidos prontos para envio (Nomes Encurtados)!")
            
            st.subheader("📋 Conferência visual dos nomes")
            st.dataframe(
                df_display[['Cliente', 'Detento', 'Código de Rastreio']], 
                use_container_width=True
            )

            # --- INTEGRAÇÃO N8N ---
            st.markdown("### 🚀 Finalizar Envio")
            webhook_url = st.text_input("URL do Webhook do n8n:", placeholder="https://seu-n8n.com/webhook/...")
            
            if st.button("Confirmar e Enviar para o WhatsApp"):
                if webhook_url.startswith("https://"):
                    payload = df_display.to_dict(orient='records')
                    
                    with st.spinner("Disparando para o n8n..."):
                        try:
                            response = requests.post(webhook_url, json=payload, timeout=25)
                            if response.status_code == 200:
                                st.balloons()
                                st.success("Show! Dados enviados com nomes encurtados.")
                            else:
                                st.error(f"Erro no n8n: {response.status_code}")
                        except Exception as e:
                            st.error(f"Falha na conexão: {e}")
                else:
                    st.warning("Insira uma URL de Webhook válida.")
        else:
            st.warning("⚠️ Nenhum pedido coincidente encontrado.")

    except Exception as e:
        st.error(f"Erro ao processar dados: {e}")
