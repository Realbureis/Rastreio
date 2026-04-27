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

        # Criamos cópias para mapeamento sem alterar os nomes originais das colunas que você precisa
        df_vendas_map = df_vendas.copy()
        
        # Mapeamento apenas para identificar as chaves de cruzamento e nomes
        mapa = {}
        for col in df_vendas.columns:
            c_upper = str(col).upper().strip()
            if "PEDIDO" in c_upper and "QUANT" not in c_upper: mapa[col] = "ID_PEDIDO"
            elif "CLIENTE" in c_upper and "QUANT" not in c_upper: mapa[col] = "Cliente_Formatado"
            elif "DETENTO" in c_upper: mapa[col] = "Detento_Formatado"

        df_vendas_map = df_vendas_map.rename(columns=mapa)
        
        # Mapeamento do Rastreio
        mapa_rastreio = {}
        for col in df_rastreio.columns:
            if "PEDIDO" in str(col).upper(): mapa_rastreio[col] = "ID_PEDIDO"
            if "RASTREIO" in str(col).upper(): mapa_rastreio[col] = "Código de Rastreio"
        
        df_rastreio_map = df_rastreio.rename(columns=mapa_rastreio)

        # IDs limpos para o Join
        df_vendas_map['ID_PEDIDO'] = df_vendas_map['ID_PEDIDO'].astype(str).str.strip()
        df_rastreio_map['ID_PEDIDO'] = df_rastreio_map['ID_PEDIDO'].astype(str).str.strip()

        # CRUZAMENTO (INNER JOIN)
        # Unimos as tabelas mantendo ABSOLUTAMENTE TODAS as colunas originais de vendas
        df_final = pd.merge(df_vendas_map, df_rastreio_map[['ID_PEDIDO', 'Código de Rastreio']], on='ID_PEDIDO', how='inner')

        if not df_final.empty:
            # --- ATUALIZAÇÃO DA COLUNA FONE FIXO ---
            df_final['Fone Fixo'] = df_final.apply(processar_fone_jumbo, axis=1)
            
            # FILTRO: Remove o lead se o 'Fone Fixo' for inválido
            df_final = df_final.dropna(subset=['Fone Fixo']).copy()

            if not df_final.empty:
                # Formatação de nomes em colunas auxiliares (opcional, mantendo as originais)
                if 'Cliente_Formatado' in df_final.columns:
                    df_final['Cliente_Formatado'] = df_final['Cliente_Formatado'].apply(tratar_primeiro_nome)
                if 'Detento_Formatado' in df_final.columns:
                    df_final['Detento_Formatado'] = df_final['Detento_Formatado'].apply(tratar_primeiro_nome)

                # Removemos apenas as colunas auxiliares de mapeamento para não duplicar dados
                df_envio = df_final.copy()

                # --- EXIBIÇÃO DA TABELA ---
                st.success(f"✅ {len(df_envio)} pedidos processados com sucesso!")
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
                            st.success(f"Enviado! Todas as colunas (incluindo Quantidades) foram processadas.")
                        else:
                            st.error(f"Erro {res.status_code}")
                    except Exception as e:
                        st.error(f"Erro de conexão: {e}")
        else:
            st.warning("⚠️ Nenhum pedido coincidente encontrado.")
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
