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

        if 'api.token' in request.cookies:
            token = request.cookies.get('api.token')

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

def enviar_emails_background(data_inicial=None, data_final=None, origem="API", email=None, codigo=None, status=None, token=None, result_holder=None):
    try:
        logger.info(f"Iniciando envio de e-mails com data_inicial={data_inicial} e data_final={data_final} código: {codigo} status: {status} para o email: {email}")
        
        # Chamada da função de envio de e-mails
        result = enviar_emails(data_inicial, data_final, origem, email, codigo, status, token)
        status_result, code = result
        # Verifica se status_result é um dicionário de erro
        if isinstance(status_result, dict):
            status_message = status_result.get('status', 'unknown')
            message = status_result.get('message')  # Atualiza a mensagem com detalhes do erro, se presente
        else:
            status_message = status_result

        # Armazena no result_holder se fornecido
        if result_holder is not None:
            result_holder["result"] = {
                "status": status_message,
                "message": message,
                "code": code,
            }

        # Logs baseados no resultado
        if code == 200:
            logger.info(f"Envio de e-mails concluído com status={status_message}, código={code}, mensagem={message}")
        else:
            logger.error(f"Erro ao enviar email! Status: {status_message}, Código: {code}, Mensagem: {message}")
        
    except Exception as e:
        logger.error(f"Erro ao enviar e-mails: {e}")
        
        # Armazena a exceção no result_holder
        if result_holder is not None:
            result_holder["result"] = {
                "status": "erro",
                "message": str(e),
                "code": 500,
            }

        
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

@main_bp.route('/api/dados/pendentes')
@token_required
def api_dados_pendentes():
    auth_header = request.headers['Authorization']
    token = auth_header.split(" ")[1]

    pendentes = pendentes_envio(token)
    return jsonify({'pendentes':pendentes})

@main_bp.route('/api/dados/historico')
@token_required
def api_dados_historico():
    auth_header = request.headers['Authorization']
    token = auth_header.split(" ")[1]    
    historico = historio_env(token)
    return jsonify({'historico': historico})

@main_bp.route('/api/dados/total')
@token_required
def api_dados_total():
    auth_header = request.headers['Authorization']
    token = auth_header.split(" ")[1]
    total = total_geral(token)
    return jsonify({'total_enviados':total})


# Rota para gerar e enviar relatório
@main_bp.route('/relatorio', methods=['POST'])
@token_required
def relatorio():
    auth_header = request.headers['Authorization']
    token = auth_header.split(" ")[1]
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

    result_holder = {}

    # Processamento em segundo plano
    thread = Thread(target=enviar_emails_background, args=(data_inicial, data_final, "API", email, None, "S",token))
    thread.start()
    thread.join()
    
    # Acessa o resultado do processamento
    result = result_holder.get("result")
    
    # Verifica se o resultado foi obtido e processa a resposta
    if result:
        status = result.get('status')
        message = result.get('message')
        code = result.get('code')
    else:
        # Caso o resultado não tenha sido obtido, trata com erro
        return jsonify({
            "error": "Erro ao processar o envio de e-mails.",
            "codigo": code,
            "message": "Não foi possível obter o resultado do envio."
        }), 500
    
    if code != 200:
        return jsonify({
            "error": message,
            "codigo": code,
            "status": status
        }), 500
    
    return jsonify({
        "message": "Relatório enviado",
        "resultado": result,
        "total_processos": total_processos
    }), 200


# Rota para gerar e enviar relatório específico
@main_bp.route('/relatorio_especifico', methods=['POST'], endpoint='/relatorio_especifico')
@token_required
def relatorio_especifico():
    auth_header = request.headers['Authorization']
    token = auth_header.split(" ")[1]    
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

    dados = validar_dados(data_inicial, data_final, codigo, "S")

    total_processos = len(dados)

    if not dados:
        response = jsonify({"error": "Nenhum dado encontrado para o dia selecionado!"})
        response.status_code = 500
        return response

    result_holder = {}

    # Processamento em segundo plano
    thread = Thread(target=enviar_emails_background, args=(data_inicial, data_final, "API", email, codigo,"S",token))
    thread.start()
    thread.join()

    # Acessa o resultado do processamento
    result = result_holder.get("result")
    
    # Verifica se o resultado foi obtido e processa a resposta
    if result:
        status = result.get('status')
        message = result.get('message')
        code = result.get('code')
    else:
        # Caso o resultado não tenha sido obtido, trata com erro
        return jsonify({
            "error": "Erro ao processar o envio de e-mails.",
            "codigo": code,
            "message": "Não foi possível obter o resultado do envio."
        }), 500
    
    if code != 200:
        return jsonify({
            "error": message,
            "codigo": code,
            "status": status
        }), 500
    
    return jsonify({
        "message": "Relatório enviado",
        "resultado": result,
        "total_processos": total_processos
    }), 200
        
@main_bp.route('/send_pending', methods=['POST'])
@token_required
def send_pending():
    auth_header = request.headers['Authorization']
    token = auth_header.split(" ")[1]
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
    
    result_holder = {}

    # Processamento em segundo plano
    thread = Thread(target=enviar_emails_background, args=(data_inicial, data_final, "API", email, codigo, status, token, result_holder))
    thread.start()
    thread.join()
    
    # Acessa o resultado do processamento
    result = result_holder.get("result")
    
    # Verifica se o resultado foi obtido e processa a resposta
    if result:
        status = result.get('status')
        message = result.get('message')
        code = result.get('code')
    else:
        # Caso o resultado não tenha sido obtido, trata com erro
        return jsonify({
            "error": "Erro ao processar o envio de e-mails.",
            "codigo": code,
            "message": "Não foi possível obter o resultado do envio."
        }), 500
    
    if code != 200:
        return jsonify({
            "error": message,
            "codigo": code,
            "status": status
        }), 500
    
    return jsonify({
        "message": "Relatório enviado",
        "resultado": result,
        "total_processos": total_processos
    }), 200

