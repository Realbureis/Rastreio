import streamlit as st
import pandas as pd
import io
import requests
import re

# 1. Configuração da Página
st.set_page_config(page_title="Jumbo CDP - Full Data", layout="wide", page_icon="🚚")

def tratar_primeiro_nome(texto):
    """Extrai apenas o primeiro nome em Title Case"""
    txt = str(texto).strip()
    if not txt or txt.lower() in ["nan", "none", "0", "-"]:
        return "N/A"
    return txt.split()[0].title()

st.title("🚚 Disparador de Rastreios | Jumbo CDP")
st.markdown("---")

# --- ENTRADA DE DADOS ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("1. Dados de Vendas")
    input_vendas = st.text_area("Cole os dados de Vendas aqui:", height=200)
with col2:
    st.subheader("2. Dados de Rastreio")
    input_rastreio = st.text_area("Cole os dados de Rastreio aqui:", height=200)

if input_vendas and input_rastreio:
    try:
        # Lendo os dados como String
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t', dtype=str).fillna("")
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t', dtype=str).fillna("")

        # --- PADRONIZAÇÃO DE COLUNAS ---
        def auto_mapear(df):
            mapa = {}
            for col in df.columns:
                c_upper = col.upper().strip()
                if "PEDIDO" in c_upper: mapa[col] = "ID_PEDIDO"
                elif "CLIENTE" in c_upper: mapa[col] = "Cliente"
                elif "DETENTO" in c_upper or "CADASTRA" in c_upper: mapa[col] = "Detento"
                elif "FONE" in c_upper or "FIXO" in c_upper: mapa[col] = "Fone"
                elif "RASTREIO" in c_upper: mapa[col] = "Código de Rastreio"
            return df.rename(columns=mapa)

        df_vendas = auto_mapear(df_vendas)
        df_rastreio = auto_mapear(df_rastreio)

        # Limpeza das chaves para o Join
        df_vendas['ID_PEDIDO'] = df_vendas['ID_PEDIDO'].str.strip()
        df_rastreio['ID_PEDIDO'] = df_rastreio['ID_PEDIDO'].str.strip()

        # --- CRUZAMENTO (INNER JOIN) ---
        # Trazemos o rastreio para dentro da tabela de vendas mantendo tudo
        df_final = pd.merge(df_vendas, df_rastreio[['ID_PEDIDO', 'Código de Rastreio']], on='ID_PEDIDO', how='inner')

        if not df_final.empty:
            # Remove duplicatas de colunas
            df_final = df_final.loc[:, ~df_final.columns.duplicated()]

            # --- FORMATAÇÃO DAS COLUNAS PRINCIPAIS ---
            if 'Cliente' in df_final.columns:
                df_final['Cliente'] = df_final['Cliente'].apply(tratar_primeiro_nome)
            if 'Detento' in df_final.columns:
                df_final['Detento'] = df_final['Detento'].apply(tratar_primeiro_nome)
            if 'Fone' in df_final.columns:
                df_final['Fone'] = df_final['Fone'].apply(lambda x: re.sub(r'\D', '', str(x)))

            # --- ORGANIZAÇÃO DE COLUNAS (Visualização) ---
            # Colocamos as suas colunas favoritas no começo, e o resto depois
            cols_principais = ['ID_PEDIDO', 'Cliente', 'Detento', 'Fone', 'Código de Rastreio']
            cols_principais = [c for c in cols_principais if c in df_final.columns]
            cols_restantes = [c for c in df_final.columns if c not in cols_principais]
            
            # DataFrame final ordenado para o Preview e para o Envio
            df_envio = df_final[cols_principais + cols_restantes].copy()

            # --- EXIBIÇÃO DA TABELA ---
            st.success(f"✅ {len(df_envio)} pedidos processados com sucesso!")
            
            st.subheader("📋 Preview da Tabela (Colunas Principais + Dados Extras)")
            st.dataframe(df_envio, use_container_width=True)

            # --- SEÇÃO DE DISPARO ---
            st.divider()
            webhook = st.text_input("URL do Webhook (POST):", value="https://jumbocdp.app.n8n.cloud/webhook/b5007963-8d59-4c88-ae17-33dfe20b9d91")
            
            if st.button("Confirmar Envio para WhatsApp"):
                if webhook.startswith("https://"):
                    payload = df_envio.to_dict(orient='records')
                    try:
                        res = requests.post(webhook, json=payload, timeout=40)
                        if res.status_code in [200, 201]:
                            st.balloons()
                            st.success(f"Show! {len(payload)} usuários enviados com dados completos para o n8n.")
                        else:
                            st.error(f"Erro {res.status_code}: Verifique o Webhook.")
                    except Exception as e:
                        st.error(f"Erro de conexão: {e}")
        else:
            st.warning("⚠️ Nenhum pedido coincidente encontrado.")
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
