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
        # Lendo os dados
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t').fillna("")
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t').fillna("")

        # VERIFICAÇÃO CRÍTICA: Se o DF estiver vazio (Erro 0), para aqui
        if df_vendas.empty or df_rastreio.empty:
            st.error("Erro: Uma das colagens parece estar vazia ou mal formatada.")
            st.stop()

        # Converte tudo para string DEPOIS de verificar se não está vazio
        df_vendas = df_vendas.astype(str)
        df_rastreio = df_rastreio.astype(str)

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

        # Limpeza das chaves de cruzamento
        if "ID_PEDIDO" in df_vendas.columns:
            df_vendas["ID_PEDIDO"] = df_vendas["ID_PEDIDO"].apply(lambda x: str(x).strip())
        if "ID_PEDIDO" in df_rastreio.columns:
            df_rastreio["ID_PEDIDO"] = df_rastreio["ID_PEDIDO"].apply(lambda x: str(x).strip())

        # --- CRUZAMENTO (INNER JOIN) ---
        if "ID_PEDIDO" in df_vendas.columns and "ID_PEDIDO" in df_rastreio.columns:
            # Pegamos o rastreio e garantimos que o ID_PEDIDO seja a chave
            df_rastreio_min = df_rastreio[["ID_PEDIDO", "Código de Rastreio"]] if "Código de Rastreio" in df_rastreio.columns else df_rastreio
            df_final = pd.merge(df_vendas, df_rastreio_min, on='ID_PEDIDO', how='inner')
        else:
            st.warning("Coluna 'ID_PEDIDO' não identificada. Verifique o cabeçalho.")
            st.stop()

        if not df_final.empty:
            # Remove duplicatas de colunas
            df_final = df_final.loc[:, ~df_final.columns.duplicated()]

            # --- FORMATAÇÃO ---
            if 'Cliente' in df_final.columns:
                df_final['Cliente'] = df_final['Cliente'].apply(tratar_primeiro_nome)
            if 'Detento' in df_final.columns:
                df_final['Detento'] = df_final['Detento'].apply(tratar_primeiro_nome)
            if 'Fone' in df_final.columns:
                df_final['Fone'] = df_final['Fone'].apply(lambda x: re.sub(r'\D', '', str(x)))

            # --- ORGANIZAÇÃO DE COLUNAS ---
            prioridade = ['ID_PEDIDO', 'Cliente', 'Detento', 'Fone', 'Código de Rastreio']
            existentes = [c for c in prioridade if c in df_final.columns]
            restantes = [c for c in df_final.columns if c not in existentes]
            
            df_envio = df_final[existentes + restantes].copy()

            # --- EXIBIÇÃO ---
            st.success(f"✅ {len(df_envio)} pedidos prontos para a Jumbo!")
            st.dataframe(df_envio, use_container_width=True)

            # --- DISPARO ---
            st.divider()
            webhook = st.text_input("URL do Webhook:", value="https://jumbocdp.app.n8n.cloud/webhook/b5007963-8d59-4c88-ae17-33dfe20b9d91")
            
            if st.button("Confirmar Envio Total"):
                payload = df_envio.to_dict(orient='records')
                res = requests.post(webhook, json=payload, timeout=40)
                if res.status_code in [200, 201]:
                    st.balloons()
                    st.success("Dados enviados com sucesso!")
        else:
            st.warning("⚠️ Nenhum cruzamento encontrado. Verifique se os números dos pedidos coincidem.")

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
