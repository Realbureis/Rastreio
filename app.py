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
        # Lendo os dados como String
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t', dtype=str).fillna("")
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t', dtype=str).fillna("")

        # --- PADRONIZAÇÃO AUTOMÁTICA DE COLUNAS ---
        def auto_mapear(df):
            mapa = {}
            for col in df.columns:
                c_upper = str(col).upper().strip()
                
                # TRAVA: Não mapeia se for Código Cliente ou colunas de Quantidade
                if "CODIGO CLIENTE" in c_upper or "QUANT" in c_upper:
                    continue
                
                # Nome final solicitado: N. Pedido
                if "PEDIDO" in c_upper: mapa[col] = "N. Pedido"
                elif "CLIENTE" in c_upper: mapa[col] = "Cliente"
                elif "DETENTO" in c_upper or "CADASTRA" in c_upper: mapa[col] = "Detento"
                elif "RASTREIO" in c_upper: mapa[col] = "Código de Rastreio"
            return df.rename(columns=mapa)

        df_vendas = auto_mapear(df_vendas)
        df_rastreio = auto_mapear(df_rastreio)

        df_vendas = df_vendas.loc[:, ~df_vendas.columns.duplicated()]
        df_rastreio = df_rastreio.loc[:, ~df_rastreio.columns.duplicated()]

        # Limpeza das chaves usando o novo nome N. Pedido
        df_vendas['N. Pedido'] = df_vendas['N. Pedido'].astype(str).str.strip()
        df_rastreio['N. Pedido'] = df_rastreio['N. Pedido'].astype(str).str.strip()

        # CRUZAMENTO (INNER JOIN)
        df_final = pd.merge(df_vendas, df_rastreio[['N. Pedido', 'Código de Rastreio']], on='N. Pedido', how='inner')

        if not df_final.empty:
            # Atualização da coluna Fone Fixo
            df_final['Fone Fixo'] = df_final.apply(processar_fone_jumbo, axis=1)
            
            # FILTRO: Remove lead sem telefone
            df_final = df_final.dropna(subset=['Fone Fixo']).copy()

            if not df_final.empty:
                # Formatação de nomes
                if 'Cliente' in df_final.columns:
                    df_final['Cliente'] = df_final['Cliente'].apply(tratar_primeiro_nome)
                if 'Detento' in df_final.columns:
                    df_final['Detento'] = df_final['Detento'].apply(tratar_primeiro_nome)

                # Mantém TODAS as colunas originais (incluindo Codigo Cliente e N. Pedido)
                df_envio = df_final.copy()

                # --- EXIBIÇÃO DA TABELA ---
                st.success(f"✅ {len(df_envio)} pedidos prontos!")
                st.dataframe(df_envio, use_container_width=True)

                # --- SEÇÃO DE DISPARO ---
                st.divider()
                webhook = st.text_input("URL do Webhook (POST):", value="https://jumbocdp.app.n8n.cloud/webhook/b5007963-8d59-4c88-ae17-33dfe20b9d91")
                
                if st.button("Confirmar Envio para WhatsApp"):
                    payload = df_envio.to_dict(orient='records')
                    try:
                        res = requests.post(webhook, json=payload, timeout=45)
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
