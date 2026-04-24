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
        # Lendo os dados e FORÇANDO tudo para string imediatamente
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t').fillna("").astype(str)
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t').fillna("").astype(str)

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

        # Limpeza segura das chaves (usando apply para garantir que não dê erro de atributo)
        if "ID_PEDIDO" in df_vendas.columns:
            df_vendas["ID_PEDIDO"] = df_vendas["ID_PEDIDO"].apply(lambda x: str(x).strip())
        if "ID_PEDIDO" in df_rastreio.columns:
            df_rastreio["ID_PEDIDO"] = df_rastreio["ID_PEDIDO"].apply(lambda x: str(x).strip())

        # --- CRUZAMENTO (INNER JOIN) ---
        if "ID_PEDIDO" in df_vendas.columns and "ID_PEDIDO" in df_rastreio.columns:
            # Selecionamos apenas o necessário da tabela de rastreio para o join
            cols_rastreio = [c for c in ["ID_PEDIDO", "Código de Rastreio"] if c in df_rastreio.columns]
            df_final = pd.merge(df_vendas, df_rastreio[cols_rastreio], on='ID_PEDIDO', how='inner')
        else:
            df_final = pd.DataFrame()

        if not df_final.empty:
            df_final = df_final.loc[:, ~df_final.columns.duplicated()]

            # --- FORMATAÇÃO DAS COLUNAS PRINCIPAIS ---
            if 'Cliente' in df_final.columns:
                df_final['Cliente'] = df_final['Cliente'].apply(tratar_primeiro_nome)
            if 'Detento' in df_final.columns:
                df_final['Detento'] = df_final['Detento'].apply(tratar_primeiro_nome)
            if 'Fone' in df_final.columns:
                df_final['Fone'] = df_final['Fone'].apply(lambda x: re.sub(r'\D', '', str(x)))

            # --- ORGANIZAÇÃO DE COLUNAS ---
            cols_prioridade = ['ID_PEDIDO', 'Cliente', 'Detento', 'Fone', 'Código de Rastreio']
            existentes = [c for c in cols_prioridade if c in df_final.columns]
            extras = [c for c in df_final.columns if c not in existentes]
            
            df_envio = df_final[existentes + extras].copy()

            # --- EXIBIÇÃO ---
            st.success(f"✅ {len(df_envio)} pedidos prontos!")
            st.dataframe(df_envio, use_container_width=True)

            # --- DISPARO ---
            st.divider()
            webhook = st.text_input("URL do Webhook (POST):", value="https://jumbocdp.app.n8n.cloud/webhook/b5007963-8d59-4c88-ae17-33dfe20b9d91")
            
            if st.button("Confirmar Envio para WhatsApp"):
                if webhook.startswith("https://"):
                    payload = df_envio.to_dict(orient='records')
                    try:
                        res = requests.post(webhook, json=payload, timeout=40)
                        if res.status_code in [200, 201]:
                            st.balloons()
                            st.success(f"Enviado! {len(payload)} itens no n8n.")
                        else:
                            st.error(f"Erro {res.status_code}")
                    except Exception as e:
                        st.error(f"Erro: {e}")
        else:
            st.warning("⚠️ IDs não coincidem.")
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
