import requests
from config.logger_config import logger
from config import config
from config.exeptions import ApiError
def fetch_cliente_api(cod_cliente,token):
    try:
        api_url = f"{config.UrlApiLig}/offices?search={cod_cliente}"  
        headers = {"Authorization": f"Bearer {token}"}  # Inclui o token necessário
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        cliente_data = response.json()

        for item in cliente_data.get("data", []):
            office_description = item.get("description")
            office_id = item.get("id")  # Pegando o ID do cliente
            office_status = item.get("status")

            return office_description, office_id, office_status
        return None, None, None
    except requests.RequestException as err:
        logger.error(f"Erro ao acessar a API de cliente: {err}")
        raise ApiError(f"Falha na comunicação com API: {err}")
    
def fetch_email_api(Id_cliente,token,origem=None):
    try:
        api_url = f"{config.UrlApiLig}/offices/emails?officesId={Id_cliente}"  
        headers = {"Authorization": f"Bearer {token}"}  # Inclui o token necessário
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        cliente_data = response.json()
        emails = []

        for item in cliente_data.get("data", []):
            if item.get("status") != "L":
                continue
            if origem == None:
                if item.get("receiveDistributions") != True:
                    continue
            
            office_email = item.get("email")
            if  office_email:
                emails.append(office_email)
        return ", ".join(emails)
    except requests.RequestException as err:
        logger.error(f"Erro ao acessar a API de email: {err}")
        raise ApiError(f"Falha na comunicação com API: {err}")

def fetch_numero_api(Id_cliente,token):
    try:
        api_url = f"{config.UrlApiLig}/offices/whatsapp-numbers?officesId={Id_cliente}"
        headers = {"Authorization": f"Bearer {token}"}  # Inclui o token necessário
        response = requests.get(api_url,headers=headers)
        response.raise_for_status()
        cliente_data = response.json()
        numeros = []
        
        for item in cliente_data.get("data", []):
            if item.get("status")!= "L":
                continue
            office_number = item.get("number")
            if office_number:
                numeros.append(office_number)

        return numeros
    
    except requests.RequestException as err:
        logger.error(f"Erro ao acessar a API de numero: {err}")
        raise ApiError(f"Falha na comunicação com API: {err}")



def fetch_cliente_api_dashboard(cod_cliente, token):
    try:
        api_url = f"{config.UrlApiLig}/offices?search={cod_cliente}"  
        headers = {"Authorization": f"Bearer {token}"}  # Inclui o token necessário
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        cliente_data = response.json()

        for item in cliente_data.get("data", []):
            office_description = item.get("description")

            return office_description
        return None
    except requests.RequestException as err:
        logger.error(f"Erro ao acessar a API de cliente: {err}")
        raise ApiError(f"Falha na comunicação com API: {err}")
