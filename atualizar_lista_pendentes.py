from datetime import datetime
from processo_data import pendentes_envio
from logger_config import logger


def Atualizar_lista_pendetes():
    try:
        clientes_data = pendentes_envio()
        total_escritorios = len(clientes_data)  
        total_processos_por_escritorio = {cliente: len(processos) for cliente, processos in clientes_data.items()}
        logger.info(f"\nAguardando o horário de envio... (Atualizado: {datetime.now().strftime('%d-%m-%y %H:%M')})")
        logger.info(f"Total de escritórios a serem enviados: {total_escritorios}")
        for cliente, total_processos in total_processos_por_escritorio.items():
            cod_escritorio = clientes_data[cliente][0]['cod_escritorio'] if clientes_data[cliente] else "N/A"
            logger.info(f"Escritório: {cliente}({cod_escritorio}) - Total de processos: {total_processos}  ")
    except Exception as err:
        logger.error(f"erro ao atualizar lista de pendentes: {err}")
