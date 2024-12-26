from datetime import datetime
from functools import wraps
from threading import Thread
import time

import jwt
import requests
from config.logger_config import logger
from app.utils.envio_email import enviar_emails
from flask import Blueprint, jsonify, request
from config import config
from app.utils.processo_data import total_geral,historio_env,pendentes_envio,validar_dados
from config.JWT_helper import save_token_in_cache,get_cached_token, get_random_cached_token


main_bp = Blueprint('main', __name__)

if config.ENV == 'test':
    UrlApiProd = config.UrlApiTest

if config.ENV == 'production':
    UrlApiProd = config.UrlApiProd

def obter_token():
    """
    Obtém o token da requisição, seja do cabeçalho Authorization ou dos cookies.

    Returns:
        str: O token JWT extraído, ou None se não estiver presente.
    """
    token = None

    # Verifica se o token está nos cookies
    if 'api.token' in request.cookies:
        token = request.cookies.get('api.token')

    # Verifica se o token está no cabeçalho Authorization
    if 'Authorization' in request.headers:
        auth_header = request.headers['Authorization']
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    return token

@main_bp.route('/save-token', methods=['POST'])
def save_token():
    token = obter_token()
    if not token:
        return jsonify({"error": "Token is required"}), 400
    
    save_token_in_cache(token)
    
    return jsonify({"message": "Token saved successfully"}), 200

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = obter_token()
        
        if not token:
            return jsonify({"error": "Token obrigatorio"}), 401
        
        get_cached_token(token)

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
            codigo_api = code
        else:
            status_message = status_result

        # Armazena no result_holder se fornecido
        if result_holder is not None:
            result_holder["result"] = {
                "status": status_message,
                "message": message,
                "code": codigo_api,
            }

        # Logs baseados no resultado
        if codigo_api == 200:
            logger.info(f"Envio de e-mails concluído com status={status_message}, código={codigo_api}, mensagem={message}")
        else:
            logger.error(f"Erro ao enviar email! Status: {status_message}, Código: {codigo_api}, Mensagem: {message}")
        
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
    # Obtém o token do header de autorização
    auth_header = request.headers.get('Authorization')
    token = auth_header.split(" ")[1] if auth_header else None
    
    # Verifica se o token existe
    if not token:
        return jsonify({"error": "Token inválido ou ausente."}), 403
    
    # Obtém os parâmetros start e end (se existirem) da query string
    start_date = request.args.get('start')  # Data de início (opcional)
    end_date = request.args.get('end')      # Data de fim (opcional)
    
    # Chamando a função total_geral, passando o token e as datas se existirem
    total = total_geral(token, start_date, end_date)
    
    # Retorna os dados no formato JSON
    return jsonify({'total_enviados': total})

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
    print(f"json api: {result}")
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

