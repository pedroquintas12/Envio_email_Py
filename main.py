from datetime import datetime
from processo_data import fetch_processes_and_clients
from template import generate_email_body
from mail_sender import send_email
import mysql.connector
import uuid
import time
import schedule
from logger_config import logger
from send_whatsapp import enviar_mensagem_whatsapp
from uploud_To_S3 import upload_html_to_s3
from processo_data import fetch_numero
from processo_data import fetch_email
from db_conexão import get_db_connection
from db_conexão import get_db_ligcontato

def enviar_emails():

    
    data_do_dia = datetime.now()

    # Busca os dados dos clientes e processos
    clientes_data = fetch_processes_and_clients()

    contador_Inativos = 0

    total_escritorios = len(clientes_data)  

    try:
        db_connection = get_db_connection()
        db_cursor = db_connection.cursor()

        # Puxar dados de configuração do SMTP
        db_cursor.execute("""SELECT ID_lig, url_Sirius, sirius_Token,aws_s3_access_key,aws_s3_secret_key,bucket_s3,smtp_host, smtp_port, smtp_username, smtp_password, smtp_from_email, 
                          smtp_from_name,smtp_reply_to, smtp_cc_emails,smtp_bcc_emails,smtp_envio_test, url_thumbnail_whatsapp, url_thumbnail FROM companies""")
        config = db_cursor.fetchone()

        if config:
            ID_lig,url_Sirius,sirius_Token,aws_s3_access_key,aws_s3_secret_key,bucket_s3,smtp_host, smtp_port, smtp_user,smtp_password,smtp_from_email,smtp_from_name,smtp_reply_to,smtp_cc_emails,smtp_bcc_emails,smtp_envio_test,whatslogo,logo = config
        else:
            logger.warning("Configuração SMTP não encontrada.")
            exit()
    except mysql.connector.Error as err:
        logger.error(f"Erro ao conectar ao banco de dados: {err}")
        exit()

    # Configuração do SMTP
    smtp_config = (smtp_host, smtp_port, smtp_user, smtp_password,smtp_from_email,smtp_from_name,smtp_reply_to,smtp_cc_emails,smtp_bcc_emails,logo)

    for cliente, processos in clientes_data.items():
         
        cliente_STATUS = processos[0]['cliente_status']
        cod_cliente = processos[0]['cod_escritorio']
        cliente_number = fetch_numero(cod_cliente)
        #emails = fetch_email(cod_cliente)

        if cliente_STATUS and cliente_STATUS[0] != 'L':
            logger.warning(f"VSAP: {cod_cliente} Não esta ativo, email não enviado!")
            contador_Inativos += 1
            continue
        
        localizador = str(uuid.uuid4()) 

        email_body = generate_email_body(cliente, processos, logo, localizador, data_do_dia)
        email_receiver =  smtp_envio_test #processos[0]['emails']
        bcc_receivers = smtp_bcc_emails
        cc_receiver = smtp_cc_emails
        subject = f"LIGCONTATO - DISTRIBUIÇÕES {data_do_dia.strftime('%d/%m/%y')} - {cliente}"

        try:

            # Envia o e-mail
            send_email(smtp_config, email_body, email_receiver, bcc_receivers,cc_receiver, subject)

            # Gera e faz o upload do arquivo HTML para o S3
            object_name = f"{cod_cliente}/{data_do_dia.strftime('%d-%m-%y')}/{localizador}.html"
            permanent_url = upload_html_to_s3(email_body, bucket_s3, object_name, aws_s3_access_key, aws_s3_secret_key)

            #verifica se o cliente tem numero para ser enviado
            # if not cliente_number:
            #     logger.warning(f"Cliente: '{cod_cliente}' não tem número cadastrado na API")
            # else:
            #     for numero in cliente_number:
            #         #envia a mensagem via whatsapp
            #         enviar_mensagem_whatsapp(ID_lig,
            #                                 url_Sirius,
            #                                 sirius_Token,
            #                                 numero['numero'],
            #                                 permanent_url,
            #                                 f"Distribuição de novas ações - {cliente}",
            #                                 f"Total: {len(processos)} publicações",
            #                                 whatslogo
            #                                 )

            logger.info(f"""E-mail enviado para {cliente} às {datetime.now().strftime('%H:%M:%S')} - Total de processos: {len(processos)}
                            numeros: {','.join(cliente_number[0] for cliente_number in cliente_number)}\n---------------------------------------------------""")


            for processo in processos:
                processo_id = processo['ID_processo']  
                #db_cursor.execute("UPDATE processo SET status = 'S' WHERE ID_processo = %s", (processo_id,))
                db_cursor.execute("""INSERT INTO envio_emails (ID_processo, numero_processo, 
                                  cod_escritorio, localizador_processo, data_envio, localizador, email_envio, numero_envio, link_s3, data_hora_envio)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,%s)""",
                                    (processo_id,   
                                    processo['numero_processo'],
                                    processo['cod_escritorio'],
                                    processo['localizador'], 
                                    data_do_dia.strftime('%Y-%m-%d'),
                                    localizador, 
                                    email_receiver,
                                    ','.join(cliente_number[0] for cliente_number in cliente_number),
                                    permanent_url,
                                    datetime.now()))

            db_connection.commit()  # Commit all changes
   
        except mysql.connector.Error as err:
            logger.error(f"Erro ao atualizar o status ou registrar o envio: {err}")

    logger.info(f"\nEnvio finalizado, total de escritorios enviados: {total_escritorios - contador_Inativos}")

def Atualizar_lista_pendetes():
    
        clientes_data = fetch_processes_and_clients()
        total_escritorios = len(clientes_data)  
        total_processos_por_escritorio = {cliente: len(processos) for cliente, processos in clientes_data.items()}
        # Atualiza a exibição
        logger.info(f"\nAguardando o horário de envio... (Atualizado: {datetime.now().strftime('%d-%m-%y %H:%M')})")
        logger.info(f"Total de escritórios a serem enviados: {total_escritorios}")
        for cliente, total_processos in total_processos_por_escritorio.items():
            logger.info(f"Escritório: {cliente} - Total de processos: {total_processos}")



# atualiza a lista de pendentes:

#schedule.every(30).minutes.do(Atualizar_lista_pendetes)

# Agenda o envio para todos os dias às 16:00
#schedule.every().day.at("16:00").do(enviar_emails)

if __name__ == "__main__":

    enviar_emails()
    # Atualizar_lista_pendetes()
    
    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)

    



