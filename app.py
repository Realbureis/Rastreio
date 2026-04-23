import streamlit as st
import pandas as pd
import io
import requests
import re

# 1. Configuração da Página
st.set_page_config(page_title="Jumbo CDP - Rastreio", layout="wide", page_icon="🚚")

def tratar_primeiro_nome(texto):
    """Extrai apenas o primeiro nome com segurança total contra erros de float/nulos"""
    txt = str(texto).strip()
    if not txt or txt.lower() == "nan":
        return "N/A"
    return txt.split()[0].title()

st.title("🚚 Disparador de Rastreios | Jumbo CDP")
st.markdown("---")

# --- ENTRADA DE DADOS ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("1. Dados de Vendas")
    input_vendas = st.text_area("Cole aqui:", height=200, placeholder="Dica: Copie os cabeçalhos da planilha")
with col2:
    st.subheader("2. Dados de Rastreio")
    input_rastreio = st.text_area("Cole aqui:", height=200, placeholder="Pedido\tCódigo de Rastreio")

if input_vendas and input_rastreio:
    try:
        # Lendo tudo como String para evitar erro de 'float'
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t', dtype=str).fillna("")
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t', dtype=str).fillna("")

        # Padronizando coluna de Pedido
        if 'Pedido' in df_rastreio.columns:
            df_rastreio = df_rastreio.rename(columns={'Pedido': 'N. Pedido'})

        df_vendas['N. Pedido'] = df_vendas['N. Pedido'].str.strip()
        df_rastreio['N. Pedido'] = df_rastreio['N. Pedido'].str.strip()

        # CRUZAMENTO
        df_final = pd.merge(df_vendas, df_rastreio[['N. Pedido', 'Código de Rastreio']], on='N. Pedido', how='inner')

        if not df_final.empty:
            # --- AUTO-MAPEAMENTO INTELIGENTE (Resolve o erro de Index) ---
            mapping = {}
            for col in df_final.columns:
                c_upper = col.upper()
                if "CLIENTE" in c_upper: mapping[col] = "Cliente"
                if "DETENTO" in c_upper: mapping[col] = "Detento"
                if "FIXO" in c_upper or "FONE" in c_upper: mapping[col] = "Fone"
                if "RASTREIO" in c_upper: mapping[col] = "Código de Rastreio"

            df_envio = df_final.rename(columns=mapping)
            
            # Garante que as colunas essenciais existam no resultado
            colunas_finais = ["Cliente", "Detento", "Código de Rastreio", "Fone"]
            existentes = [c for c in colunas_finais if c in df_envio.columns]
            df_envio = df_envio[existentes]

            # --- FORMATAÇÃO DE TEXTO ---
            if 'Cliente' in df_envio.columns:
                df_envio['Cliente'] = df_envio['Cliente'].apply(tratar_primeiro_nome)
            if 'Detento' in df_envio.columns:
                df_envio['Detento'] = df_envio['Detento'].apply(tratar_primeiro_nome)
            if 'Fone' in df_envio.columns:
                df_envio['Fone'] = df_envio['Fone'].apply(lambda x: re.sub(r'\D', '', str(x)))

            # --- EXIBIÇÃO ---
            st.success(f"✅ {len(df_envio)} jumbos prontos para envio!")
            st.dataframe(df_envio[["Cliente", "Detento", "Código de Rastreio"]], use_container_width=True)

            # --- DISPARO ---
            st.divider()
            webhook = st.text_input("URL do Webhook n8n:", "https://")
            
            if st.button("🚀 Confirmar e Disparar"):
                if "https://" in webhook and len(webhook) > 20:
                    payload = df_envio.to_dict(orient='records')
                    res = requests.post(webhook, json=payload, timeout=30)
                    if res.status_code == 200:
                        st.balloons()
                        st.success("Enviado com sucesso!")
                    else:
                        st.error(f"Erro {res.status_code}")
                else:
                    st.warning("URL Inválida")
        else:
            st.warning("Nenhum pedido coincidente.")
    except Exception as e:
        st.error(f"Erro: {e}")
