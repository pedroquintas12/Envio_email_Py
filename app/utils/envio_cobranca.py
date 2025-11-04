from datetime import datetime
from config.logger_config import logger
from app.utils.processo_data import fetch_companies, fetch_cliente_cobranca
from scripts.mail_sender import send_email
from templates.template_cobranca import generate_email_cobranca
from app.repository.cobranca_repository import cobrancaRepository

def enviar_email_cobranca(cod_cliente, content, autor, pdf_bytes: bytes = None, pdf_filename: str = "cobranca.pdf"):
    nome_cliente = None
    try:
        config_smtp = fetch_companies()
        if not config_smtp:
            logger.warning("Configuração SMTP não encontrada.")
            return {"status": "error", "message": "Configuração SMTP não encontrada."}, 500

        # desempacota sua tupla
        (id_companies, ID_lig, url_Sirius, sirius_Token,
         aws_s3_access_key, aws_s3_secret_key, bucket_s3, bucket_S3_resumo, region,
         smtp_host, smtp_port, smtp_user, smtp_password,
         smtp_from_email, smtp_from_name, smtp_reply_to,
         smtp_cc_emails, smtp_bcc_emails, smtp_envio_test,
         whatslogo, logo) = config_smtp

        smtp_config = (
            smtp_host, smtp_port, smtp_user, smtp_password,
            smtp_from_email, smtp_from_name, smtp_reply_to,
            smtp_cc_emails, smtp_bcc_emails, logo
        )

        cliente = fetch_cliente_cobranca(cod_cliente)
        if not cliente:
            msg = f"Cliente '{cod_cliente}' não encontrado para envio da cobrança."
            logger.warning(msg)
            return {"status": "warning", "message": msg}, 400

        email_receiver = cliente.get("emails_cobranca")
        nome_cliente = cliente.get("cliente")
        if not email_receiver:
            msg = f"Cliente '{cod_cliente}' não possui email de cobrança cadastrado."
            logger.warning(msg)
            return {"status": "warning", "message": msg}, 400

        email_body = generate_email_cobranca(nome_cliente, "Lig Contato Soluções Jurídicas", content, logo=logo)

        subject = f"Boleto Bancario em Aberto - {nome_cliente}"

        resposta_email = send_email(
            smtp_config=smtp_config,
            email_body=email_body,
            email_receiver=email_receiver,
            subject=subject,
            cc_receiver=smtp_cc_emails,
            tipo="pdf" if pdf_bytes else "pdf",  
            attachment=pdf_bytes
        )

        if isinstance(resposta_email, tuple):
            payload, code = resposta_email
        else:
            payload, code = ({"status": "ok", "message": "E-mail enviado"}, 200)

        if isinstance(payload, dict) and payload.get("status") == "error":
            err_msg = payload.get("message") or "Falha desconhecida no envio de e-mail"
            logger.warning(f"Erro ao enviar e-mail para {nome_cliente}({cod_cliente}): {err_msg}")
            cobrancaRepository.registrar_falha(
                cod_cliente, email_receiver, subject, content, autor,
                f"FALHA ENVIO EMAIL {err_msg}"
            )
            return {"status": "error", "message": err_msg}, code or 500

        logger.info(f"E-mail de cobrança enviado com sucesso para {nome_cliente}({cod_cliente}) as {datetime.now():%Y-%m-%d %H:%M:%S}")
        cobrancaRepository.registrar_sucesso(cod_cliente, email_receiver, subject, content, autor)

        return {"status": "success", "message": f"E-mail enviado para {nome_cliente}({cod_cliente})."}, 200

    except Exception as err:
        logger.error(f"Erro ao enviar e-mail de cobrança para {nome_cliente}({cod_cliente}): {err}")
        return {"status": "error", "message": str(err)}, 500
