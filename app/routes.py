from datetime import datetime
from functools import wraps
from threading import Thread
import time

import jwt
import requests
from config.logger_config import logger
from app.utils.envio_email import enviar_emails
from flask import Blueprint, jsonify, make_response, redirect, render_template, request, url_for
from app.utils.processo_data import validar_dados
from config import config
from app.utils.processo_data import total_geral
from app.utils.processo_data import historio_env
from app.utils.processo_data import pendentes_envio

main_bp = Blueprint('main', __name__)

if config.ENV == 'test':
    UrlApiProd = config.UrlApiTest

if config.ENV == 'production':
    UrlApiProd = config.UrlApiProd

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        
        if not token:
            return jsonify({"error": "Token obrigatorio"}), 401

        try:
            # Decodificar e validar o token
            jwt.decode(token, config.SECRET_TOKEN, algorithms=["HS512"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401

        # Token válido, continuar para a rota
        return f(*args, **kwargs)

    return decorated

# Função para enviar e-mails em background
def enviar_emails_background(data_inicial=None, data_final=None, origem="API", email=None, codigo=None,status = None):
    try:
        logger.info(f"Iniciando envio de e-mails com data_inicial={data_inicial} e data_final={data_final} código: {codigo} status: {status} para o email: {email}")
        result = enviar_emails(data_inicial, data_final, origem, email, codigo,status)
        if result:
            status, code = result
            logger.info(f"Envio de e-mails concluído com status={status}, código={code}")
    except Exception as e:
        logger.error(f"Erro ao enviar e-mails: {e}")
        status, code = "erro", 500
        
@main_bp.route('/api/dados')
@token_required
def api_dados():

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
@main_bp.route('/relatorio', methods=['POST'])
@token_required
def relatorio():
    data = request.get_json()
    data_inicial = data.get('data_inicial')
    data_final = data.get('data_final')
    email = data.get('email') 

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
        thread = Thread(target=enviar_emails_background, args=(data_inicial, data_final, "API", email, "enviado"))
        thread.start()
        thread.join()
        return response

# Rota para gerar e enviar relatório específico
@main_bp.route('/relatorio_especifico', methods=['POST'], endpoint='/relatorio_especifico')
@token_required
def relatorio_especifico():
    data = request.get_json()
    data_inicial = data.get('data_inicial')
    data_final = data.get('data_final')
    email = data.get('email')
    codigo = data.get('codigo')
    
    if not data_inicial or not data_final:
        response = jsonify({"Campos de 'data' obrigatorios!"})
        response.status_code = 500
        return response
    
    if not email:
        response = jsonify({"Campo 'email' obrigatorio!"})
        response.status_code = 500
        return response

    dados = validar_dados(data_inicial, data_final, codigo, "enviado")

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
        thread = Thread(target=enviar_emails_background, args=(data_inicial, data_final, "API", email, codigo,"enviado"))
        thread.start()
        thread.join()
        return response
        
@main_bp.route('/send_pending', methods=['POST'])
@token_required
def send_pending():
    data = request.get_json()
    data_inicial = data.get('data_inicial')
    email = data.get('email')
    codigo = data.get('codigo')
    status = data.get('Status')

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
            "total_processos": total_processos  
        })
        # Processamento em segundo plano
        thread = Thread(target=enviar_emails_background, args=(data_inicial, data_final, "API", email, codigo,status))
        thread.start()
        thread.join()
        return response        


