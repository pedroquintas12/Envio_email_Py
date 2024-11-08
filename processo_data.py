from datetime import datetime
from logger_config import logger
from db_conexão import get_db_connection, get_db_ligcontato
from concurrent import futures
import concurrent

# Captura todos os dados do processo
def fetch_processes_and_clients():
    clientes_data = {}
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor(dictionary=True) as db_cursor:
                # Consulta para buscar todos os processos
                db_cursor.execute(""" 
                    SELECT p.Cod_escritorio, p.numero_processo, 
                           MAX(p.data_distribuicao) as data_distribuicao, 
                           p.orgao_julgador, p.tipo_processo, p.status, 
                           p.uf, p.sigla_sistema, MAX(p.instancia) as instancia, p.tribunal, 
                           p.ID_processo, MAX(p.LocatorDB) as LocatorDB, 
                           p.tipo_processo 
                    FROM apidistribuicao.processo AS p 
                    WHERE p.status = 'P'
                    GROUP BY p.numero_processo, p.Cod_escritorio, p.orgao_julgador, p.tipo_processo, 
                             p.uf, p.sigla_sistema, p.tribunal,ID_processo;
                """)
                
                processes = db_cursor.fetchall()
                
                # Pré-carrega autores, réus e links para todos os processos
                autor_dict = fetch_autores_reus_links("autor", processes)
                reu_dict = fetch_autores_reus_links("reu", processes)
                links_dict = fetch_autores_reus_links("links", processes)

                #utiliza o multithreds para otimizar o processamento de dados
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = []
                    for process in processes:
                        futures.append(executor.submit(process_result, process, clientes_data, autor_dict, reu_dict, links_dict))

                    # Wait for all futures to finish
                    concurrent.futures.wait(futures)

    except Exception as err:
        logger.error(f"Erro ao executar a consulta: {err}")

    return clientes_data

def fetch_autores_reus_links(tipo, processes):
    data_dict = {}
    ids = [process['ID_processo'] for process in processes]
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor(dictionary=True) as db_cursor:
                if tipo == "autor":
                    query = """SELECT ID_processo, nome as nomeAutor 
                               FROM apidistribuicao.processo_autor 
                               WHERE ID_processo IN (%s)"""
                elif tipo == "reu":
                    query = """SELECT ID_processo, nome as nomeReu 
                               FROM apidistribuicao.processo_reu 
                               WHERE ID_processo IN (%s)"""
                elif tipo == "links":
                    query = """SELECT ID_processo, ID_Doc_incial as id_link, link_documento as link_doc, tipo as tipoLink 
                               FROM apidistribuicao.processo_docinicial 
                               WHERE ID_processo IN (%s) AND doc_peticao_inicial=0"""
                
                # Converter a lista de IDs para um formato que possa ser usado no SQL
                format_strings = ','.join(['%s'] * len(ids))
                query = query % format_strings  # Substituir o %s pelo número correto de %s
                
                db_cursor.execute(query, tuple(ids))  # Passar a lista de IDs como parâmetros
                results = db_cursor.fetchall()
                
                for row in results:
                    process_id = row['ID_processo']
                    if process_id not in data_dict:
                        data_dict[process_id] = []
                    data_dict[process_id].append(row)
    except Exception as err:
        logger.error(f"Erro ao carregar {tipo}: {err}")
    
    return data_dict

def process_result(process, clientes_data, autor_dict, reu_dict, links_dict):
    clienteVSAP = nome_cliente(process['Cod_escritorio'])
    num_processo = process['numero_processo']
    data_distribuicao = process['data_distribuicao'].strftime('%d/%m/%Y')
    tribunal = process['tribunal']
    uf = process['uf']
    instancia = process['instancia']
    comarca = process['sigla_sistema']
    
    # Pega os autores, réus e links dos dicionários pré-carregados
    autor_list = autor_dict.get(process['ID_processo'], [{"nomeAutor": "[Nenhum dado disponível]"}])
    reu_list = reu_dict.get(process['ID_processo'], [{"nomeReu": "[Nenhum dado disponível]"}])
    links_list = links_dict.get(process['ID_processo'], [])

    status_cliente = validar_cliente(process['Cod_escritorio'])

    # Adiciona os dados ao cliente
    if clienteVSAP not in clientes_data:
        clientes_data[clienteVSAP] = []

    clientes_data[clienteVSAP].append({
        'ID_processo': process['ID_processo'],
        'cod_escritorio': process['Cod_escritorio'],
        'numero_processo': num_processo,
        'data_distribuicao': data_distribuicao,
        'orgao': process['orgao_julgador'],
        'classe_judicial': process['tipo_processo'],
        'autor': autor_list,
        'reu': reu_list,
        'links': links_list,
        'tribunal': tribunal,
        'uf': uf,
        'instancia': instancia,
        'comarca': comarca,
        'localizador': process['LocatorDB'],
        'tipo_processo': process['tipo_processo'],
        'cliente_status': status_cliente
    })
# Captura os números para envio
def fetch_numero(cod_cliente):
    list_numbers = []
    try:
        with get_db_ligcontato() as db_connection:
            with db_connection.cursor() as db_cursor:
                db_cursor.execute("""
                    SELECT nw.`number` 
                    FROM offices_whatsapp_numbers nw 
                    JOIN offices e ON nw.offices_id = e.offices_id 
                    WHERE e.office_code = %s AND nw.status = 'L' AND nw.deleted = 0 
                """, (cod_cliente,))
                cliente_number = db_cursor.fetchall()

                list_numbers = [{'numero': number[0]} for number in cliente_number]

    except Exception as err:
        logger.error(f"Erro na consulta do número de celular: {err}")

    return list_numbers

# Faz a verificação se o cliente está ativo (L) ou Bloqueado (B)
def validar_cliente(cod_cliente):
    try:
        with get_db_ligcontato() as db_connection:
            with db_connection.cursor() as db_cursor:
                db_cursor.execute("SELECT status FROM offices WHERE office_code = %s", (cod_cliente,))
                cliente_STATUS = db_cursor.fetchone()
                
                return cliente_STATUS[0] if cliente_STATUS else None

    except Exception as err:
        logger.error(f"Erro na consulta do status do cliente: {err}")

# Captura emails para serem enviados 
def fetch_email(cod_cliente):
    try:
        with get_db_ligcontato() as db_connection:
            with db_connection.cursor() as db_cursor:
                db_cursor.execute("""
                    SELECT GROUP_CONCAT(DISTINCT oe.email ORDER BY oe.email SEPARATOR ', ') 
                    FROM offices_emails oe 
                    JOIN offices e ON oe.offices_id = e.offices_id 
                    WHERE e.office_code = %s
                    AND oe.status = 'L' AND oe.deleted = 0 AND oe.receive_distribution = 1
                """, (cod_cliente,))
                email_cliente = db_cursor.fetchone()

                return email_cliente[0] if email_cliente else None
    except Exception as err:
        logger.error(f"Erro na consulta do email: {err}")

# Puxa todos os dados necessários para envio de email e WhatsApp (SMTP/URL API)
def fetch_companies():
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor() as db_cursor:
                db_cursor.execute("""
                    SELECT ID_lig, url_Sirius, sirius_Token, aws_s3_access_key, aws_s3_secret_key, bucket_s3,
                           smtp_host, smtp_port, smtp_username, smtp_password, smtp_from_email, smtp_from_name,
                           smtp_reply_to, smtp_cc_emails, smtp_bcc_emails, smtp_envio_test, url_thumbnail_whatsapp, url_thumbnail 
                    FROM companies
                """)
                config = db_cursor.fetchone()
                
                return config

    except Exception as err:
        logger.error(f"Erro na consulta do banco companies: {err}")
        exit()

# Atualiza o status do processo de envio e insere no banco o email enviado
def status_envio(processo_id, numero_processo, cod_escritorio, localizador_processo,
                 data_do_dia, localizador_email, email_receiver, numero, permanent_url):
     
    try:
    
        with get_db_connection() as db_connection:
            with db_connection.cursor() as db_cursor:
                #se não houver numero aplica uma string vazia
                if not numero:
                    numero = ""
                db_cursor.execute("UPDATE processo SET status = 'S', modified_date = %s WHERE ID_processo = %s", (datetime.now(),processo_id))
                db_cursor.execute("""INSERT INTO envio_emails (ID_processo, numero_processo, cod_escritorio, localizador_processo,
                                              data_envio, localizador, email_envio, numero_envio, link_s3, data_hora_envio)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (processo_id, numero_processo, cod_escritorio, localizador_processo, data_do_dia, 
                      localizador_email, email_receiver, numero, permanent_url, datetime.now()))
                
                db_connection.commit()

    except Exception as err:
        logger.error(f"Erro ao atualizar o status de envio do email: {err}")

def nome_cliente(cod_cliente):
    try:
        with get_db_ligcontato() as db_connection:
            with db_connection.cursor() as db_cursor:

                db_cursor.execute("""SELECT description FROM offices WHERE office_code = %s""", (cod_cliente,))
                cliente = db_cursor.fetchone()

                return cliente[0]
    except Exception as err:
        logger.error(f"Erro ao capturar nome: {err}")

def cliente_erro(ID_processo):
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor() as db_cursor:
                db_cursor.execute("""UPDATE apidistribuicao.processo SET status = 'E', modified_date = %s  WHERE (ID_processo = %s)""", (datetime.now(),ID_processo))
                logger.warning(f"Processo '{ID_processo}' marcado com 'E'! ")

                db_connection.commit()

    
    except Exception as err:
        logger.error(f"erro ao atualizar Status de erro: {err}")