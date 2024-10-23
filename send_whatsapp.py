from logger_config import logger
import json
import requests
def enviar_mensagem_whatsapp(ID_lig, url_Sirius, sirius_Token, numero_cliente, url_arquivo, titulo, descricao, thumbnail):
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {sirius_Token}" 
    }

    data = {
        "validLgpd": True,
        "appId": f"{ID_lig}",
        "type": "WHATSAPP",
        "recipient": numero_cliente,
        "payloadType": "WHATSAPP_THUMB",
        "payload": f"""{{
            "url": "{url_arquivo}",
            "title": "{titulo}",
            "description": "{descricao}",
            "thumb": "{thumbnail}"
        }}"""
    }

    try:
        response = requests.post(url_Sirius, json=data, headers=headers)
        if response.status_code == 200:
            logger.info(f"Mensagem de WhatsApp enviada com sucesso para {numero_cliente}.")

        else:
            logger.error(f"Erro ao enviar WhatsApp: {response.status_code}, {response.text}\n Corpo requisição: {json.dumps(data, indent=4)}.")
    except requests.RequestException as e:
        logger.error(f"Erro na requisição ao enviar WhatsApp: {e}")