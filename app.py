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

def processar_telefone_jumbo(row):
    """REGRA: Fone Fixo > Celular | Limpa caracteres | Adiciona 55"""
    # Pega os valores das colunas originais
    fixo = str(row.get('Fone Fixo', '')).strip()
    cel = str(row.get('Celular', '')).strip()
    
    # 1. Prioridade Fone Fixo, se vazio busca Celular
    fone_escolhido = fixo if fixo and fixo.lower() not in ["nan", "none", "0", ""] else cel
    
    # 2. Limpeza total (deixa apenas números)
    fone_limpo = re.sub(r'\D', '', fone_escolhido)
    
    # 3. Validação e Adição do 55
    if fone_limpo and len(fone_limpo) >= 8:
        if not fone_limpo.startswith('55'):
            fone_limpo = '55' + fone_limpo
        return fone_limpo
    return None # Retorna None para quem não tem telefone

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
        # VOLTANDO PARA A LEITURA ORIGINAL QUE FUNCIONAVA
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t').fillna("").astype(str)
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t').fillna("").astype(str)

        # Mapeamento padrão (O mesmo que você já usava)
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

        # CRUZAMENTO (INNER JOIN)
        # Aqui mantemos TODAS as colunas de vendas (df_vendas)
        df_final = pd.merge(df_vendas, df_rastreio[['ID_PEDIDO', 'Código de Rastreio']], on='ID_PEDIDO', how='inner')

        if not df_final.empty:
            # --- APLICANDO AS NOVAS CONDIÇÕES ---
            
            # 1. Criar coluna Fone com a nova lógica (Fixo > Celular + 55)
            df_final['Fone'] = df_final.apply(processar_telefone_jumbo, axis=1)

            # 2. Remover leads que ficaram sem telefone (Não inserir no resultado)
            df_final = df_final.dropna(subset=['Fone']).copy()

            if not df_final.empty:
                # 3. Formatação de Nomes
                if 'Cliente' in df_final.columns:
                    df_final['Cliente'] = df_final['Cliente'].apply(tratar_primeiro_nome)
                if 'Detento' in df_final.columns:
                    df_final['Detento'] = df_final['Detento'].apply(tratar_primeiro_nome)

                # 4. Organização: VIPs na frente, mas mantém TUDO
                cols_vips = ['ID_PEDIDO', 'Cliente', 'Detento', 'Fone', 'Código de Rastreio']
                existentes_vips = [c for c in cols_vips if c in df_final.columns]
                resto_das_colunas = [c for c in df_final.columns if c not in existentes_vips]
                
                df_envio = df_final[existentes_vips + resto_das_colunas].copy()

                # --- EXIBIÇÃO ---
                st.success(f"✅ {len(df_envio)} pedidos prontos!")
                st.dataframe(df_envio, use_container_width=True)

                # --- DISPARO ---
                st.divider()
                webhook = st.text_input("URL do Webhook:", value="https://jumbocdp.app.n8n.cloud/webhook/b5007963-8d59-4c88-ae17-33dfe20b9d91")
                
                if st.button("Confirmar Envio para WhatsApp"):
                    payload = df_envio.to_dict(orient='records')
                    res = requests.post(webhook, json=payload, timeout=45)
                    if res.status_code in [200, 201]:
                        st.balloons()
                        st.success(f"Enviado! {len(payload)} leads processados.")
            else:
                st.warning("Nenhum lead com telefone válido encontrado.")
        else:
            st.warning("Nenhum pedido coincidente encontrado.")
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
