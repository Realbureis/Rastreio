import streamlit as st
import pandas as pd
import io
import requests
import re

# 1. Configuração da Página
st.set_page_config(page_title="Jumbo CDP - Rastreio", layout="wide", page_icon="🚚")

def tratar_primeiro_nome(texto):
    """Extrai apenas o primeiro nome e coloca em Title Case"""
    txt = str(texto).strip()
    if not txt or txt.lower() in ["nan", "none", "0"]:
        return "N/A"
    # Pega a primeira palavra e formata
    return txt.split()[0].title()

st.title("🚚 Disparador de Rastreios | Jumbo CDP")
st.markdown("---")

# --- ENTRADA DE DADOS ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("1. Dados de Vendas")
    input_vendas = st.text_area("Cole aqui (Pedido, Cliente, Fone Fixo, Ultimo Detento cadastrado...):", height=200)
with col2:
    st.subheader("2. Dados de Rastreio")
    input_rastreio = st.text_area("Cole aqui (Pedido, Código de Rastreio):", height=200)

if input_vendas and input_rastreio:
    try:
        # Lendo os dados forçando String para evitar erros de tipo
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t', dtype=str).fillna("")
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t', dtype=str).fillna("")

        # Padronizando coluna de Pedido para o cruzamento
        # O sistema procura por 'Pedido' ou 'N. Pedido' em ambas
        for df in [df_vendas, df_rastreio]:
            for col in df.columns:
                if "PEDIDO" in col.upper():
                    df.rename(columns={col: 'N. Pedido'}, inplace=True)

        # Cruzamento (Merge)
        # Filtramos apenas as colunas que você especificou para o cruzamento
        df_final = pd.merge(df_vendas, df_rastreio, on='N. Pedido', how='inner')

        if not df_final.empty:
            # --- MAPEAMENTO EXATO ---
            # Aqui usamos exatamente os nomes que você forneceu
            mapeamento = {
                'Ultimo Detento cadastrado': 'Detento',
                'Fone Fixo': 'Fone',
                'Cliente': 'Cliente',
                'Código de Rastreio': 'Código de Rastreio'
            }
            
            # Renomeia as colunas para o padrão do n8n
            df_envio = df_final.rename(columns=mapeamento)
            
            # Seleciona apenas as colunas que interessam
            colunas_finais = ['Cliente', 'Detento', 'Fone', 'Código de Rastreio']
            existentes = [c for c in colunas_finais if c in df_envio.columns]
            df_envio = df_envio[existentes].copy()

            # --- FORMATAÇÃO DE DADOS ---
            if 'Cliente' in df_envio.columns:
                df_envio['Cliente'] = df_envio['Cliente'].apply(tratar_primeiro_nome)
            if 'Detento' in df_envio.columns:
                df_envio['Detento'] = df_envio['Detento'].apply(tratar_primeiro_nome)
            if 'Fone' in df_envio.columns:
                # Limpa o telefone deixando só números
                df_envio['Fone'] = df_envio['Fone'].apply(lambda x: re.sub(r'\D', '', str(x)))

            # --- EXIBIÇÃO DA TABELA ---
            st.success(f"✅ {len(df_envio)} pedidos prontos para conferência!")
            st.subheader("📋 Auditoria de Nomes (Primeiro Nome apenas)")
            st.dataframe(df_envio[['Cliente', 'Detento', 'Código de Rastreio']], use_container_width=True)

            # --- SEÇÃO DE DISPARO ---
            st.divider()
            st.subheader("🚀 Enviar para WhatsApp")
            webhook = st.text_input("URL do Webhook (Deve ser POST no n8n):", 
                                   value="https://jumbocdp.app.n8n.cloud/webhook-test/b5007963-8d59-4c88-ae17-33dfe20b9d91")
            
            if st.button("Confirmar Envio"):
                if webhook.startswith("https://"):
                    payload = df_envio.to_dict(orient='records')
                    try:
                        # Envia os dados
                        res = requests.post(webhook, json=payload, timeout=30)
                        if res.status_code in [200, 201]:
                            st.balloons()
                            st.success("Dados disparados com sucesso!")
                        else:
                            st.error(f"Erro no n8n ({res.status_code}): Verifique se o nó está como POST.")
                    except Exception as e:
                        st.error(f"Erro de conexão: {e}")
                else:
                    st.warning("⚠️ Insira uma URL de Webhook válida.")
        else:
            st.warning("⚠️ Nenhum pedido coincidente encontrado entre as tabelas.")
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
