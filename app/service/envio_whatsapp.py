from typing import Optional
from config import config
from scripts.send_whatsapp import enviar_mensagem_whatsapp
from config.logger_config import logger

class WhatsappService:
   
   def enviar_whatsapp(
        self,
        cod_cliente = int,
        cliente = str,
        cliente_number = Optional[list],
        processos = list,
        ID_lig = int,
        url_Sirius = str,
        sirius_Token = str,
        permanent_url = str,
        whatslogo = str,
        env = str,
        Origem = str
    ):

    if env == 'test' :
        cliente_number = ["5581997067420"]
    if Origem == 'API':
        cliente_number = None
    #verifica se o cliente tem numero para ser enviado
    if not cliente_number:
        logger.warning(f"Cliente: '{cod_cliente}' não tem número cadastrado na API ou email enviado via API")
    else:
        if config.WHATSAPP_ENABLED == True:
            for numero in cliente_number:
                #envia a mensagem via whatsapp
                enviar_mensagem_whatsapp(ID_lig,
                                        url_Sirius,
                                        sirius_Token,
                                        numero,
                                        permanent_url,
                                        f"Distribuição de novas ações - {cliente}",
                                        f"Total: {len(processos)} Distribuições",
                                        whatslogo
                                        )