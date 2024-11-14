from threading import Thread
from flask import Flask, jsonify, request
from envio_email import enviar_emails
from logger_config import logger

app = Flask(__name__)

def enviar_emails_background(data_inicial=None, data_final=None):
    try:
        logger.info(f"Iniciando envio de e-mails com data_inicial={data_inicial} e data_final={data_final}")
        result = enviar_emails(data_inicial, data_final)
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

    # Retorna uma resposta imediata dizendo que a requisição foi recebida
    response = jsonify({"message": "Envio em andamento, por favor aguarde."})
    response.status_code = 200  # Código de aceitação, requisição recebida com sucesso.

    # Processamento em segundo plano
    thread = Thread(target=enviar_emails_background, args=(data_inicial, data_final))
    thread.start()

    return response

app.run(host='localhost', port=8080, threaded=True)
