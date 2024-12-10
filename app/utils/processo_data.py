from datetime import datetime
from config.logger_config import logger
from config.db_conexão import get_db_connection, get_db_ligcontato
from concurrent import futures
import concurrent
import mysql.connector
from concurrent.futures import ThreadPoolExecutor, as_completed

# Captura todos os dados do processo
def fetch_processes_and_clients(data_inicio, data_fim, codigo, status, origem):
    clientes_data = {}
    try:
        db_connection = get_db_connection()
        db_cursor = db_connection.cursor(dictionary=True)
                # Consulta para buscar todos os processos
        query=""" 
                    SELECT p.Cod_escritorio, p.numero_processo, 
                        MAX(p.data_distribuicao) as data_distribuicao, 
                        p.orgao_julgador, p.tipo_processo, p.status, 
                        p.uf, p.sigla_sistema, MAX(p.instancia) as instancia, p.tribunal, 
                        p.ID_processo, MAX(p.LocatorDB) as LocatorDB, 
                        p.tipo_processo 
                    FROM apidistribuicao.processo AS p """

        if data_inicio and data_fim:
            query += "WHERE DATE(p.data_insercao) between  %s and %s "
            if status == 'enviado' or origem == 'API':
                query += "AND p.status = 'S' "
            if status == 'pendente':
                query += "AND p.status = 'P' "              
        
        if not data_inicio and not data_fim and not codigo:
                query += "WHERE p.status = 'P' "
        if codigo:
            query+= "AND p.Cod_escritorio = %s "
            
        query+= """GROUP BY p.numero_processo, p.Cod_escritorio, p.orgao_julgador, p.tipo_processo, 
                            p.uf, p.sigla_sistema, p.tribunal,ID_processo;
                """
        if codigo:
            db_cursor.execute(query, (data_inicio, data_fim, codigo)) 

        if data_inicio and data_fim and not codigo:
            db_cursor.execute(query, (data_inicio, data_fim))

        if not data_inicio and not data_fim and not codigo:
            db_cursor.execute(query)

        processes = db_cursor.fetchall()

        if processes:
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

    except mysql.connector.Error as err:
        logger.error(f"Erro ao executar a consulta: {err}")
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
    finally:
        if db_cursor:
            db_cursor.close()
        if db_connection:
            db_connection.close()

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
# Atualiza o status do processo enviado
def status_processo(processo_id):
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor() as db_cursor:
                db_cursor.execute("UPDATE processo SET status = 'S', modified_date = %s WHERE ID_processo = %s", (datetime.now(),processo_id))

                db_connection.commit()
    except Exception as err:
        logger.error(f"Erro ao atulaizar status do email para 'S': {err}")

# Insere no banco o email enviado
def status_envio(processo_id, numero_processo, cod_escritorio, localizador_processo,
                data_do_dia, localizador_email, email_receiver, numero, permanent_url, Origem):

    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor() as db_cursor:
                db_cursor.execute("""
                    INSERT INTO envio_emails (ID_processo, numero_processo, cod_escritorio, localizador_processo,
                                            data_envio, localizador, email_envio, numero_envio, link_s3, Origem,data_hora_envio)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,%s, %s)
                """, (processo_id, numero_processo, cod_escritorio, localizador_processo, data_do_dia, 
                    localizador_email, email_receiver, numero, permanent_url, Origem,datetime.now()))
                
                db_connection.commit()

    except Exception as err:
        logger.error(f"Erro ao inserir o email no banco de dados: {err}")

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

def validar_dados(data_inicio, data_fim, codigo,status):
    try:
        db_connection = get_db_connection()
        db_cursor = db_connection.cursor(dictionary=True)
        # Consulta para validar se há processo para a data
        query=""" 
                    SELECT p.Cod_escritorio, p.numero_processo, 
                        MAX(p.data_distribuicao) as data_distribuicao, 
                        p.orgao_julgador, p.tipo_processo, p.status, 
                        p.uf, p.sigla_sistema, MAX(p.instancia) as instancia, p.tribunal, 
                        p.ID_processo, MAX(p.LocatorDB) as LocatorDB, 
                        p.tipo_processo 
                    FROM apidistribuicao.processo AS p 
                    WHERE DATE(p.data_insercao) between  %s and %s """
        if status:
            if status == 'enviado':
                query+= "AND p.status = 'S' "
            if status == 'pendente':
                query += "AND p.status = 'P' "
        if not status:
            query += "AND p.status = 'S' "
        if codigo:
            query+= """AND p.Cod_escritorio = %s """
            
        query+= """ GROUP BY p.numero_processo, p.Cod_escritorio, p.orgao_julgador, p.tipo_processo, 
                            p.uf, p.sigla_sistema, p.tribunal,ID_processo;
                """
        if not codigo:
            db_cursor.execute(query, (data_inicio, data_fim))
        if codigo:
            db_cursor.execute(query, (data_inicio, data_fim,codigo))
            

        processes = db_cursor.fetchall()
        
        return processes
    except mysql.connector.Error as err:
        logger.error(f"erro ao validar dados {err}")
    except Exception as e:
        logger.error(f"erro ao validar dados {e}")


def formatar_data(data):
    if data:
        return data.strftime("%d/%m/%Y %H:%M:%S")
    return None

def historio_env():
    try:
        listnmes = []
        db_connection = get_db_connection()
        db_cursor = db_connection.cursor(dictionary=True)
        query = """SELECT 
                    cod_escritorio,
                    GROUP_CONCAT(ID_processo ORDER BY data_hora_envio SEPARATOR ', ') AS processos_enviados,
                    localizador,
                    origem,
                    MAX(data_hora_envio) AS ultima_data_envio
                FROM 
                    envio_emails
                GROUP BY 
                    cod_escritorio, localizador, data_hora_envio, origem
                ORDER BY
                    data_hora_envio DESC LIMIT 10;"""
        db_cursor.execute(query)
        dados = db_cursor.fetchall()

        # Mapeando registros com índices
        indexed_data = {i: registro for i, registro in enumerate(dados)}

        # Usando threading
        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(nome_cliente, registro['cod_escritorio']): index
                for index, registro in indexed_data.items()
            }

            for future in as_completed(futures):
                index = futures[future]
                try:
                    nome_do_cliente = future.result()
                    indexed_data[index]['nome_cliente'] = nome_do_cliente if nome_do_cliente else 'Cliente não encontrado'
                except Exception as e:
                    logger.error(f"Erro ao obter nome do cliente: {e}")
                    indexed_data[index]['nome_cliente'] = 'Erro ao obter cliente'
        for registro in indexed_data.values():
            registro['ultima_data_envio'] = formatar_data(registro['ultima_data_envio'])
        # Reconstruindo a lista na ordem original
        listnmes = [indexed_data[i] for i in sorted(indexed_data)]

        return listnmes

    except mysql.connector.Error as err:
        logger.error(f"Erro ao puxar historico de envio {err}")
    except Exception as e:
        logger.error(f"Erro ao puxar historico de envio {e}")


def pendentes_envio():
    try:
        listnmes = []
        db_connection = get_db_connection()
        db_cursor = db_connection.cursor(dictionary=True)
        query = """SELECT
                    p.Cod_escritorio,
                    c.Cliente_VSAP,    
                    COUNT(p.Cod_escritorio) AS Total
                FROM 
                    apidistribuicao.processo p
                    INNER JOIN apidistribuicao.clientes AS c ON p.Cod_escritorio = c.Cod_escritorio
                WHERE 
                    p.deleted = 0
                    AND p.status = 'P'
                GROUP BY
                    p.Cod_escritorio,
                    c.Cliente_VSAP
                ORDER BY
                    p.Cod_escritorio;"""
        db_cursor.execute(query)
        dados = db_cursor.fetchall()

        # Mapeando registros com índices
        indexed_data = {i: registro for i, registro in enumerate(dados)}

        # Usando threading
        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(nome_cliente, registro['Cod_escritorio']): index
                for index, registro in indexed_data.items()
            }

            for future in as_completed(futures):
                index = futures[future]
                try:
                    nome_do_cliente = future.result()
                    indexed_data[index]['nome_cliente'] = nome_do_cliente if nome_do_cliente else 'Cliente não encontrado'
                except Exception as e:
                    logger.error(f"Erro ao obter nome do cliente: {e}")
                    indexed_data[index]['nome_cliente'] = 'Erro ao obter cliente'

        # Reconstruindo a lista na ordem original
        listnmes = [indexed_data[i] for i in sorted(indexed_data)]

        return listnmes

    except mysql.connector.Error as err:
        logger.error(f"Erro ao puxar pendentes {err}")
    except Exception as e:
        logger.error(f"Erro ao puxar pendentes {e}")


def total_geral():
    data = datetime.now()
    ano = data.year
    mes = data.month
    data_inicio_obj = data.strftime("%Y-%m-%d")
    try:
        listnmes = []
        db_connection = get_db_connection()
        db_cursor = db_connection.cursor(dictionary=True)
        query = f"""SELECT
                        MAX(c.Cod_Escritorio) AS Codigo_VSAP,
                        c.Cliente_VSAP AS clienteVSAP,
                        COUNT(p.ID_processo) AS totalDistribuicoes
                    FROM
                        apidistribuicao.processo AS p
                        INNER JOIN apidistribuicao.clientes AS c ON p.Cod_escritorio = c.Cod_escritorio
                    WHERE
                        p.deleted = 0 AND DATE(p.data_insercao) between '{ano}-{mes}-01' and '{data_inicio_obj}'
                    GROUP BY 
                        Cliente_VSAP
                    ORDER BY  totalDistribuicoes DESC LIMIT 7;"""
        db_cursor.execute(query)
        dados = db_cursor.fetchall()

        # Mapeando registros com índices
        indexed_data = {i: registro for i, registro in enumerate(dados)}

        # Usando threading
        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(nome_cliente, registro['Codigo_VSAP']): index
                for index, registro in indexed_data.items()
            }

            for future in as_completed(futures):
                index = futures[future]
                try:
                    nome_do_cliente = future.result()
                    indexed_data[index]['nome_cliente'] = nome_do_cliente if nome_do_cliente else 'Cliente não encontrado'
                except Exception as e:
                    logger.error(f"Erro ao obter nome do cliente: {e}")
                    indexed_data[index]['nome_cliente'] = 'Erro ao obter cliente'

        # Reconstruindo a lista na ordem original
        listnmes = [indexed_data[i] for i in sorted(indexed_data)]

        return listnmes

    except mysql.connector.Error as err:
        logger.error(f"Erro ao puxar historico total {err}")
    except Exception as e:
        logger.error(f"Erro ao puxar historico total {e}")