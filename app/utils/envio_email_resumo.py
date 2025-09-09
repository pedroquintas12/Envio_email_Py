import base64
import gzip
from queue import Queue
from datetime import datetime
import threading
from app.service.envio_historio_email_service import processar_envio_publicacoes
from templates.template_resumo import generate_email_body
from templates.generate_execel import gerar_excel_base64
from scripts.mail_sender import send_email
import uuid
from scripts.uploud_To_S3 import thread_function
from config.logger_config import logger
from app.utils.processo_data import fetch_companies,status_envio_resumo_bulk, puxarClientesResumo
from app.apiLig import fetch_email_api
from config.JWT_helper import get_random_cached_token
from config import config
import locale


def enviar_emails_resumo(
        Origem= None,
        data_inicial = None ,
        email = None ,
        codigo= None,
        token = None):
    try:
        data_do_dia_obj = datetime.now()
        registros_bulk = []
        token = get_random_cached_token(Refresh=True)

        if Origem == "API":
            data_inicio_obj = datetime.strptime(data_inicial, "%Y-%m-%d")
            data_inicio_br = data_inicio_obj.strftime("%d/%m/%Y")
        else:
            data_inicio_obj = data_do_dia_obj.strftime("%Y-%m-%d")
            clientes = puxarClientesResumo()
            codigo = [cliente['Cod_escritorio'] for cliente in clientes]

        config_smtp = fetch_companies()

        if config_smtp:
                id_companies,ID_lig,url_Sirius,sirius_Token,aws_s3_access_key,aws_s3_secret_key,bucket_s3,bucket_S3_resumo,region,smtp_host, smtp_port, smtp_user,smtp_password,smtp_from_email,smtp_from_name,smtp_reply_to,smtp_cc_emails,smtp_bcc_emails,smtp_envio_test,whatslogo,logo = config_smtp
        else:
                logger.warning("configuração SMTP não encontrada.")
                exit()
        resumo = True
    
        # Busca os dados dos clientes e processos
        clientes_data = processar_envio_publicacoes(id_companies,codigo,data_inicio_obj,token)

        if clientes_data == None or not clientes_data:
            return {"status": "error", "message": f"Nenhum processo encontrado para o código {codigo} "}, 404
        
        contador_Inativos = 0

        total_escritorios = len(clientes_data)  
        #recupera dos dados do comapanies

        # configuração do SMTP
        smtp_config = (smtp_host, smtp_port, smtp_user, smtp_password,smtp_from_email,smtp_from_name,smtp_reply_to,smtp_cc_emails,smtp_bcc_emails,logo)

        for cliente, processos in clientes_data.items():
            data_do_dia = datetime.now()
            locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
            ID_processo = processos[0]['publications_id']
            cliente_STATUS = processos[0]['office_status']
            cod_cliente = processos[0]['cod_escritorio']
            Office_id = processos[0]['Office_id']
            emails = fetch_email_api(Office_id,token,"Resumo")
            localizador_email = str(uuid.uuid4()) 
            if data_inicial:
                subject = f"LIGCONTATO - RELATÓRIO PROCESSOS DO DIA {data_inicio_br} - {cliente}"
            else:
                subject = f"LIGCONTATO - RELATÓRIO PROCESSOS {data_do_dia.strftime('%d/%m/%y')} - {cliente}"

            env = config.ENV

            erro_no_cliente = False  # Flag para indicar erro no cliente

            # Verificação para todos os processos do cliente
            for processo in processos:
                cliente_STATUS = processo['office_status']
                numero_processo = processo['numero_processo']

                if Origem == 'Automatico':
                    # Se o cliente não tem email para ser enviado, marca todos os processos com erro
                    if not emails and not email:
                        logger.warning(f"VSAP: {cod_cliente} não tem email cadastrado ou está bloqueado")
                        # Adiciona erro no histórico
                        registros_bulk.append(ID_processo, numero_processo, cod_cliente, None, 
                                    data_do_dia.strftime('%Y-%m-%d'), localizador_email, 
                                    'N/A','NÃO ENVIADO - SEM EMAIL CADASTRADO NA API', "N/A", None, Origem, len(processos),"E",True,subject)
                        
                        erro_no_cliente = True
                        continue

                    # Verifica se o cliente tem código na API
                    if not cliente_STATUS:
                        logger.warning(f"VSAP: {cod_cliente} não está cadastrado na API, email não enviado!")
                        registros_bulk.append(ID_processo, numero_processo, cod_cliente, None, 
                                    data_do_dia.strftime('%Y-%m-%d'), localizador_email, 
                                    'N/A','NÃO ENVIADO - CLIENTE NÃO CADASTRADO NA API',"N/A", None,
                                    Origem, len(processos),"E",True,subject)
                        erro_no_cliente = True                   
                        continue  # Continua para o próximo processo

                    # Verifica se o Status do cliente está "Liberado (L)"
                    if cliente_STATUS[0] != 'L':
                        logger.warning(f"VSAP: {cod_cliente} não está ativo na API, email não enviado!")
                        registros_bulk.append(ID_processo, numero_processo, cod_cliente, None, 
                                    data_do_dia.strftime('%Y-%m-%d'), localizador_email, 
                                    'N/A',f'NÃO ENVIADO - STATUS DO CLIENTE({cliente_STATUS})' ,"N/A", None, 
                                    Origem, len(processos),"E",True,subject)
                        erro_no_cliente = True
                        continue  # Continua para o próximo processo

            if erro_no_cliente:
                contador_Inativos += 1
                continue
            
            localizador_email = str(uuid.uuid4()) 

            email_body = generate_email_body(cliente, processos, logo, localizador_email, data_do_dia)
            attachment = gerar_excel_base64(processos)
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


            # Envia o e-mail
            resposta_envio = send_email(smtp_config, email_body, email_receiver, bcc_receivers, cc_receiver, subject,attachment,cliente,data_do_dia.strftime('%Y-%m-%d'))

            # Se a função retornou erro (status == error)
            if isinstance(resposta_envio, tuple) and resposta_envio[0].get("status") == "error":
                logger.warning(f"Erro ao enviar e-mail para {cliente}({cod_cliente}): {resposta_envio[0].get('message')}")
                for processo in processos:
                    registros_bulk.append(processo['ID_processo'], processo['numero_processo'], processo['cod_escritorio'], None,
                                data_do_dia.strftime('%Y-%m-%d'), localizador_email, email_receiver,
                                f'FALHA ENVIO EMAIL {resposta_envio[0].get('message')}', 'N/A', None, Origem, len(processos), "E", True, subject)
                    contador_Inativos += 1
                continue  # Pula o restante e vai pro próximo cliente

            # gera o excel em base 64
            if isinstance(attachment, bytes):
                # Comprime os dados antes de codificar em Base64
                attachment_BLOB = gzip.compress(attachment)
            else:
                attachment_BLOB = attachment  # já é string Base64

            # Gera e faz o upload do arquivo HTML para o S3
            if env == 'production':
                object_name = f"{cod_cliente}/{data_do_dia.strftime('%d-%m-%y')}/{localizador_email}.html"

            if env == 'test':
                object_name = f"test/{cod_cliente}/{data_do_dia.strftime('%d-%m-%y')}/{localizador_email}.html"

            queue = Queue()

            thread = threading.Thread(target=thread_function, args=(email_body, bucket_S3_resumo, object_name, aws_s3_access_key, aws_s3_secret_key,region,resumo,queue))
            thread.start()
            thread.join()

            permanent_url = queue.get() 

            logger.info(f"""E-mail de resumo enviado para {cliente}({cod_cliente}) às {datetime.now().strftime('%H:%M:%S')} - Total de processos: {len(processos)}
                            \n---------------------------------------------------""")

            for processo in processos:
                processo_id = processo['publications_id']

                if Origem in ("API", "Automatico"):
                    registros_bulk.append((
                        processo_id,
                        processo['numero_processo'],
                        processo['cod_escritorio'],
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

            # Só executa 1 insert em lote no final
            if registros_bulk:
                status_envio_resumo_bulk(registros_bulk)
                
        pass
        logger.info(f"Envio finalizado, total de escritorios enviados: {total_escritorios - contador_Inativos}")
        return {"status": "success", "message": f"Emails enviados com sucesso. Total de processos: {len(processos)} "}, 200

    except Exception as err:
        logger.error(f"Erro ao executar o envio: {err}")
        return {"status": "error", "message": str(err)},500
    