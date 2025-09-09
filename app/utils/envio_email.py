from queue import Queue
from datetime import datetime
import threading
from app.utils.processo_data import fetch_processes_and_clients
from templates.template import generate_email_body
from scripts.mail_sender import send_email
import uuid
from config.logger_config import logger
from scripts.uploud_To_S3 import thread_function
from app.utils.processo_data import fetch_companies,status_envio
from app.apiLig import fetch_email_api,fetch_numero_api
from config.JWT_helper import get_random_cached_token
from config import config
import locale
from app.repository.envio_repository import EnvioRepository
from app.service.persistence_policy import format_numbers_for_db
from app.service.envio_whatsapp import WhatsappService

def enviar_emails(data_inicio = None, data_fim=None, Origem= None, email = None ,codigo= None, status= None,numero_processo=None, token = None):
    try:
        
        token = get_random_cached_token(Refresh=True)
        resumo = False
        data_do_dia = datetime.now()
        if Origem == "API":
            data_inicio_obj = datetime.strptime(data_inicio, "%Y-%m-%d")
            data_fim_obj = datetime.strptime(data_fim, "%Y-%m-%d")
            data_inicio_br = data_inicio_obj.strftime("%d/%m/%Y")
            data_fim_br = data_fim_obj.strftime("%d/%m/%Y")

        # Busca os dados dos clientes e processos
        clientes_data = fetch_processes_and_clients(data_inicio,data_fim,codigo,numero_processo,status,Origem,token)

        contador_Inativos = 0

        total_escritorios= len(clientes_data)

        #recupera dos dados do comapanies
        config_smtp = fetch_companies()

        if config_smtp:
                id_companies,ID_lig,url_Sirius,sirius_Token,aws_s3_access_key,aws_s3_secret_key,bucket_s3,bucket_S3_resumo,region,smtp_host, smtp_port, smtp_user,smtp_password,smtp_from_email,smtp_from_name,smtp_reply_to,smtp_cc_emails,smtp_bcc_emails,smtp_envio_test,whatslogo,logo = config_smtp
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
            Office_id = processos[0]['office_id']
            cliente_number = fetch_numero_api(Office_id,token)
            emails = fetch_email_api(Office_id,token)
            localizador = str(uuid.uuid4()) 

            if data_inicio and data_fim or Origem == 'Automatico':
                data_do_dia = datetime.now()
                subject = f"LIGCONTATO - DISTRIBUIÇÕES {data_do_dia.strftime('%d/%m/%y')} - {cliente}"
            if Origem == 'API':
                subject = f"LIGCONTATO - RELATÓRIO DISTRIBUIÇÕES DATAS: {data_inicio_br} - {data_fim_br} - {cliente}"

            env = config.ENV

            erro_no_cliente = False  # Flag para indicar erro no cliente

            # Verificação para todos os processos do cliente
            for processo in processos:
                ID_processo = processo['ID_processo']
                cliente_STATUS = processo['cliente_status']
                numero_processo = processo['numero_processo']
                LocatorDB = processo['localizador']

                if Origem == 'Automatico':
                    # Se o cliente não tem email para ser enviado, marca todos os processos com erro
                    if not emails and not email:
                        logger.warning(f"VSAP: {cod_cliente} não tem email cadastrado ou está bloqueado")
                        EnvioRepository.marcar_processado_se_automatico("E",ID_processo,Origem)                        
                        # Adiciona erro no histórico
                        status_envio(ID_processo, numero_processo, cod_cliente, LocatorDB, 
                                    data_do_dia.strftime('%Y-%m-%d'), localizador, 
                                    'N/A','NÃO ENVIADO - SEM EMAIL CADASTRADO NA API', "N/A", None, Origem, len(processos),"E",subject)
                        
                        erro_no_cliente = True
                        continue

                    # Verifica se o cliente tem código na API
                    if not cliente_STATUS:
                        logger.warning(f"VSAP: {cod_cliente} não está cadastrado na API, email não enviado!")
                        EnvioRepository.marcar_processado_se_automatico("E",ID_processo,Origem) # Marca este processo com erro
                        status_envio(ID_processo, numero_processo, cod_cliente, LocatorDB, 
                                    data_do_dia.strftime('%Y-%m-%d'), localizador, 
                                    'N/A','NÃO ENVIADO - CLIENTE NÃO CADASTRADO NA API',"N/A", None,
                                      Origem, len(processos),"E",subject)
                        erro_no_cliente = True                   
                        continue  # Continua para o próximo processo

                    # Verifica se o Status do cliente está "Liberado (L)"
                    if cliente_STATUS[0] != 'L':
                        logger.warning(f"VSAP: {cod_cliente} não está ativo na API, email não enviado!")
                        EnvioRepository.marcar_processado_se_automatico("E",ID_processo,Origem)  # Marca este processo com erro
                        status_envio(ID_processo, numero_processo, cod_cliente, LocatorDB, 
                                    data_do_dia.strftime('%Y-%m-%d'), localizador, 
                                    'N/A',f'NÃO ENVIADO - STATUS DO CLIENTE({cliente_STATUS})' ,"N/A", None, 
                                    Origem, len(processos),"E",subject)
                        erro_no_cliente = True
                        continue  # Continua para o próximo processo

            if erro_no_cliente:
                contador_Inativos += 1
                continue
            
            localizador = str(uuid.uuid4()) 

            email_body = generate_email_body(cliente, processos, logo, localizador, data_do_dia)
            if env == 'production' or Origem == 'Automatico':
                email_receiver = emails
                bcc_receivers = smtp_bcc_emails
                cc_receiver = smtp_cc_emails
            if env == 'test' :
                email_receiver = smtp_envio_test
                bcc_receivers = smtp_envio_test
                cc_receiver = smtp_envio_test
            if Origem == 'API' :
                email_receiver = email

                if env == 'test':
                    bcc_receivers = None
                else:
                    bcc_receivers = smtp_bcc_emails
                    
                if env == 'test':
                    cc_receiver = smtp_envio_test
                else:
                    cc_receiver = smtp_cc_emails

               

            # Gera e faz o upload do arquivo HTML para o S3
            if env == 'production':
                object_name = f"{cod_cliente}/{data_do_dia.strftime('%d-%m-%y')}/{localizador}.html"

            if env == 'test':
                object_name = f"test/{cod_cliente}/{data_do_dia.strftime('%d-%m-%y')}/{localizador}.html"

            if Origem == 'API':
                object_name = f"relatorios/{cod_cliente}/{data_inicio}_{data_fim}/{localizador}.html"

            queue = Queue()

            thread = threading.Thread(target=thread_function, args=(email_body, bucket_s3, object_name, aws_s3_access_key, aws_s3_secret_key,region,resumo,queue))
            thread.start()
            thread.join()

            #retorna o link em uma queue
            permanent_url = queue.get()
            
            if permanent_url:
                WhatsappService.enviar_whatsapp(
                    cod_cliente,
                    cliente,
                    cliente_number,
                    processos,
                    ID_lig,
                    url_Sirius,
                    sirius_Token,
                    permanent_url,
                    whatslogo,
                    env,
                    Origem
                )
            # Envia o e-mail
            resposta_envio = send_email(smtp_config, email_body, email_receiver, bcc_receivers, cc_receiver, subject)


            # Se a função retornou erro (status == error)
            if isinstance(resposta_envio, tuple) and resposta_envio[0].get("status") == "error":
                logger.warning(f"Erro ao enviar e-mail para {cliente}({cod_cliente}): {resposta_envio[0].get('message')}")
                for processo in processos:
                    EnvioRepository.marcar_processado_se_automatico("E",processo['numero_processo'], Origem)
                    EnvioRepository.registrar_falha(processo, data_do_dia.strftime('%Y-%m-%d'), localizador, email_receiver,
                                f'FALHA ENVIO EMAIL {resposta_envio[0].get('message')}', 'N/A', None, Origem, len(processos), "E",subject)
                    contador_Inativos += 1
                continue  # Pula o restante e vai pro próximo cliente

            logger.info(f"""E-mail enviado para {cliente}({cod_cliente}) às {datetime.now().strftime('%H:%M:%S')} - Total de processos: {len(processos)}""")


            for processo in processos:
                processo_id = processo['ID_processo']

                numero_para_db = format_numbers_for_db(cliente_number if isinstance(cliente_number, list) else None)

                EnvioRepository.marcar_processado_se_automatico("S",processo_id, Origem)

                EnvioRepository.registrar_sucesso(
                    processo,
                    data_do_dia.strftime('%Y-%m-%d'),
                    localizador,
                    email_receiver,
                    numero_para_db,
                    permanent_url,
                    Origem,
                    len(processos),
                    subject
                )
            logger.info("\n---------------------------------------------------")

        logger.info(f"Envio finalizado, total de escritorios enviados: {total_escritorios - contador_Inativos}")
        return {"status": "success", "message": "Emails enviados com sucesso"}, 200

    except Exception as err:
        logger.error(f"Erro ao executar o envio: {err}")
        return {"status": "error", "message": str(err)},500
       

