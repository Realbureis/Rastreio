import streamlit as st
import pandas as pd
import io
import re
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials

# 1. Configuração da Página
st.set_page_config(page_title="Jumbo CDP - Rastreio", layout="wide", page_icon="🚚")

# --- CONFIGURAÇÕES FIXAS DO GOOGLE SHEETS ---
ID_PLANILHA = "1Sz7AcX7-sjejb4EfvJ9bIGsUovHaQovnAh0NNDMfnP8"
NOME_ABA = "Página 1"
CAMINHO_JSON_CREDS = "credentials.json"  # O arquivo JSON deve estar na mesma pasta do script

def tratar_primeiro_nome(texto):
    """Extrai apenas o primeiro nome em Title Case"""
    txt = str(texto).strip()
    if not txt or txt.lower() in ["nan", "none", "0", "-"]:
        return "N/A"
    return txt.split()[0].title()

def formatar_data_bq(texto):
    """Converte DD/MM/YYYY para YYYY-MM-DD para o BigQuery entender como DATE"""
    txt = str(texto).strip()
    match = re.search(r'(\d{2})/(\d{2})/(\d{4})', txt)
    if match:
        dia, mes, ano = match.groups()
        return f"{ano}-{mes}-{dia}"
    return txt

def limpar_valor_monetario(valor):
    """Transforma 'R$ 1.250,50' em '1250.50' para o BigQuery entender como número"""
    v = str(valor).replace('R$', '').strip()
    if not v or v.lower() in ["nan", "none"]:
        return "0.00"
    v = v.replace('.', '').replace(',', '.')
    v = re.sub(r'[^0-9.]', '', v)
    return v

def processar_fone_jumbo(row):
    """Fallback Fixo > Celular | Limpa | Adiciona 55"""
    fixo = str(row.get('Fone Fixo', '')).strip()
    cel = str(row.get('Celular', '')).strip()
    bruto = fixo if fixo and fixo.lower() not in ["nan", "none", "0", ""] else cel
    limpo = re.sub(r'\D', '', bruto)
    if limpo and len(limpo) >= 8:
        return '55' + limpo if not limpo.startswith('55') else limpo
    return None

def enviar_para_sheets(df, spreadsheet_id, sheet_name, creds_path):
    """Autentica na API do Google, limpa a aba atual e escreve os novos dados (sobrescreve)"""
    escopos = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    # Carrega as credenciais da Service Account
    credenciais = Credentials.from_service_account_file(creds_path, scopes=escopos)
    cliente = gspread.authorize(credenciais)
    
    # Abre a planilha pelo ID fornecido
    planilha = cliente.open_by_key(spreadsheet_id)
    
    try:
        aba = planilha.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        # Fallback de segurança caso a aba não seja encontrada
        aba = planilha.add_worksheet(title=sheet_name, rows="100", cols="20")
    
    # Limpa completamente a aba antes do novo envio (apaga dados e formatações anteriores)
    aba.clear()
    
    # Envia o DataFrame começando sempre da linha 1, incluindo o cabeçalho
    set_with_dataframe(
        aba, 
        df, 
        row=1, 
        include_index=False, 
        include_column_header=True
    )

st.title("🚚 Disparador de Rastreios | Jumbo CDP → Google Sheets")
st.markdown("---")

# Barra lateral informativa sobre o status da conexão com os teus dados
st.sidebar.header("⚙️ Status da Conexão")
st.sidebar.text_input("ID da Planilha Ativo:", value=ID_PLANILHA, disabled=True)
st.sidebar.text_input("Aba de Destino:", value=NOME_ABA, disabled=True)
st.sidebar.info(f"🔑 Conta de Serviço vinculada:\nrastreio-beta@rastreio-banco.iam.gserviceaccount.com")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1. Dados de Vendas")
    input_vendas = st.text_area("Cole os dados de Vendas aqui:", height=200)
with col2:
    st.subheader("2. Dados de Rastreio")
    input_rastreio = st.text_area("Cole os dados de Rastreio aqui:", height=200)

if input_vendas and input_rastreio:
    try:
        df_vendas = pd.read_csv(io.StringIO(input_vendas), sep='\t', dtype=str).fillna("")
        df_rastreio = pd.read_csv(io.StringIO(input_rastreio), sep='\t', dtype=str).fillna("")

        def auto_mapear(df):
            mapa = {}
            for col in df.columns:
                c_upper = str(col).upper().strip()
                if "CODIGO CLIENTE" in c_upper or "QUANT" in c_upper: continue
                if "PEDIDO" in c_upper: mapa[col] = "N. Pedido"
                elif "CLIENTE" in c_upper: mapa[col] = "Cliente"
                elif "DETENTO" in c_upper or "CADASTRA" in c_upper: mapa[col] = "Detento"
                elif "RASTREIO" in c_upper: mapa[col] = "Código de Rastreio"
            return df.rename(columns=mapa)

        df_vendas = auto_mapear(df_vendas)
        df_rastreio = auto_mapear(df_rastreio)

        df_vendas = df_vendas.loc[:, ~df_vendas.columns.duplicated()]
        df_rastreio = df_rastreio.loc[:, ~df_rastreio.columns.duplicated()]

        df_vendas['N. Pedido'] = df_vendas['N. Pedido'].apply(lambda x: str(x).strip())
        df_rastreio['N. Pedido'] = df_rastreio['N. Pedido'].apply(lambda x: str(x).strip())

        df_final = pd.merge(df_vendas, df_rastreio[['N. Pedido', 'Código de Rastreio']], on='N. Pedido', how='inner')

        if not df_final.empty:
            df_final['Fone Fixo'] = df_final.apply(processar_fone_jumbo, axis=1)
            df_final = df_final.dropna(subset=['Fone Fixo']).copy()

            if not df_final.empty:
                # --- TRATAMENTO DATA E MOEDA (Padrão BigQuery) ---
                for col in df_final.columns:
                    c_up = str(col).upper()
                    if "DATA" in c_up:
                        df_final[col] = df_final[col].apply(formatar_data_bq)
                    if any(x in c_up for x in ["VALOR", "TOTAL", "PRECO", "FRETE"]):
                        df_final[col] = df_final[col].apply(limpar_valor_monetario)

                if 'Cliente' in df_final.columns:
                    df_final['Cliente'] = df_final['Cliente'].apply(tratar_primeiro_nome)
                if 'Detento' in df_final.columns:
                    df_final['Detento'] = df_final['Detento'].apply(tratar_primeiro_nome)

                df_envio = df_final.copy()
                st.success(f"✅ {len(df_envio)} pedidos processados com sucesso!")
                st.dataframe(df_envio, use_container_width=True)

                st.divider()
                
                # Botão que executa a limpeza e sobrescreve os dados
                if st.button("🚀 Confirmar Envio (Sobrescrever Planilha)"):
                    with st.spinner("Limpando histórico antigo e enviando novos dados..."):
                        enviar_para_sheets(df_envio, ID_PLANILHA, NOME_ABA, CAMINHO_JSON_CREDS)
                    st.balloons()
                    st.success(f"Planilha atualizada! A aba '{NOME_ABA}' foi limpa e reescrita com os novos dados.")
                        
    except Exception as e:
        st.error(f"Erro crítico no processamento ou envio: {e}")
