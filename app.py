import streamlit as st
import pandas as pd
import io
import requests
import re

# 1. Configuração da Página
st.set_page_config(page_title="Jumbo CDP - Rastreio", layout="wide", page_icon="🚚")

def tratar_primeiro_nome(texto):
    """Extrai apenas o primeiro nome em Title Case de forma segura"""
    txt = str(texto).strip()
    if not txt or txt.lower() in ["nan", "none", "0", "-"]:
        return "N/A"
    return txt.split()[0].title()

def limpar_e_extrair_fone(row):
    """Lógica de Prioridade: Fone Fixo > Celular. Limpa ( ) - e espaços."""
    # Coleta os valores garantindo que sejam strings
    fixo = str(row.get('Fone Fixo', '')).strip()
    cel = str(row.get('Celular', '')).strip()
    
    # Prioridade solicitada: Fone Fixo primeiro
    fone_bruto = fixo if fixo and fixo.lower() not in ["nan", "none", "0", ""] else cel
    
    # Limpa tudo que não for número (Remove parênteses, traços e espaços)
    fone_limpo = re.sub(r'\D', '', fone_bruto)
    
    # Retorna o número se tiver tamanho mínimo, senão None para exclusão
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
        # Lendo os dados como string para evitar erros de tipo e perda de zeros à esquerda
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t', dtype=str).fillna("")
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t', dtype=str).fillna("")

        # --- PADRONIZAÇÃO DE COLUNAS ---
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

        # Cruzamento pelo ID_PEDIDO
        df_vendas['ID_PEDIDO'] = df_vendas['ID_PEDIDO'].astype(str).str.strip()
        df_rastreio['ID_PEDIDO'] = df_rastreio['ID_PEDIDO'].astype(str).str.strip()
        
        # Merge mantendo todas as colunas de vendas
        df_final = pd.merge(df_vendas, df_rastreio[['ID_PEDIDO', 'Código de Rastreio']], on='ID_PEDIDO', how='inner')

        if not df_final.empty:
            # 1. Aplicação da Prioridade de Telefone (Fixo > Celular) e Limpeza de (11) 91111-1111
            df_final['Fone'] = df_final.apply(limpar_e_extrair_fone, axis=1)

            # 2. CONDIÇÃO: Não inserir lead se não tiver nenhum telefone
            df_final = df_final.dropna(subset=['Fone']).copy()

            if not df_final.empty:
                # 3. Tratamento de Nomes
                if 'Cliente' in df_final.columns:
                    df_final['Cliente'] = df_final['Cliente'].apply(tratar_primeiro_nome)
                if 'Detento' in df_final.columns:
                    df_final['Detento'] = df_final['Detento'].apply(tratar_primeiro_nome)

                # 4. Organização (VIPs primeiro, mas com TODAS as colunas para o BigQuery)
                vips = ['ID_PEDIDO', 'Cliente', 'Detento', 'Fone', 'Código de Rastreio']
                cols_vips = [c for c in vips if c in df_final.columns]
                outras_cols = [c for c in df_final.columns if c not in cols_vips]
                
                df_envio = df_final[cols_vips + outras_cols].copy()

                st.success(f"✅ {len(df_envio)} pedidos processados com prioridade no Fone Fixo!")
                
                # Preview com todas as colunas preenchidas
                st.dataframe(df_envio, use_container_width=True)

                # --- SEÇÃO DE DISPARO ---
                st.divider()
                webhook = st.text_input("URL do Webhook (POST):", value="https://jumbocdp.app.n8n.cloud/webhook/b5007963-8d59-4c88-ae17-33dfe20b9d91")
                
                if st.button("Confirmar Envio para WhatsApp"):
                    payload = df_envio.to_dict(orient='records')
                    res = requests.post(webhook, json=payload, timeout=45)
                    if res.status_code in [200, 201]:
                        st.balloons()
                        st.success(f"Sucesso! {len(payload)} leads enviados.")
                    else:
                        st.error(f"Erro {res.status_code}")
            else:
                st.warning("⚠️ Nenhum lead com telefone válido encontrado após o cruzamento.")
        else:
            st.warning("⚠️ Nenhum pedido coincidente encontrado.")
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
