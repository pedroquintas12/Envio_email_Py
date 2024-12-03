from datetime import datetime
from threading import Thread
import time
import schedule
from logger_config import logger
from envio_email import enviar_emails
from processo_data import historio_env
from processo_data import pendentes_envio
from processo_data import total_geral
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from processo_data import validar_dados
import requests
import sys, os

# Captura o ambiente de execução e configura o diretório base
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(__file__)

load_dotenv(os.path.join(base_dir, 'config.env'))

TEMPLATE_FOLDER = os.getenv("TEMPLATE_FOLDER")
STATIC_FOLDER = os.getenv("STATIC_FOLDER")
URL= os.getenv("URL")

app = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_FOLDER)
CORS(app, resources={r"/*": {"origins": "*"}})

# Agenda o envio de e-mails todos os dias às 16:00
schedule.every().day.at("10:30").do(lambda: enviar_emails(data_inicio=None, data_fim=None, Origem="Automatico",status = None))



# Função para enviar e-mails em background
def enviar_emails_background(data_inicial=None, data_final=None, origem="API", email=None, codigo=None,status = None):
    try:
        logger.info(f"Iniciando envio de e-mails com data_inicial={data_inicial} e data_final={data_final} código: {codigo} para o email: {email}")
        result = enviar_emails(data_inicial, data_final, origem, email, codigo,status)
        if result:
            status, code = result
            logger.info(f"Envio de e-mails concluído com status={status}, código={code}")
    except Exception as e:
        logger.error(f"Erro ao enviar e-mails: {e}")
        status, code = "erro", 500

@app.route('/')
def index():
    return render_template('html/index.html')

@app.route('/api/dados')
def api_dados():
    

    # Obter os dados
    historico = historio_env()
    pendentes = pendentes_envio()
    total = total_geral()

    # Retornar os dados como JSON
    return jsonify({
        'historico': historico,
        'pendentes': pendentes,
        'total_enviados': total
    })
# Rota para gerar e enviar relatório
@app.route('/relatorio', methods=['GET', 'POST'])
def relatorio():
    if request.method == 'GET':
        return render_template('html/relatorio.html')
    elif request.method == 'POST':
        data = request.get_json()
        data_inicial = data.get('data_inicial')
        data_final = data.get('data_final')
        email = data.get('email')
        time.sleep(1)

        # Validação dos dados de entrada
        if not data_inicial or not data_final:
            response = jsonify({"Campos de 'data' obrigatorios!"})
            response.status_code = 500
            return response
        
        if not email:
            response = jsonify({"Campo 'email' obrigatorio!"})
            response.status_code = 500
            return response

        dados = validar_dados(data_inicial, data_final, None, None)
        total_processos = len(dados)
        if not dados:
            response = jsonify({"error": "Nenhum dado encontrado para o dia selecionado!"})
            response.status_code = 500
            return response

        if data_final and data_inicial and email:
            response = jsonify({
                "message": "Dentro de alguns minutos o relatório estará no seu e-mail!",
                "total_processos": total_processos  # Adiciona o total de processos ao JSON
            })
            # Processamento em segundo plano
            thread = Thread(target=enviar_emails_background, args=(data_inicial, data_final, "API", email, None))
            thread.start()
            thread.join()
            return response

# Rota para gerar e enviar relatório específico
@app.route('/relatorio_especifico', methods=['GET', 'POST'], endpoint='/relatorio_especifico')
    
def relatorio_especifico():
    if request.method == 'GET':
        return render_template('html/relatorio_especifico.html')
    elif request.method == 'POST':
        data = request.get_json()
        data_inicial = data.get('data_inicial')
        data_final = data.get('data_final')
        email = data.get('email')
        codigo = data.get('codigo')
        time.sleep(1)

        if not data_inicial or not data_final:
            response = jsonify({"Campos de 'data' obrigatorios!"})
            response.status_code = 500
            return response
        
        if not email:
            response = jsonify({"Campo 'email' obrigatorio!"})
            response.status_code = 500
            return response

        dados = validar_dados(data_inicial, data_final, codigo, None)

        total_processos = len(dados)

        if not dados:
            response = jsonify({"error": "Nenhum dado encontrado para o dia selecionado!"})
            response.status_code = 500
            return response

        if data_final and data_inicial and email and codigo:
            response = jsonify({
                "message": "Dentro de alguns minutos o relatório estará no seu e-mail!",
                "total_processos": total_processos  # Adiciona o total de processos ao JSON
            })
            # Processamento em segundo plano
            thread = Thread(target=enviar_emails_background, args=(data_inicial, data_final, "API", email, codigo,None))
            thread.start()
            thread.join()
            return response
        
@app.route('/send_pending', methods=['GET', 'POST'])
def send_pending():
    if request.method == 'GET':
        return render_template('html/enviar_pendentes.html')
    elif request.method == 'POST':
        data = request.get_json()
        data_inicial = data.get('data_inicial')
        email = data.get('email')
        codigo = data.get('codigo')
        status = data.get('Status')
        time.sleep(1)

        data_final = data_inicial
        
        if not email:
            response = jsonify({"Campo 'email' obrigatorio!"})
            response.status_code = 500
            return response

        dados = validar_dados(data_inicial, data_final, codigo, status)

        total_processos = len(dados)

        if not dados:
            response = jsonify({"error": "Nenhum dado encontrado para o dia selecionado!"})
            response.status_code = 500
            return response

        if data_final and data_inicial and email and codigo:
            response = jsonify({
                "message": "Dentro de alguns minutos o relatório estará no seu e-mail!",
                "total_processos": total_processos  # Adiciona o total de processos ao JSON
            })
            # Processamento em segundo plano
            thread = Thread(target=enviar_emails_background, args=(data_inicial, data_final, "API", email, codigo,status))
            thread.start()
            thread.join()
            return response        

@app.route('/proxy/relatorio', methods = ['POST'])
def proxy_relatorio():
    data = request.get_json()

    URL= f'http://26.154.23.230:8080/relatorio'

    try:
        response = requests.post(URL,json = data)
        return jsonify(response.json()), response.status_code
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao encaminhar a requisição para o servidor real: {e}")
        return jsonify({"error": "Erro ao comunicar com o servidor real"}), 500

@app.route('/proxy/relatorio_especifico', methods=['POST'])
def proxy_relatorio_especifico():
    data = request.get_json()

    URL= f'http://26.154.23.230:8080/relatorio_especifico'
    
    try:
        response = requests.post(URL,json = data)
        return jsonify(response.json()), response.status_code
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao encaminhar a requisição para o servidor real: {e}")
        return jsonify({"error": "Erro ao comunicar com o servidor real"}), 500

@app.route('/proxy/send_pending',methods=['POST'])
def proxy_send_pending():
    data = request.get_json()

    URL = f'http://26.154.23.230:8080/send_pending'

    try:
        response = requests.post(URL,json=data)
        return jsonify(response.json()), response.status_code
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao encaminhar a requisição para o servidor real: {e}")
        return jsonify({"error": "Erro ao comunicar com o servidor real"}), 500
# Função para execução do agendamento
def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Inicia o Flask e o agendamento
if __name__ == "__main__":
    Thread(target=run_schedule).start()
    app.run(host='0.0.0.0', port=8080, threaded=True)
