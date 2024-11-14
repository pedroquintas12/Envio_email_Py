from datetime import datetime
from processo_data import fetch_processes_and_clients
from logger_config import logger


def Atualizar_lista_pendetes():
    try:
        clientes_data = fetch_processes_and_clients(data_inicio=None, data_fim=None)
        total_escritorios = len(clientes_data)  
        total_processos_por_escritorio = {cliente: len(processos) for cliente, processos in clientes_data.items()}
        logger.info(f"\nAguardando o horário de envio... (Atualizado: {datetime.now().strftime('%d-%m-%y %H:%M')})")
        logger.info(f"Total de escritórios a serem enviados: {total_escritorios}")
        for cliente, total_processos in total_processos_por_escritorio.items():
            logger.info(f"Escritório: {cliente} - Total de processos: {total_processos}  ")
    except Exception as err:
        logger.error(f"erro ao atualizar lista de pendentes: {err}")
