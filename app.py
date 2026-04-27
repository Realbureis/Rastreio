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

def processar_fone_jumbo(row):
    """Fallback Fixo > Celular | Limpa | Adiciona 55"""
    fixo = str(row.get('Fone Fixo', '')).strip()
    cel = str(row.get('Celular', '')).strip()
    
    # Prioridade Fone Fixo
    bruto = fixo if fixo and fixo.lower() not in ["nan", "none", "0", ""] else cel
    limpo = re.sub(r'\D', '', bruto)
    
    if limpo and len(limpo) >= 8:
        return '55' + limpo if not limpo.startswith('55') else limpo
    return None

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
        # Lendo os dados como String (Mantendo sua base original)
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

        df_vendas = df_vendas.loc[:, ~df_vendas.columns.duplicated()]
        df_rastreio = df_rastreio.loc[:, ~df_rastreio.columns.duplicated()]

        df_vendas['ID_PEDIDO'] = df_vendas['ID_PEDIDO'].str.strip()
        df_rastreio['ID_PEDIDO'] = df_rastreio['ID_PEDIDO'].str.strip()

        # CRUZAMENTO (INNER JOIN)
        # Pegamos o ID_PEDIDO e Código de Rastreio, mas fazemos o join na base TOTAL de vendas
        df_final = pd.merge(df_vendas, df_rastreio[['ID_PEDIDO', 'Código de Rastreio']], on='ID_PEDIDO', how='inner')

        if not df_final.empty:
            # --- NOVAS CONDIÇÕES ---
            df_final['Fone'] = df_final.apply(processar_fone_jumbo, axis=1)
            df_final = df_final.dropna(subset=['Fone']).copy() # Filtro de quem não tem telefone

            # Formatação de nomes (na tabela final agora com todas as colunas)
            if 'Cliente' in df_final.columns:
                df_final['Cliente'] = df_final['Cliente'].apply(tratar_primeiro_nome)
            if 'Detento' in df_final.columns:
                df_final['Detento'] = df_final['Detento'].apply(tratar_primeiro_nome)

            # Organização das colunas (Vips primeiro, o resto tudo depois)
            colunas_vips = ['ID_PEDIDO', 'Cliente', 'Detento', 'Fone', 'Código de Rastreio']
            existentes = [c for c in colunas_vips if c in df_final.columns]
            extras = [c for c in df_final.columns if c not in existentes]
            df_envio = df_final[existentes + extras].copy()

            # --- EXIBIÇÃO DA TABELA ---
            st.success(f"✅ {len(df_envio)} pedidos prontos!")
            st.dataframe(df_envio, use_container_width=True)

            # --- SEÇÃO DE DISPARO ---
            st.divider()
            webhook = st.text_input("URL do Webhook (POST):", value="https://jumbocdp.app.n8n.cloud/webhook/b5007963-8d59-4c88-ae17-33dfe20b9d91")
            
            if st.button("Confirmar Envio para WhatsApp"):
                payload = df_envio.to_dict(orient='records')
                try:
                    res = requests.post(webhook, json=payload, timeout=35)
                    if res.status_code in [200, 201]:
                        st.balloons()
                        st.success("Dados enviados com sucesso!")
                    else:
                        st.error(f"Erro {res.status_code}")
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")
        else:
            st.warning("⚠️ Nenhum pedido coincidente encontrado.")
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
