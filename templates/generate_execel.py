from collections import defaultdict
import io
from openpyxl import Workbook

def gerar_excel_base64(clientes_data):
    wb = Workbook()
    ws = wb.active
    ws.title = "Processos"
    ws.append(["UF", "Diário","Vara","Nome Pesquisado","Número do Processo"])
    agrupado = defaultdict(lambda: defaultdict(list))

    for proc in clientes_data:
        uf = proc['uf']
        diario = proc['sigla_diario']
        agrupado[uf][diario].append(proc)
        
    for uf, diarios in agrupado.items():
        for diario, processos in diarios.items():
            for proc in processos:
                ws.append([uf, diario,proc["vara"],proc["nome_pesquisado"], proc["numero_processo"]])

    # Salva em memória
    excel_buffer = io.BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)

    # Converte para Base64
    return excel_buffer.read()
