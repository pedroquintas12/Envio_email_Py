from datetime import datetime

from flask import jsonify
from app.utils.processo_data import fetch_companies,fetch_cliente_cobranca
from config.logger_config import logger
from scripts.mail_sender import send_email
from templates.template_cobranca import generate_email_cobranca
from app.repository.cobranca_repository import cobrancaRepository 

def enviar_email_cobranca(cod_cliente, content,autor):
    try:
        data_do_dia_obj = datetime.now()

        config_smtp = fetch_companies()

        if config_smtp:
                id_companies,ID_lig,url_Sirius,sirius_Token,aws_s3_access_key,aws_s3_secret_key,bucket_s3,bucket_S3_resumo,region,smtp_host, smtp_port, smtp_user,smtp_password,smtp_from_email,smtp_from_name,smtp_reply_to,smtp_cc_emails,smtp_bcc_emails,smtp_envio_test,whatslogo,logo = config_smtp
        else:
                logger.warning("configuração SMTP não encontrada.")
                exit()
        smtp_config = (smtp_host, smtp_port, smtp_user, smtp_password,smtp_from_email,smtp_from_name,smtp_reply_to,smtp_cc_emails,smtp_bcc_emails,logo)



        cliente = fetch_cliente_cobranca(cod_cliente)

        if not cliente:
            logger.warning(f"Cliente: '{cod_cliente}' não encontrado para envio da cobraça.")
            return jsonify({"status": "warning", "message": f"Cliente: '{cod_cliente}' não encontrado para envio da cobraça."}), 400
        
        email_receiver = cliente.get("emails_cobranca")
        nome_cliente = cliente.get("cliente")

        if not email_receiver:
            logger.warning(f"Cliente: '{cod_cliente}' não possui email de cobrança cadastrado.")
            return jsonify({"status": "warning", "message": f"Cliente: '{cod_cliente}' não possui email de cobrança cadastrado."}), 400
        
        email_body = generate_email_cobranca(nome_cliente, "Lig Contato Soluções Jurídicas",content ,logo=logo)

        subject = f"Cobrança de serviços - {nome_cliente} - {datetime.now().strftime('%m/%Y')}"
        resposta_email = send_email(smtp_config, email_body,email_receiver,subject=subject,cc_receiver=smtp_cc_emails) 

        if isinstance(resposta_email, tuple) and resposta_email[0].get("status") == "error":
                logger.warning(f"Erro ao enviar e-mail para {nome_cliente}({cod_cliente}): {resposta_email[0].get('message')}")
                cobrancaRepository.registrar_falha(cod_cliente,email_receiver,subject,content,autor,f'FALHA ENVIO EMAIL {resposta_email[0].get('message')}')

        logger.info(f"E-mail de cobrança enviado com sucesso para {nome_cliente}({cod_cliente}) as {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        cobrancaRepository.registrar_sucesso(cod_cliente,email_receiver,subject,content,autor)

        return jsonify({"status": "success", "message": f"E-mail de cobrança enviado com sucesso para {nome_cliente}({cod_cliente})."}), 200

    except Exception as err:
        logger.error(f"Erro ao enviar e-mail de cobrança para {nome_cliente}({cod_cliente}): {err}")
        return jsonify({"status": "error", "message": str(err)}), 500

        