# Configuração do cache (suporta múltiplos tokens, com limite de 100 tokens)
from datetime import datetime
from datetime import datetime, timedelta
import random
from cachetools import LRUCache
import jwt
import requests
from config import config
from config.logger_config import logger

token_cache = LRUCache(maxsize=100)

if config.ENV == 'test':
    UrlApiProd = config.UrlApiTest

if config.ENV == 'production':
    UrlApiProd = config.UrlApiProd

# URL para renovar tokens
TOKEN_REFRESH_URL = f"{config.UrlApiProd}/login"

print(TOKEN_REFRESH_URL)

def save_token_in_cache(token):
    """
    Salva um token no cache junto com seu tempo de expiração.
    """
    # Verifica se o token já está no cache
    if token in token_cache:
        return
    
    try:
        decoded_token = jwt.decode(token, options={"verify_signature": False})
        exp_timestamp = decoded_token.get("exp")
        
        if exp_timestamp:
            exp_time = datetime.fromtimestamp(exp_timestamp)
            remaining_time = (exp_time - datetime.utcnow()).total_seconds()
            
            if remaining_time > 0:
                # Salva o token e sua expiração no cache
                token_cache[token] = {"expiration": exp_time}
                logger.info(f"Token salvo no cache. Expira em {exp_time}.")
            else:
                logger.warning("Token já expirado. Não foi salvo no cache.")
        else:
            logger.warning("Token não possui campo 'exp'.")
    except Exception as e:
        logger.error(f"Erro ao salvar token no cache: {e}")


def get_cached_token(token_identifier, Refresh):
    """
    Recupera um token do cache pelo identificador e verifica se está próximo de expirar.
    Se o token estiver prestes a expirar, ele será renovado.
    """
    token_info = token_cache.get(token_identifier)

    if token_info:
        expiration = token_info.get("expiration")
        time_to_expire = (expiration - datetime.utcnow()).total_seconds()

        logger.info(f"Tempo restante para o token expirar: {time_to_expire} segundos.")

        if time_to_expire <= 0:
            logger.warning("Token expirado.")
            if Refresh:
                logger.info("Criando um novo token, Refresh habilitado.")
                new_token = refresh_token()
                return new_token
            else:
                logger.error("Token expirado e Refresh não está habilitado.")
                return None
            
        # Renova o token se faltar menos de 5 minutos para expirar
        if time_to_expire < 300:  # 5 minutos
            logger.warning("Token próximo de expirar. Renovando...")
            new_token = refresh_token()
            return new_token
        return token_identifier
    else:
        logger.error("Token não encontrado no cache ou já expirado.")
        return None


def refresh_token():
    """
    Faz uma requisição para obter um novo token e salva no cache.
    """
    try:
        response = requests.post(TOKEN_REFRESH_URL, json={"username": config.USERNAME, "password": config.PASSWORD})
        

        if response.status_code == 200:
            new_token = response.json().get("token")
            save_token_in_cache(new_token)
            return new_token
        else:
            logger.info(f"Erro ao renovar o token. Código: {response.status_code}. Detalhes: {response.text}")
    except Exception as e:
        logger.error(f"Erro ao renovar o token: {e}")

    return None


def remove_expired_tokens():
    """
    Remove tokens expirados do cache.
    """
    expired_tokens = []
    for token, data in token_cache.items():
        expiration = data.get("expiration")
        if expiration < datetime.utcnow():
            expired_tokens.append(token)
    
    for token in expired_tokens:
        del token_cache[token]
        logger.info(f"Token expirado removido do cache: {token}")



def get_random_cached_token(Refresh = False):
    """
    Recupera um token aleatório que está salvo no cache. Caso o cache esteja vazio,
    solicita um novo token através do refresh_token().
    """
    if not token_cache:
        logger.warning("Cache está vazio. Tentando obter um novo token.")
        
        new_token = refresh_token()
        
        if new_token:
            return new_token
        else:
            logger.error("Falha ao obter um novo token.")
            return None

    # Pega uma chave aleatória do cache se existir
    random_token_key = random.choice(list(token_cache.keys()))
    
    # Verifica se o token recuperado está válido
    token_valid = get_cached_token(random_token_key, Refresh)

    return token_valid

def list_all_cached_tokens():
    """
    Retorna uma lista de todos os tokens no cache com informações de expiração.
    """
    tokens = []
    for token, data in token_cache.items():
        expiration = data.get("expiration", "Sem expiração registrada")
        tokens.append({
            "token": token,
            "expiration": expiration.strftime('%Y-%m-%d %H:%M:%S') if isinstance(expiration, datetime) else expiration
        })
    return tokens
