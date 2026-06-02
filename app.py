import streamlit as st
import pandas as pd
import io
import requests
import re
import time

# 1. Configuração da Página
st.set_page_config(page_title="Jumbo CDP - Rastreio", layout="wide", page_icon="🚚")

def tratar_primeiro_nome(texto):
    """Extrai apenas o primeiro nome em Title Case"""
    txt = str(texto).strip()
    if not txt or txt.lower() in ["nan", "none", "0", "-"]:
        return "N/A"
    return txt.split()[0].title()

def formatar_data_bq(texto):
    """Converte DD/MM/YYYY para YYYY-MM-DD para o BigQuery entender como DATE"""
    txt = str(texto).strip()
    # Procura o padrão de data brasileira 00/00/0000
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
                # --- TRATAMENTO PARA BIGQUERY (DATA E MOEDA) ---
                for col in df_final.columns:
                    c_up = str(col).upper()
                    # Se for coluna de data, converte para YYYY-MM-DD
                    if "DATA" in c_up:
                        df_final[col] = df_final[col].apply(formatar_data_bq)
                    # Se for coluna financeira, limpa para número puro
                    if any(x in c_up for x in ["VALOR", "TOTAL", "PRECO", "FRETE"]):
                        df_final[col] = df_final[col].apply(limpar_valor_monetario)

                if 'Cliente' in df_final.columns:
                    df_final['Cliente'] = df_final['Cliente'].apply(tratar_primeiro_nome)
                if 'Detento' in df_final.columns:
                    df_final['Detento'] = df_final['Detento'].apply(tratar_primeiro_nome)

                df_envio = df_final.copy()
                st.success(f"✅ {len(df_envio)} pedidos processados e traduzidos para o BigQuery!")
                st.dataframe(df_envio, use_container_width=True)

                st.divider()
                webhook = st.text_input("URL do Webhook:", value="https://n8n.corcaqui.com.br/webhook-test/b5007963-8d59-4c88-ae17-33dfe20b9d91")
                
                if st.button("Confirmar Envio"):
                    payloads = df_envio.to_dict(orient='records')
                    total_pedidos = len(payloads)
                    
                    # Elementos visuais para feedback do usuário
                    progresso_bar = st.progress(0)
                    status_texto = st.empty()
                    
                    sucessos = 0
                    erros = 0
                    
                    for index, item in enumerate(payloads):
                        # Atualiza a interface gráfica
                        status_texto.text(f"Enviando pedido {index + 1} de {total_pedidos} (Pedido N.: {item.get('N. Pedido', '?')})...")
                        progresso_bar.progress((index + 1) / total_pedidos)
                        
                        try:
                            # Envia registro por registro com um timeout seguro de 30s por linha
                            res = requests.post(webhook, json=item, timeout=30)
                            if res.status_code in [200, 201]:
                                sucessos += 1
                            else:
                                erros += 1
                        except Exception:
                            erros += 1
                        
                        # Pequena pausa opcional para não metralhar o servidor (0.1 segundos)
                        time.sleep(0.1)
                    
                    # Finalização do processo
                    status_texto.empty()
                    if erros == 0:
                        st.balloons()
                        st.success(f"🚀 Todos os {sucessos} pedidos foram enviados com sucesso para o n8n!")
                    elif sucessos > 0:
                        st.warning(f"Processo concluído com alertas: {sucessos} enviados com sucesso, mas {erros} falharam. Verifique o n8n.")
                    else:
                        st.error("Falha crítica: Nenhum pedido pôde ser entregue ao n8n. O servidor de webhook está offline?")
                        
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
