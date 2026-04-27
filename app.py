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

def limpar_e_extrair_fone(row):
    """Prioridade: Fone Fixo > Celular. Adiciona 55 e limpa caracteres."""
    # Busca flexível para evitar erro de nomes de colunas
    fixo = ""
    cel = ""
    
    for col in row.index:
        c_up = str(col).upper().strip()
        if c_up == "FONE FIXO": fixo = str(row[col])
        if c_up == "CELULAR": cel = str(row[col])
    
    # Prioridade Fone Fixo
    fone_bruto = fixo.strip() if fixo.strip() and fixo.lower() not in ["nan", "none", "0", ""] else cel.strip()
    
    # Limpeza total
    fone_limpo = re.sub(r'\D', '', fone_bruto)
    
    if fone_limpo and len(fone_limpo) >= 8:
        if not fone_limpo.startswith('55'):
            fone_limpo = '55' + fone_limpo
        return fone_limpo
    return None

st.title("🚚 Disparador de Rastreios | Jumbo CDP")
st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1. Dados de Vendas")
    input_vendas = st.text_area("Cole os dados de Vendas aqui:", height=200)
with col2:
    st.subheader("2. Dados de Rastreio")
    input_rastreio = st.text_area("Cole os dados de Rastreio aqui:", height=200)

if input_vendas and input_rastreio:
    try:
        # Lendo os dados com separador de Tabulação (Padrão do Excel)
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t').fillna("").astype(str)
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t').fillna("").astype(str)

        if df_vendas.empty or df_rastreio.empty:
            st.error("Uma das tabelas coladas está vazia.")
            st.stop()

        # Mapeamento de Colunas Críticas
        def auto_mapear(df):
            mapa = {}
            for col in df.columns:
                c_upper = str(col).upper().strip()
                if "PEDIDO" in c_upper: mapa[col] = "ID_PEDIDO"
                elif "CLIENTE" in c_upper: mapa[col] = "Cliente"
                elif "DETENTO" in c_upper or "CADASTRA" in c_upper: mapa[col] = "Detento"
                elif "RASTREIO" in c_upper: mapa[col] = "Código de Rastreio"
            return df.rename(columns=mapa)

        df_vendas = auto_mapear(df_vendas)
        df_rastreio = auto_mapear(df_rastreio)

        # IDs limpos para o Join
        df_vendas['ID_PEDIDO'] = df_vendas['ID_PEDIDO'].apply(lambda x: str(x).strip())
        df_rastreio['ID_PEDIDO'] = df_rastreio['ID_PEDIDO'].apply(lambda x: str(x).strip())

        # Cruzamento
        df_final = pd.merge(df_vendas, df_rastreio[['ID_PEDIDO', 'Código de Rastreio']], on='ID_PEDIDO', how='inner')

        if not df_final.empty:
            # 1. Aplicação da Prioridade e Inserção do 55
            df_final['Fone'] = df_final.apply(limpar_e_extrair_fone, axis=1)

            # 2. Filtro Crítico: Remove quem ficou sem telefone
            df_final = df_final.dropna(subset=['Fone']).copy()

            if not df_final.empty:
                # 3. Tratamento de Nomes
                if 'Cliente' in df_final.columns:
                    df_final['Cliente'] = df_final['Cliente'].apply(tratar_primeiro_nome)
                if 'Detento' in df_final.columns:
                    df_final['Detento'] = df_final['Detento'].apply(tratar_primeiro_nome)

                # 4. Organização do Preview e Envio
                vips = ['ID_PEDIDO', 'Cliente', 'Detento', 'Fone', 'Código de Rastreio']
                existentes_vips = [c for c in vips if c in df_final.columns]
                outras_cols = [c for c in df_final.columns if c not in existentes_vips]
                
                df_envio = df_final[existentes_vips + outras_cols].copy()

                st.success(f"✅ {len(df_envio)} pedidos processados com sucesso!")
                st.dataframe(df_envio, use_container_width=True)

                st.divider()
                webhook = st.text_input("URL do Webhook:", value="https://jumbocdp.app.n8n.cloud/webhook/b5007963-8d59-4c88-ae17-33dfe20b9d91")
                
                if st.button("Confirmar Envio Total"):
                    payload = df_envio.to_dict(orient='records')
                    res = requests.post(webhook, json=payload, timeout=45)
                    if res.status_code in [200, 201]:
                        st.balloons()
                        st.success(f"Enviado! {len(payload)} leads processados.")
            else:
                st.warning("⚠️ Nenhum lead com Fone Fixo ou Celular encontrado no cruzamento.")
        else:
            st.warning("⚠️ Nenhum pedido coincidente encontrado entre as duas colagens.")
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
