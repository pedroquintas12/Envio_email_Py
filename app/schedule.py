import schedule
from app.utils.envio_email import enviar_emails
import time

_scheduler_started = False  # Variável para evitar múltiplas inicializações

schedule.every().day.at("11:36").do(lambda: enviar_emails(data_inicio=None, data_fim=None, Origem="Automatico",status = "P"))


def run_scheduler():
    global _scheduler_started
    if _scheduler_started:  # Verifica se o agendador já está rodando
        return
    _scheduler_started = True  

    while True:
        schedule.run_pending()
        time.sleep(1)