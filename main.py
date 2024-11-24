from datetime import datetime
from threading import Thread
import time
import schedule
from logger_config import logger
from envio_email import enviar_emails
from atualizar_lista_pendentes import Atualizar_lista_pendetes
from dotenv import load_dotenv
from threading import Thread
from flask import Flask, jsonify, render_template, request
from envio_email import enviar_emails
from logger_config import logger
from flask_cors import CORS
from processo_data import validar_dados
import requests

# Atualiza a lista de pendentes:
schedule.every().hour.do(Atualizar_lista_pendetes)

# Agenda o envio para todos os dias às 16:00
schedule.every().day.at("16:25").do(lambda:enviar_emails(data_inicio= None, data_fim= None, Origem = "Automatico") )


app = Flask(__name__, template_folder='C:\\Users\\pedro\\OneDrive\\Documentos\\GitHub\\envio_email_py\\templates\\', static_folder='C:\\Users\\pedro\\OneDrive\\Documentos\\GitHub\\envio_email_py\\static\\')

CORS(app,resources={r"/*": {"origins": "*"}})

def enviar_emails_background(data_inicial=None, data_final=None, origem = "API", email = None,codigo = None):
    try:
        logger.info(f"Iniciando envio de e-mails com data_inicial={data_inicial} e data_final={data_final} codigo: {codigo} para o email: {email}")
        result = enviar_emails(data_inicial, data_final,origem,email,codigo)
        if result:  
            status, code = result
            logger.info(f"Envio de e-mails concluído com status={status}, code={code}")
    except Exception as e:
        logger.error(f"Erro ao enviar e-mails: {e}")
        status, code = "erro", 500
        
@app.route('/')
def index():
    return render_template('html/index.html')

@app.route('/relatorio', methods=['GET','POST'])
def relatorio():
    if request.method=='GET':
            return render_template('html/relatorio.html')
    elif request.method=='POST':
        data = request.get_json()
        data_inicial = data.get('data_inicial')
        data_final = data.get('data_final')
        email = data.get('email')
        time.sleep(1)

        if not data_inicial or not data_final:
            response = jsonify({"Campos de 'data' obrigatorios!"})
            response.status_code= 500       
            return response
        
        if not email:
            response = jsonify({"Campo 'email' obrigatorio!"})
            response.status_code= 500
            return response

        dados = validar_dados(data_inicial,data_final,codigo=None)

        if not dados:
            response = jsonify({"error":"Nenhum dado encontrato para o dia selecionado!"})
            response.status_code= 500
            return response
        
        if data_final and data_inicial and email:
            response = jsonify({"message": "Dentro de alguns minutos o relatorio estará no seu email!"})
            response.status_code = 200  
            # Processamento em segundo plano
            thread = Thread(target=enviar_emails_background, args=(data_inicial, data_final, "API", email))
            thread.start()
            return response
        
@app.route('/relatorio_especifico', methods=['GET','POST'], endpoint = '/relatorio_especifico')
def relatorio_especifico():
    if request.method=='GET':
            return render_template('html/relatorio_especifico.html')
    elif request.method=='POST':
        data = request.get_json()
        data_inicial = data.get('data_inicial')
        data_final = data.get('data_final')
        email = data.get('email')
        codigo = data.get('codigo')
        time.sleep(1)

        if not data_inicial or not data_final:
            response = jsonify({"Campos de 'data' obrigatorios!"})
            response.status_code= 500       
            return response
        
        if not email:
            response = jsonify({"Campo 'email' obrigatorio!"})
            response.status_code= 500
            return response

        dados = validar_dados(data_inicial,data_final,codigo)

        if not dados:
            response = jsonify({"error":"Nenhum dado encontrato para o dia selecionado!"})
            response.status_code= 500
            return response
        
        if data_final and data_inicial and email and codigo:
            response = jsonify({"message": "Dentro de alguns minutos o relatorio estará no seu email!"})
            response.status_code = 200  
            # Processamento em segundo plano
            thread = Thread(target=enviar_emails_background, args=(data_inicial, data_final, "API", email, codigo))
            thread.start()
            return response
    
@app.route('/proxy/relatorio', methods = ['POST'])
def proxy_relatorio():
    data = request.get_json()

    URL= 'http://26.154.23.230:8080/relatorio'

    try:
        response = requests.post(URL,json = data)
        return jsonify(response.json()), response.status_code
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao encaminhar a requisição para o servidor real: {e}")
        return jsonify({"error": "Erro ao comunicar com o servidor real"}), 500

@app.route('/proxy/relatorio_especifico', methods=['POST'])
def proxy_relatorio_especifico():
    data = request.get_json()

    URL= 'http://26.154.23.230:8080/relatorio_especifico'
    
    try:
        response = requests.post(URL,json = data)
        return jsonify(response.json()), response.status_code
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao encaminhar a requisição para o servidor real: {e}")
        return jsonify({"error": "Erro ao comunicar com o servidor real"}), 500


def run_schedule():

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    Atualizar_lista_pendetes()

    Thread(target=run_schedule).start()

app.run(host='0.0.0.0', port=8080, threaded=True)

