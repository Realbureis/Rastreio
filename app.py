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

def extrair_telefone(row):
    """Fallback: Celular > Fone Fixo. Remove quem não tem nenhum."""
    # Respeitando os nomes exatos das suas colunas
    celular = str(row.get('Celular', '')).strip()
    fixo = str(row.get('Fone Fixo', '')).strip()
    
    # Se celular for vazio ou nan, tenta o fixo
    fone_final = celular if celular and celular.lower() not in ["nan", "none", "0", ""] else fixo
    
    # Limpa caracteres especiais
    fone_limpo = re.sub(r'\D', '', fone_final)
    
    # Retorna o número se for válido, senão None para o filtro dropna
    return fone_limpo if fone_limpo and len(fone_limpo) >= 8 else None

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
                c_upper = col.upper().strip()
                if "PEDIDO" in c_upper: mapa[col] = "ID_PEDIDO"
                elif "CLIENTE" in c_upper: mapa[col] = "Cliente"
                elif "DETENTO" in c_upper or "CADASTRA" in c_upper: mapa[col] = "Detento"
                elif "RASTREIO" in c_upper: mapa[col] = "Código de Rastreio"
            return df.rename(columns=mapa)

        df_vendas = auto_mapear(df_vendas)
        df_rastreio = auto_mapear(df_rastreio)

        # Remove duplicatas de colunas
        df_vendas = df_vendas.loc[:, ~df_vendas.columns.duplicated()]
        df_rastreio = df_rastreio.loc[:, ~df_rastreio.columns.duplicated()]

        # Limpeza das chaves
        df_vendas['ID_PEDIDO'] = df_vendas['ID_PEDIDO'].str.strip()
        df_rastreio['ID_PEDIDO'] = df_rastreio['ID_PEDIDO'].str.strip()

        # --- CRUZAMENTO (INNER JOIN) ---
        # Mantém TODAS as colunas originais de vendas
        df_final = pd.merge(df_vendas, df_rastreio[['ID_PEDIDO', 'Código de Rastreio']], on='ID_PEDIDO', how='inner')

        if not df_final.empty:
            # --- TRATAMENTO DE TELEFONE E FILTRO ---
            # Cria a coluna 'Fone' baseada no Celular ou Fone Fixo
            df_final['Fone'] = df_final.apply(extrair_telefone, axis=1)
            
            # REMOVE quem não tem nenhum dos dois (Condição solicitada)
            df_final = df_final.dropna(subset=['Fone']).copy()

            if not df_final.empty:
                # --- FORMATAÇÃO ---
                if 'Cliente' in df_final.columns:
                    df_final['Cliente'] = df_final['Cliente'].apply(tratar_primeiro_nome)
                if 'Detento' in df_final.columns:
                    df_final['Detento'] = df_final['Detento'].apply(tratar_primeiro_nome)

                # --- ORGANIZAÇÃO PARA O PAYLOAD ---
                # Colunas VIPs primeiro, mas mantemos o restante absoluto das colunas
                cols_vips = ['ID_PEDIDO', 'Cliente', 'Detento', 'Fone', 'Código de Rastreio']
                existentes_vips = [c for c in cols_vips if c in df_final.columns]
                resto_das_colunas = [c for c in df_final.columns if c not in existentes_vips]
                
                df_envio = df_final[existentes_vips + resto_das_colunas].copy()

                # --- EXIBIÇÃO DA TABELA ---
                st.success(f"✅ {len(df_envio)} pedidos validados e prontos para envio!")
                
                st.subheader("📋 Auditoria de Dados (Principais + Extras)")
                st.dataframe(df_envio, use_container_width=True)

                # --- SEÇÃO DE DISPARO ---
                st.divider()
                webhook = st.text_input("URL do Webhook (POST):", value="https://jumbocdp.app.n8n.cloud/webhook/b5007963-8d59-4c88-ae17-33dfe20b9d91")
                
                if st.button("Confirmar Envio para WhatsApp"):
                    if webhook.startswith("https://"):
                        payload = df_envio.to_dict(orient='records')
                        try:
                            res = requests.post(webhook, json=payload, timeout=45)
                            if res.status_code in [200, 201]:
                                st.balloons()
                                st.success(f"Dados enviados! {len(payload)} usuários com histórico completo no n8n.")
                            else:
                                st.error(f"Erro {res.status_code}: Mude o Webhook no n8n para POST.")
                        except Exception as e:
                            st.error(f"Erro de conexão: {e}")
                    else:
                        st.warning("Insira uma URL válida.")
            else:
                st.warning("⚠️ Todos os leads coincidentes estavam sem Celular ou Fone Fixo.")
        else:
            st.warning("⚠️ Nenhum pedido coincidente encontrado.")
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
