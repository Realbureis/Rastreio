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
    if not txt or txt.lower() in ["nan", "none", "0", "-"]:
        return "N/A"
    return txt.split()[0].title()

def limpar_telefone(valor):
    """Remove ( ) - e espaços, retornando apenas números"""
    if not valor or str(valor).lower() in ["nan", "none", "0", ""]:
        return None
    fone_limpo = re.sub(r'\D', '', str(valor))
    return fone_limpo if len(fone_limpo) >= 8 else None

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
        # Lendo como String para preservar o formato original antes da limpeza
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t', dtype=str).fillna("")
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t', dtype=str).fillna("")

        # --- PADRONIZAÇÃO AUTOMÁTICA DE COLUNAS ---
        def auto_mapear(df):
            mapa = {}
            for col in df.columns:
                c_upper = col.upper().strip()
                if "PEDIDO" in c_upper: mapa[col] = "ID_PEDIDO"
                elif "CLIENTE" in c_upper: mapa[col] = "Cliente"
                elif "DETENTO" in c_upper or "CADASTRA" in c_upper: mapa[col] = "Detento"
                elif "RASTREIO" in c_upper: mapa[col] = "Código de Rastreio"
            return df.rename(columns=mapa)

        df_vendas = auto_mapear(df_vendas)
        df_rastreio = auto_mapear(df_rastreio)

        # Limpeza das chaves de cruzamento
        df_vendas['ID_PEDIDO'] = df_vendas['ID_PEDIDO'].str.strip()
        df_rastreio['ID_PEDIDO'] = df_rastreio['ID_PEDIDO'].str.strip()

        # --- CRUZAMENTO (INNER JOIN) ---
        # Cruzamos o rastreio com a base TOTAL de vendas para não perder nenhuma coluna
        df_final = pd.merge(df_vendas, df_rastreio[['ID_PEDIDO', 'Código de Rastreio']], on='ID_PEDIDO', how='inner')

        if not df_final.empty:
            # --- LÓGICA DE TELEFONE (CELULAR > FONE FIXO) ---
            # Limpamos ambos os campos que vêm com (11) 91111-1111
            df_final['celular_limpo'] = df_final.get('Celular', '').apply(limpar_telefone)
            df_final['fixo_limpo'] = df_final.get('Fone Fixo', '').apply(limpar_telefone)

            # Define a coluna 'Fone' final: se celular_limpo existir use ele, senão use fixo_limpo
            df_final['Fone'] = df_final['celular_limpo'].fillna(df_final['fixo_limpo'])

            # FILTRO: Remove quem não tem nenhum telefone válido (None)
            df_final = df_final.dropna(subset=['Fone']).copy()

            if not df_final.empty:
                # --- FORMATAÇÃO DE NOMES ---
                if 'Cliente' in df_final.columns:
                    df_final['Cliente'] = df_final['Cliente'].apply(tratar_primeiro_nome)
                if 'Detento' in df_final.columns:
                    df_final['Detento'] = df_final['Detento'].apply(tratar_primeiro_nome)

                # --- ORGANIZAÇÃO DE COLUNAS ---
                # Colocamos o que você audita no início, mas o resto vai junto!
                vips = ['ID_PEDIDO', 'Cliente', 'Detento', 'Fone', 'Código de Rastreio']
                cols_vips = [c for c in vips if c in df_final.columns]
                outras_colunas = [c for c in df_final.columns if c not in cols_vips and c not in ['celular_limpo', 'fixo_limpo']]
                
                df_envio = df_final[cols_vips + outras_colunas].copy()

                # --- EXIBIÇÃO ---
                st.success(f"✅ {len(df_envio)} pedidos cruzados e validados!")
                st.dataframe(df_envio, use_container_width=True)

                # --- DISPARO ---
                st.divider()
                webhook = st.text_input("URL do Webhook:", value="https://jumbocdp.app.n8n.cloud/webhook/b5007963-8d59-4c88-ae17-33dfe20b9d91")
                
                if st.button("Confirmar Envio Total para n8n"):
                    payload = df_envio.to_dict(orient='records')
                    res = requests.post(webhook, json=payload, timeout=45)
                    if res.status_code in [200, 201]:
                        st.balloons()
                        st.success(f"Show! {len(payload)} usuários enviados com todos os dados.")
            else:
                st.warning("⚠️ Nenhum lead com telefone válido após a limpeza dos caracteres.")
        else:
            st.warning("⚠️ Nenhum pedido coincidente encontrado entre as listas.")
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
