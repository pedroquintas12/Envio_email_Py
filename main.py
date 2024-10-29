from datetime import datetime
from processo_data import fetch_processes_and_clients
from template import generate_email_body
from mail_sender import send_email
import uuid
import time
import schedule
from logger_config import logger
from send_whatsapp import enviar_mensagem_whatsapp
from uploud_To_S3 import upload_html_to_s3
from processo_data import fetch_numero
from processo_data import fetch_email
from processo_data import fetch_companies
from processo_data import status_envio
from processo_data import cliente_erro
import sys
import os
from dotenv import load_dotenv

#captura o ambiente de execução 
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(__file__)

load_dotenv(os.path.join(base_dir, 'config.env'))

def enviar_emails():
    try:
        data_do_dia = datetime.now()

        # Busca os dados dos clientes e processos
        clientes_data = fetch_processes_and_clients()

        contador_Inativos = 0

        total_escritorios = len(clientes_data)  
        #recupera dos dados do comapanies
        config = fetch_companies()

        if config:
                ID_lig,url_Sirius,sirius_Token,aws_s3_access_key,aws_s3_secret_key,bucket_s3,smtp_host, smtp_port, smtp_user,smtp_password,smtp_from_email,smtp_from_name,smtp_reply_to,smtp_cc_emails,smtp_bcc_emails,smtp_envio_test,whatslogo,logo = config
        else:
                logger.warning("Configuração SMTP não encontrada.")
                exit()


        # Configuração do SMTP
        smtp_config = (smtp_host, smtp_port, smtp_user, smtp_password,smtp_from_email,smtp_from_name,smtp_reply_to,smtp_cc_emails,smtp_bcc_emails,logo)

        for cliente, processos in clientes_data.items():
            ID_processo = processos[0]['ID_processo']
            cliente_STATUS = processos[0]['cliente_status']
            cod_cliente = processos[0]['cod_escritorio']
            cliente_number = fetch_numero(cod_cliente)
            emails = fetch_email(cod_cliente)
            env = os.getenv('ENV')

            #Se o cliente não tem email para ser enviado, logo esta "bloquado"
            if not emails:
                logger.warning(f"VSAP: {cod_cliente} não tem email cadastrado ou esta bloqueado")
                contador_Inativos += 1
                cliente_erro(ID_processo)
                continue
            #verifica se existe algum cliente com esse codigo VSAP
            if not cliente_STATUS:
                logger.warning(f"VSAP: {cod_cliente} não esta cadastrado na API email não enviado!")
                contador_Inativos += 1
                cliente_erro(ID_processo)
                continue
            #verifica se o Status dele esta Liberado(L)
            if cliente_STATUS[0] != 'L':
                logger.warning(f"VSAP: {cod_cliente} não esta ativo na API email não enviado!")
                contador_Inativos += 1
                cliente_erro(ID_processo)
                continue
            

            
            localizador = str(uuid.uuid4()) 

            email_body = generate_email_body(cliente, processos, logo, localizador, data_do_dia)
            if env == 'production':
                email_receiver = emails
            if env == 'test':
                email_receiver = smtp_envio_test
            bcc_receivers = smtp_bcc_emails
            cc_receiver = smtp_cc_emails
            subject = f"LIGCONTATO - DISTRIBUIÇÕES {data_do_dia.strftime('%d/%m/%y')} - {cliente}"

            # Envia o e-mail
            send_email(smtp_config, email_body, email_receiver, bcc_receivers,cc_receiver, subject)

            # Gera e faz o upload do arquivo HTML para o S3
            if env == 'production':
                object_name = f"{cod_cliente}/{data_do_dia.strftime('%d-%m-%y')}/{localizador}.html"
            if env == 'test':
                object_name = f"test/{cod_cliente}/{data_do_dia.strftime('%d-%m-%y')}/{localizador}.html"

            permanent_url = upload_html_to_s3(email_body, bucket_s3, object_name, aws_s3_access_key, aws_s3_secret_key)

            #verifica se o cliente tem numero para ser enviado
            if not cliente_number:
                logger.warning(f"Cliente: '{cod_cliente}' não tem número cadastrado na API")
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

            logger.info(f"""E-mail enviado para {cliente} às {datetime.now().strftime('%H:%M:%S')} - Total de processos: {len(processos)}
                            \n---------------------------------------------------""")


            for processo in processos:
                processo_id = processo['ID_processo']
                status_envio(processo_id,processo['numero_processo'],processo['cod_escritorio'],processo['localizador'],
                                data_do_dia.strftime('%Y-%m-%d'),localizador,email_receiver, cliente_number,permanent_url)
            

        logger.info(f"\nEnvio finalizado, total de escritorios enviados: {total_escritorios - contador_Inativos}")
    except Exception as err:
        logger.error(f"Erro ao executar o codigo: {err}")


# Atualiza a exibição
def Atualizar_lista_pendetes():
    try:
        clientes_data = fetch_processes_and_clients()
        total_escritorios = len(clientes_data)  
        total_processos_por_escritorio = {cliente: len(processos) for cliente, processos in clientes_data.items()}
        logger.info(f"\nAguardando o horário de envio... (Atualizado: {datetime.now().strftime('%d-%m-%y %H:%M')})")
        logger.info(f"Total de escritórios a serem enviados: {total_escritorios}")
        for cliente, total_processos in total_processos_por_escritorio.items():
            logger.info(f"Escritório: {cliente} - Total de processos: {total_processos}  ")
    except Exception as err:
        logger.error(f"erro ao atualizar lista de pendentes: {err}")



# atualiza a lista de pendentes:
schedule.every().hour.do(Atualizar_lista_pendetes)

# # Agenda o envio para todos os dias às 16:00
schedule.every().day.at("16:00").do(enviar_emails)

if __name__ == "__main__":

    Atualizar_lista_pendetes()

    while True:
        schedule.run_pending()  # Executa as tarefas agendadas
        time.sleep(1)