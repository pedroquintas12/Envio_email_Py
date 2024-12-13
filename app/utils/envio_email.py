from queue import Queue
from datetime import datetime
import threading
from app.utils.processo_data import fetch_processes_and_clients
from templates.template import generate_email_body
from scripts.mail_sender import send_email
import uuid
from config.logger_config import logger
from scripts.send_whatsapp import enviar_mensagem_whatsapp
from scripts.uploud_To_S3 import upload_html_to_s3
from app.utils.processo_data import fetch_numero
from app.utils.processo_data import fetch_email
from app.utils.processo_data import fetch_companies
from app.utils.processo_data import status_envio
from app.utils.processo_data import status_processo
from app.utils.processo_data import cliente_erro
from config import config

import locale
from dateutil.relativedelta import relativedelta

def enviar_emails(data_inicio = None, data_fim=None, Origem= None, email = None ,codigo= None, status= None):
    try:
        
        data_do_dia = datetime.now()
        if Origem == "API":
            data_inicio_obj = datetime.strptime(data_inicio, "%Y-%m-%d")
            data_fim_obj = datetime.strptime(data_fim, "%Y-%m-%d")
            data_inicio_br = data_inicio_obj.strftime("%d/%m/%Y")
            data_fim_br = data_fim_obj.strftime("%d/%m/%Y")

        # Busca os dados dos clientes e processos
        clientes_data = fetch_processes_and_clients(data_inicio,data_fim,codigo,status,Origem)

        contador_Inativos = 0

        total_escritorios = len(clientes_data)  
        #recupera dos dados do comapanies
        config_smtp = fetch_companies()

        if config_smtp:
                ID_lig,url_Sirius,sirius_Token,aws_s3_access_key,aws_s3_secret_key,bucket_s3,smtp_host, smtp_port, smtp_user,smtp_password,smtp_from_email,smtp_from_name,smtp_reply_to,smtp_cc_emails,smtp_bcc_emails,smtp_envio_test,whatslogo,logo = config_smtp
        else:
                logger.warning("configuração SMTP não encontrada.")
                exit()


        # configuração do SMTP
        smtp_config = (smtp_host, smtp_port, smtp_user, smtp_password,smtp_from_email,smtp_from_name,smtp_reply_to,smtp_cc_emails,smtp_bcc_emails,logo)

        for cliente, processos in clientes_data.items():
            locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
            ID_processo = processos[0]['ID_processo']
            cliente_STATUS = processos[0]['cliente_status']
            cod_cliente = processos[0]['cod_escritorio']
            cliente_number = fetch_numero(cod_cliente)
            emails = fetch_email(cod_cliente)
            env = config.ENV

            # Verificação para todos os processos do cliente
            for processo in processos:
                ID_processo = processo['ID_processo']
                cliente_STATUS = processo['cliente_status']

                # Se o cliente não tem email para ser enviado, marca todos os processos com erro
                if not emails and not email:
                    logger.warning(f"VSAP: {cod_cliente} não tem email cadastrado ou está bloqueado")
                    contador_Inativos += 1
                    cliente_erro(ID_processo)  # Marca este processo com erro
                    continue  # Continua para o próximo processo

                # Verifica se o cliente tem código VSAP
                if not cliente_STATUS:
                    logger.warning(f"VSAP: {cod_cliente} não está cadastrado na API, email não enviado!")
                    contador_Inativos += 1
                    cliente_erro(ID_processo)  # Marca este processo com erro
                    continue  # Continua para o próximo processo

                # Verifica se o Status do cliente está "Liberado (L)"
                if cliente_STATUS[0] != 'L':
                    logger.warning(f"VSAP: {cod_cliente} não está ativo na API, email não enviado!")
                    contador_Inativos += 1
                    cliente_erro(ID_processo)  # Marca este processo com erro
                    continue  # Continua para o próximo processo

            
            localizador = str(uuid.uuid4()) 

            email_body = generate_email_body(cliente, processos, logo, localizador, data_do_dia)
            if env == 'production' or Origem == 'Automatico':
                email_receiver = emails
                bcc_receivers = smtp_bcc_emails
                cc_receiver = smtp_cc_emails
            if env == 'test' :
                email_receiver = smtp_envio_test
                bcc_receivers = smtp_bcc_emails
                cc_receiver = smtp_cc_emails
            if Origem == 'API' :
                email_receiver = email
                bcc_receivers = None
                cc_receiver = smtp_cc_emails

            if data_inicio and data_fim or Origem == 'Automatico':
                data_do_dia = datetime.now()
                subject = f"LIGCONTATO - DISTRIBUIÇÕES {data_do_dia.strftime('%d/%m/%y')} - {cliente}"
            if Origem == 'API':
                subject = f"LIGCONTATO - RELATÓRIO DISTRIBUIÇÕES DATAS: {data_inicio_br} - {data_fim_br} - {cliente}"
               

            # Envia o e-mail
            send_email(smtp_config, email_body, email_receiver, bcc_receivers,cc_receiver, subject)

            # Gera e faz o upload do arquivo HTML para o S3
            if env == 'production':
                object_name = f"{cod_cliente}/{data_do_dia.strftime('%d-%m-%y')}/{localizador}.html"

            if env == 'test':
                object_name = f"test/{cod_cliente}/{data_do_dia.strftime('%d-%m-%y')}/{localizador}.html"

            if Origem == 'API':
                object_name = f"relatorios/{cod_cliente}/{data_inicio}_{data_fim}/{localizador}.html"

            queue = Queue()

            thread = threading.Thread(target=thread_function, args=(email_body, bucket_s3, object_name, aws_s3_access_key, aws_s3_secret_key,queue))
            thread.start()
            thread.join()

            #retorna o link em uma queue
            permanent_url = queue.get()
            if permanent_url:
                if env == 'test' :
                    cliente_number = [{"numero": "5581997067420"}]
                if Origem == 'API':
                    cliente_number = None
                #verifica se o cliente tem numero para ser enviado
                if not cliente_number:
                    logger.warning(f"Cliente: '{cod_cliente}' não tem número cadastrado na API ou email enviado via API")
                else:
                    for numero in cliente_number:
                        #envia a mensagem via whatsapp
                        enviar_mensagem_whatsapp(ID_lig,
                                                url_Sirius,
                                                sirius_Token,
                                                numero['numero'],
                                                permanent_url,
                                                f"Distribuição de novas ações - {cliente}",
                                                f"Total: {len(processos)} Distribuições",
                                                whatslogo
                                                )

            logger.info(f"""E-mail enviado para {cliente}({cod_cliente}) às {datetime.now().strftime('%H:%M:%S')} - Total de processos: {len(processos)}
                            \n---------------------------------------------------""")


            for processo in processos:
                processo_id = processo['ID_processo']

                if cliente_number and isinstance(cliente_number, list):
                    numero = ', '.join(item['numero'] for item in cliente_number if 'numero' in item)
                else:
                    numero = "Cliente não tem número cadastrado na API"  

                status_processo(processo_id)
                status_envio(processo_id,processo['numero_processo'],processo['cod_escritorio'],processo['localizador'],
                                data_do_dia.strftime('%Y-%m-%d'),localizador,email_receiver, numero,permanent_url,Origem)

        logger.info(f"Envio finalizado, total de escritorios enviados: {total_escritorios - contador_Inativos}")
    except Exception as err:
        logger.error(f"Erro ao executar o envio: {err}")

def thread_function(email_body, bucket_s3, object_name, aws_s3_access_key, aws_s3_secret_key, queue):
    try:
        permanent_url = upload_html_to_s3(email_body, bucket_s3, object_name, aws_s3_access_key, aws_s3_secret_key)
        queue.put(permanent_url)  # Coloca o URL na fila para a função principal
    except Exception as e:
        logger.error(f"Erro ao enviar para S3: {e}")
        queue.put(None)
