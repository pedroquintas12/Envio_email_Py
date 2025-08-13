from config.logger_config import logger
from app.utils.envio_email_resumo import enviar_emails_resumo

def enviar_emails_background_resumo(data_inicial=None, origem="API", email=None, codigo=None, result_holder=None, token =None):
    try:
        logger.info(f"Iniciando envio de e-mails com data_inicial={data_inicial} código: {codigo} para o email: {email}")
        
        # Chamada da função de envio de e-mails
        result = enviar_emails_resumo(origem, data_inicial,email, codigo,token)

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