import base64
import gzip
from queue import Queue
from datetime import datetime
import threading
import uuid
import locale

from app.service.envio_historio_email_service import processar_envio_publicacoes
from templates.template_resumo import generate_email_body
from templates.generate_execel import gerar_excel_base64
from scripts.mail_sender import send_email
from scripts.uploud_To_S3 import thread_function
from config.logger_config import logger
from app.utils.processo_data import (
    fetch_companies,
    status_envio_resumo_bulk,
    puxarClientesResumo
)
from app.apiLig import fetch_email_api
from config.JWT_helper import get_random_cached_token
from config import config


def enviar_emails_resumo(
    Origem=None,
    data_inicial=None,
    data_fim = None,
    email=None,
    codigo=None,
    token=None,
    tipo=None
):

    registros_bulk = []
    contador_Inativos = 0

    try:

        data_inicio_obj = None
        data_fim_obj = None
        data_inicio_br = None
        data_fim_br = None

        data_do_dia_obj = datetime.now()
        token = get_random_cached_token(Refresh=True)

        # ORIGEM 
        if Origem == "API":
            data_inicio_obj = datetime.strptime(data_inicial, "%Y-%m-%d")
            data_inicio_br = data_inicio_obj.strftime("%d/%m/%Y")
            data_fim_obj = datetime.strptime(data_fim, "%Y-%m-%d")
            data_fim_br = data_fim_obj.strftime("%d/%m/%Y")
        else:
            data_inicio_obj = datetime.now().strftime("%Y-%m-%d")
            clientes = puxarClientesResumo()
            codigo = [cliente['Cod_escritorio'] for cliente in clientes]

        # CONFIG SMTP 
        config_smtp = fetch_companies()

        if not config_smtp:
            logger.warning("Configuração SMTP não encontrada.")
            return {"status": "error", "message": "SMTP não configurado"}, 500

        (
            id_companies, ID_lig, url_Sirius, sirius_Token,
            aws_s3_access_key, aws_s3_secret_key, bucket_s3,
            bucket_S3_resumo, region, smtp_host, smtp_port,
            smtp_user, smtp_password, smtp_from_email,
            smtp_from_name, smtp_reply_to, smtp_cc_emails,
            smtp_bcc_emails, smtp_envio_test, whatslogo, logo
        ) = config_smtp

        smtp_config = (
            smtp_host, smtp_port, smtp_user, smtp_password,
            smtp_from_email, smtp_from_name, smtp_reply_to,
            smtp_cc_emails, smtp_bcc_emails, logo
        )

        env = config.ENV
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')

        #  BUSCA CLIENTES 
        clientes_data = processar_envio_publicacoes(
            id_companies, codigo, data_inicio_obj,data_fim_obj ,token
        )

        if not clientes_data:
            return {"status": "error", "message": "Nenhum processo encontrado"}, 404

        total_escritorios = len(clientes_data)

        # LOOP PRINCIPAL CLIENTES

        for cliente, processos in clientes_data.items():

            try:
                data_do_dia = datetime.now()

                cod_cliente = processos[0]['cod_escritorio']
                Office_id = processos[0]['Office_id']
                cliente_STATUS = processos[0]['office_status']

                localizador_email = str(uuid.uuid4())

                # SUBJECT
                if data_inicial and data_fim:
                    subject = f"LIGCONTATO - RELATÓRIO PROCESSOS DE {data_inicio_br} A {data_fim_br} - {cliente}"

                elif data_inicial:
                    subject = f"LIGCONTATO - RELATÓRIO PROCESSOS DO DIA {data_inicio_br} - {cliente}"

                elif data_fim:
                    subject = f"LIGCONTATO - RELATÓRIO PROCESSOS ATÉ {data_fim_br} - {cliente}"

                else:
                    subject = f"LIGCONTATO - RELATÓRIO PROCESSOS {data_do_dia.strftime('%d/%m/%y')} - {cliente}"

                # EMAIL API 
                try:
                    emails = fetch_email_api(Office_id, token, "Resumo")
                except Exception as err:
                    logger.error(f"Erro ao buscar email API {cod_cliente}: {err}")
                    emails = None

                # VALIDAÇÕES CLIENTE

                erro_no_cliente = False

                if Origem == 'Automatico':

                        # Sem email
                        if not emails:
                            logger.warning(f"VSAP: {cod_cliente} sem email")


                            registros_bulk.append((
                                cod_cliente,
                                data_do_dia.strftime('%Y-%m-%d'),
                                localizador_email,
                                subject,
                                'N/A',
                                'SEM EMAIL CADASTRADO',
                                None,
                                Origem,
                                len(processos),
                                "E",
                                subject
                            ))
                            erro_no_cliente = True

                        # Não cadastrado API
                        if not cliente_STATUS:
                            logger.warning(f"VSAP: {cod_cliente} não cadastrado API")


                            registros_bulk.append((
                                cod_cliente,
                                data_do_dia.strftime('%Y-%m-%d'),
                                localizador_email,
                                subject,
                                'N/A',
                                'CLIENTE NÃO CADASTRADO NA API',
                                None,
                                Origem,
                                len(processos),
                                "E",
                                subject
                            ))

                            erro_no_cliente = True

                        # Status não liberado
                        if cliente_STATUS[0] != 'L':
                            logger.warning(f"VSAP: {cod_cliente} não ativo")

                            registros_bulk.append((
                                cod_cliente,
                                data_do_dia.strftime('%Y-%m-%d'),
                                localizador_email,
                                subject,
                                'N/A',
                                f'STATUS CLIENTE {cliente_STATUS}',
                                None,
                                Origem,
                                len(processos),
                                "E",
                                subject
                            ))

                            erro_no_cliente = True
                if erro_no_cliente:
                    contador_Inativos += 1
                    continue

    
                # GERA EMAIL BODY

                try:
                    email_body = generate_email_body(
                        cliente, processos, logo,
                        localizador_email, data_do_dia
                    )
                except Exception as err:
                    logger.error(f"Erro gerando HTML {cod_cliente}: {err}")
                    contador_Inativos += 1
                    continue

                # GERA EXCEL
                
                try:
                    attachment = gerar_excel_base64(processos)
                except Exception as err:
                    logger.error(f"Erro gerando Excel {cod_cliente}: {err}")
                    attachment = None

                # DESTINATÁRIOS

                if env == 'production' or Origem == 'Automatico':
                    email_receiver = emails
                    bcc_receivers = smtp_bcc_emails
                    cc_receiver = smtp_cc_emails

                if env == 'test':
                    email_receiver = smtp_envio_test
                    bcc_receivers = smtp_envio_test
                    cc_receiver = smtp_envio_test

                if Origem == 'API':
                    email_receiver = email
                    bcc_receivers = None if env == 'test' else smtp_bcc_emails
                    cc_receiver = smtp_envio_test if env == 'test' else smtp_cc_emails

                # ENVIO EMAIL

                try:
                    resposta_envio = send_email(
                        smtp_config, email_body, email_receiver,
                        bcc_receivers, cc_receiver, subject,
                        attachment, cliente,
                        data_do_dia.strftime('%Y-%m-%d'),
                        tipo=tipo
                    )
                except Exception as err:
                    logger.error(f"Erro SMTP {cod_cliente}: {err}")
                    contador_Inativos += 1
                    continue

                # PREPARA BLOB

                attachment_BLOB = None
                if isinstance(attachment, bytes):
                    attachment_BLOB = gzip.compress(attachment)

                # UPLOAD S3

                permanent_url = None

                try:

                    if env == 'production':
                        object_name = f"{cod_cliente}/{data_do_dia.strftime('%d-%m-%y')}/{localizador_email}.html"
                    else:
                        object_name = f"test/{cod_cliente}/{data_do_dia.strftime('%d-%m-%y')}/{localizador_email}.html"

                    queue = Queue()

                    thread = threading.Thread(
                        target=thread_function,
                        args=(
                            email_body,
                            bucket_S3_resumo,
                            object_name,
                            aws_s3_access_key,
                            aws_s3_secret_key,
                            region,
                            True,
                            queue
                        )
                    )

                    thread.start()
                    thread.join()

                    permanent_url = queue.get()

                except Exception as err:
                    logger.error(f"Erro upload S3 {cod_cliente}: {err}")

                # REGISTRA SUCESSO

                registros_bulk.append((
                    cod_cliente,
                    data_do_dia.strftime('%Y-%m-%d'),
                    localizador_email,
                    subject,
                    email_receiver,
                    'SUCESSO',
                    permanent_url,
                    Origem,
                    len(processos),
                    "S",
                    attachment_BLOB
                ))

                logger.info(
                    f"E-mail enviado para {cliente} ({cod_cliente}) \n --------------------------------------------"
                )

            except Exception as cliente_error:
                logger.error(f"Erro cliente {cliente}: {cliente_error}")
                contador_Inativos += 1
                continue

        # INSERT EM LOTE FINAL

        if registros_bulk:
            try:
                status_envio_resumo_bulk(registros_bulk)
            except Exception as err:
                logger.error(f"Erro insert histórico: {err}")

        logger.info(
            f"Envio finalizado. Total enviados: {total_escritorios - contador_Inativos} de {total_escritorios}"
        )

        return {
            "status": "success",
            "message": f"Envio finalizado. Total de processos: {len(processos)}"
        }, 200

    except Exception as fatal_error:
        logger.critical(f"Erro fatal envio resumo: {fatal_error}")
        return {"status": "error", "message": str(fatal_error)}, 500
