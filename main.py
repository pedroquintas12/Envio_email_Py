from datetime import datetime
from threading import Thread
import time
import schedule
from logger_config import logger
from envio_email import enviar_emails
from atualizar_lista_pendentes import Atualizar_lista_pendetes
from dotenv import load_dotenv
from threading import Thread
from flask import Flask, jsonify, request
from envio_email import enviar_emails
from logger_config import logger

# Atualiza a lista de pendentes:
schedule.every().hour.do(Atualizar_lista_pendetes)

# Agenda o envio para todos os dias às 16:00
schedule.every().day.at("16:00").do(lambda:enviar_emails(data_inicio= None, data_fim= None, Origem = "Automatico") )


app = Flask(__name__)

def enviar_emails_background(data_inicial=None, data_final=None, origem = "API"):
    try:
        logger.info(f"Iniciando envio de e-mails com data_inicial={data_inicial} e data_final={data_final}")
        result = enviar_emails(data_inicial, data_final,origem)
        if result:
            status, code = result
            logger.info(f"Envio de e-mails concluído com status={status}, code={code}")
    except Exception as e:
        logger.error(f"Erro ao enviar e-mails: {e}")
        status, code = "erro", 500

@app.route('/relatorio', methods=['POST'])
def api_enviar_emails():
    data = request.get_json()
    data_inicial = data.get('data_inicial')
    data_final = data.get('data_final')

    time.sleep(1)
    # Retorna uma resposta imediata dizendo que a requisição foi recebida
    response = jsonify({"message": "Envio em andamento, por favor aguarde."})
    response.status_code = 200  # Código de aceitação, requisição recebida com sucesso.

    # Processamento em segundo plano
    thread = Thread(target=enviar_emails_background, args=(data_inicial, data_final, "API"))
    thread.start()

    return response

def run_schedule():

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    Atualizar_lista_pendetes()

    Thread(target=run_schedule).start()

app.run(host='localhost', port=8080, threaded=True)

