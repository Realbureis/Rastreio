import streamlit as st
import pandas as pd
import io
import requests
import re

# 1. Configuração da Página
st.set_page_config(page_title="Jumbo CDP - Rastreio", layout="wide", page_icon="🚚")

def tratar_primeiro_nome(texto):
    """Extrai apenas o primeiro nome em Title Case"""
    txt = str(texto).strip()
    if not txt or txt.lower() in ["nan", "none", "0"]:
        return "N/A"
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
        # Lendo os dados como String
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t', dtype=str).fillna("")
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t', dtype=str).fillna("")

        # --- PADRONIZAÇÃO DE COLUNAS (Evita o erro 'not unique') ---
        def padronizar_coluna_pedido(df):
            for col in df.columns:
                if "PEDIDO" in col.upper():
                    # Renomeia e remove outras colunas que possam ter nomes parecidos
                    df = df.rename(columns={col: 'ID_PEDIDO'})
                    break
            return df

        df_vendas = padronizar_coluna_pedido(df_vendas)
        df_rastreio = padronizar_coluna_pedido(df_rastreio)

        # Limpeza das chaves de cruzamento
        df_vendas['ID_PEDIDO'] = df_vendas['ID_PEDIDO'].str.strip()
        df_rastreio['ID_PEDIDO'] = df_rastreio['ID_PEDIDO'].str.strip()

        # CRUZAMENTO (INNER JOIN) - Usando o nome temporário ID_PEDIDO para evitar duplicidade
        df_final = pd.merge(df_vendas, df_rastreio[['ID_PEDIDO', 'Código de Rastreio']], on='ID_PEDIDO', how='inner')

        if not df_final.empty:
            # --- MAPEAMENTO DOS SEUS CAMPOS ---
            mapeamento = {
                'Ultimo Detento cadastrado': 'Detento',
                'Fone Fixo': 'Fone',
                'Cliente': 'Cliente',
                'Código de Rastreio': 'Código de Rastreio',
                'ID_PEDIDO': 'N. Pedido'
            }
            
            # Renomeia para o padrão final
            df_envio = df_final.rename(columns=mapeamento)
            
            # Seleciona apenas as colunas necessárias para o n8n
            colunas_finais = ['Cliente', 'Detento', 'Fone', 'Código de Rastreio', 'N. Pedido']
            existentes = [c for c in colunas_finais if c in df_envio.columns]
            df_envio = df_envio[existentes].copy()

            # --- FORMATAÇÃO ---
            if 'Cliente' in df_envio.columns:
                df_envio['Cliente'] = df_envio['Cliente'].apply(tratar_primeiro_nome)
            if 'Detento' in df_envio.columns:
                df_envio['Detento'] = df_envio['Detento'].apply(tratar_primeiro_nome)
            if 'Fone' in df_envio.columns:
                df_envio['Fone'] = df_envio['Fone'].apply(lambda x: re.sub(r'\D', '', str(x)))

            # --- EXIBIÇÃO DA TABELA ---
            st.success(f"✅ {len(df_envio)} pedidos prontos para conferência!")
            st.subheader("📋 Auditoria de Dados (Primeiro Nome)")
            st.dataframe(df_envio[['N. Pedido', 'Cliente', 'Detento', 'Código de Rastreio']], use_container_width=True)

            # --- SEÇÃO DE DISPARO ---
            st.divider()
            webhook = st.text_input("URL do Webhook (Certifique-se de estar como POST no n8n):", 
                                   value="https://jumbocdp.app.n8n.cloud/webhook-test/b5007963-8d59-4c88-ae17-33dfe20b9d91")
            
            if st.button("Confirmar Envio para WhatsApp"):
                if webhook.startswith("https://"):
                    payload = df_envio.to_dict(orient='records')
                    try:
                        # Envio via POST
                        res = requests.post(webhook, json=payload, timeout=30)
                        if res.status_code in [200, 201]:
                            st.balloons()
                            st.success("Tudo certo! Dados enviados para o n8n.")
                        else:
                            st.error(f"Erro no n8n ({res.status_code}): Verifique se o método é POST.")
                    except Exception as e:
                        st.error(f"Erro de conexão: {e}")
                else:
                    st.warning("Insira uma URL de Webhook válida.")
        else:
            st.warning("⚠️ Nenhum pedido coincidente encontrado.")
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
