from datetime import datetime
from threading import Thread
import time
import schedule
from logger_config import logger
from envio_email import enviar_emails
from atualizar_lista_pendentes import Atualizar_lista_pendetes
from dotenv import load_dotenv
from api_relatorio import api_enviar_emails


# Atualiza a lista de pendentes:
schedule.every().hour.do(Atualizar_lista_pendetes)

# Agenda o envio para todos os dias às 16:00
schedule.every().day.at("08:27").do(enviar_emails)



def run_schedule():

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    Atualizar_lista_pendetes()

    api_enviar_emails()
    # Inicia a API Flask em uma thread separada
    Thread(target=run_schedule).start()
