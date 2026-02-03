from datetime import datetime
from errno import errorcode
import math
from sqlite3 import DatabaseError, OperationalError
import time

from flask import jsonify
from config.logger_config import logger
from config.db_conexão import get_db_connection
from app.apiLig import fetch_cliente_api_dashboard, fetch_cliente_api
import concurrent
import mysql.connector
from concurrent.futures import ThreadPoolExecutor, as_completed
from config.exeptions import ErroInterno,BancoError
from config.JWT_helper import get_random_cached_token
# Captura todos os dados do processo
def fetch_processes_and_clients(data_inicio, data_fim, codigo,numero_processo, status, origem,token):
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
                        p.tipo_processo,
                        p.data_insercao,
                        p.status,
                        p.modified_date
                    FROM apidistribuicao.processo AS p """

        if numero_processo:
            query+="WHERE p.numero_processo = %s"

        if data_inicio and data_fim:
            query += "WHERE DATE(p.data_insercao) between  %s and %s "

            query += f"AND p.status = '{status}' "            
        
        if not data_inicio and not data_fim and not codigo and not numero_processo:
                query += "WHERE p.status = 'P' "
        if codigo:
            query+= "AND p.Cod_escritorio = %s "
            
        query+= """GROUP BY p.numero_processo, p.Cod_escritorio, p.orgao_julgador, p.tipo_processo, 
                            p.uf, p.sigla_sistema, p.tribunal,ID_processo,data_insercao,status,modified_date;
                """
        if numero_processo:
            db_cursor.execute(query,(numero_processo,))

        if data_inicio and data_fim and codigo:
            db_cursor.execute(query, (data_inicio, data_fim, codigo)) 

        if data_inicio and data_fim and not codigo:
            db_cursor.execute(query, (data_inicio, data_fim))

        if not data_inicio and not data_fim and not codigo and not numero_processo:
            db_cursor.execute(query)

        processes = db_cursor.fetchall()

        if processes:
        # Pré-carrega autores, réus e links para todos os processos
            autor_dict = fetch_autores_reus_links("autor", processes)
            reu_dict = fetch_autores_reus_links("reu", processes)
            links_dict = fetch_autores_reus_links("links", processes)
            email_enviado = fetch_autores_reus_links("localizador",processes)
            Log_erro = fetch_autores_reus_links("log_erro", processes)

        #utiliza o multithreds para otimizar o processamento de dados
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for process in processes:
                futures.append(executor.submit(process_result, process, clientes_data, autor_dict, reu_dict, links_dict,email_enviado,Log_erro,token))

        # Wait for all futures to finish
        concurrent.futures.wait(futures)

    except mysql.connector.Error as err:
        logger.error(f"Erro ao executar a consulta: {err}")
        raise BancoError(f"Falha no banco: {err}")
    except Exception as e:
        raise ErroInterno(f"Erro inesperado: {err}")
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
                elif tipo == "localizador":
                    query= """SELECT 
                        ID_processo,
                        localizador,
                        link_s3,
                        total,
                        email_envio,
                        numero_envio,
                        Origem,
                        data_hora_envio
                    FROM apidistribuicao.envio_emails
                    WHERE ID_processo IN (%s)"""
                elif tipo == "log_erro":
                    query = """SELECT Id_LogErro,ID_processo,motivo,created_date 
                    FROM log_erro WHERE ID_processo IN (%s)"""
                
                # Converter a lista de IDs para um formato que possa ser usado no SQL
                format_strings = ','.join(['%s'] * len(ids))
                query = query % format_strings  # Substituir o %s pelo número correto de %s
                
                db_cursor.execute(query, tuple(ids))  # Passar a lista de IDs como parâmetros
                results = db_cursor.fetchall()
                
                for row in results:
                    process_id = row['ID_processo']
                    if process_id not in data_dict:
                        data_dict[process_id] = []
                    if 'data_hora_envio'  in row and row['data_hora_envio']:
                        row['data_hora_envio'] = formatar_data(row['data_hora_envio'])
                    if 'created_date' in row and row['created_date']:
                        row['created_date'] = formatar_data(row['created_date'])    
                    data_dict[process_id].append(row)
    except Exception as err:
        logger.error(f"Erro ao carregar {tipo}: {err}")
        raise ErroInterno(f"Erro inesperado: {err}")

    
    return data_dict

def process_result(process, clientes_data, autor_dict, reu_dict, links_dict,email_enviado,Log_erro,token):
    clienteVSAP, Office_id, office_status = fetch_cliente_api(process['Cod_escritorio'],token)
    
    if not clienteVSAP and not Office_id and not office_status:
        clienteVSAP, Office_id, office_status = "[Cliente não cadastrado]", None, None

    num_processo = process['numero_processo']
    data_distribuicao = process['data_distribuicao'].strftime('%d/%m/%Y')
    tribunal = process['tribunal']
    uf = process['uf']
    instancia = process['instancia']
    comarca = process['sigla_sistema']
    modified_date = process['modified_date']
    status = process['status']
    data_insercao = formatar_data(process["data_insercao"]) if process["data_insercao"] else None

    # Pega os autores, réus e links dos dicionários pré-carregados
    autor_list = autor_dict.get(process['ID_processo'], [{"nomeAutor": "[Nenhum dado disponível]"}])
    reu_list = reu_dict.get(process['ID_processo'], [{"nomeReu": "[Nenhum dado disponível]"}])
    links_list = links_dict.get(process['ID_processo'], [])
    envio_emailList = email_enviado.get(process['ID_processo'], [])
    Log_erroList = Log_erro.get(process['ID_processo'], [])

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
        'cliente_status': office_status,
        'office_id': Office_id,
        'modified_date': modified_date,
        'status': status,
        'data_insercao': data_insercao,
        'email_enviado': envio_emailList,
        'Log_erro': Log_erroList
    })


def fetch_email_locator(localizador):
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor(dictionary=True) as db_cursor:
                query = """
                    SELECT 
                        localizador,
                        link_s3,
                        total,
                        email_envio,
                        numero_envio,
                        Origem,
                        data_hora_envio
                    FROM apidistribuicao.envio_emails
                    WHERE localizador_processo = %s
                """
                db_cursor.execute(query, tuple(localizador))
                results = db_cursor.fetchall()
                
                # Transformar os resultados em uma lista de dicionários formatados
                formatted_results = [
                    {
                        "localizador": row["localizador"],
                        "link_s3": row["link_s3"],
                        "total": row["total"],
                        "email_envio": row["email_envio"],
                        "numero_envio": row["numero_envio"],
                        "origem": row["Origem"],
                        "data_hora_envio": formatar_data(row["data_hora_envio"]) if row["data_hora_envio"] else None,
                    }
                    for row in results
                ]
                
                return formatted_results

    except Exception as err:
        logger.error(f"Erro na consulta do banco envio_email: {err}")
        raise ErroInterno(f"Erro inesperado: {err}")
    
# Puxa todos os dados necessários para envio de email e WhatsApp (SMTP/URL API)
def fetch_companies():
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor() as db_cursor:
                db_cursor.execute("""
                    SELECT id_companies,ID_lig, url_Sirius, sirius_Token, aws_s3_access_key, aws_s3_secret_key, bucket_s3,bucket_S3_resumo,
                        region,smtp_host, smtp_port, smtp_username, smtp_password, smtp_from_email, smtp_from_name,
                        smtp_reply_to, smtp_cc_emails, smtp_bcc_emails, smtp_envio_test, url_thumbnail_whatsapp, url_thumbnail 
                    FROM companies
                """)
                config = db_cursor.fetchone()
                
                return config

    except Exception as err:
        logger.error(f"Erro na consulta do banco companies: {err}")
        raise ErroInterno(f"Erro inesperado: {err}")
# Atualiza o status do processo enviado
def status_processo(status,processo_id):
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor() as db_cursor:
                db_cursor.execute("UPDATE processo SET status = %s, modified_date = %s WHERE ID_processo = %s", (status,datetime.now(),processo_id))
                db_connection.commit()
    except Exception as err:
        logger.error(f"Erro ao atulaizar status do email para {status}: {err}")
        raise ErroInterno(f"Erro inesperado: {err}")

# Insere no banco o email enviado
def status_envio(processo_id = int, numero_processo= str, cod_escritorio = int, localizador_processo= str,
                data_do_dia= str, localizador_email= str, email_receiver= str,menssagem = str,
                numero = str, permanent_url = str, Origem = str, total_processos = int,status = str,subject =str):

    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor() as db_cursor:
                db_cursor.execute("""
                    INSERT INTO envio_emails (ID_processo, numero_processo, cod_escritorio, localizador_processo,
                                            data_envio, localizador,subject, email_envio,menssagem ,numero_envio, link_s3, Origem, total,data_hora_envio,status)
                    VALUES (%s, %s, %s, %s, %s, %s,%s, %s,%s ,%s, %s,%s, %s,%s,%s)
                """, (processo_id, numero_processo, cod_escritorio, localizador_processo, data_do_dia, 
                    localizador_email,subject ,email_receiver, menssagem,numero, permanent_url, Origem,total_processos,datetime.now(),status))
                
                db_connection.commit()

    except mysql.connector.Error as err:
        logger.error(f"Erro ao inserir o email no banco de dados: {err}")
        raise BancoError(f"Falha no banco: {err}")

    except Exception as err:
        logger.error(f"Erro ao inserir o email no banco de dados: {err}")
        raise ErroInterno(f"Erro inesperado: {err}")


def validar_dados(data_inicio=None, data_fim=None, codigo=None, status=None):
    try:
        db_connection = get_db_connection()
        db_cursor = db_connection.cursor(dictionary=True)

        # Query base
        query = """ 
            SELECT p.Cod_escritorio, p.numero_processo, 
                   MAX(p.data_distribuicao) as data_distribuicao, 
                   p.orgao_julgador, p.tipo_processo, p.status, 
                   p.uf, p.sigla_sistema, MAX(p.instancia) as instancia, 
                   p.tribunal, p.ID_processo, MAX(p.LocatorDB) as LocatorDB, 
                   p.tipo_processo 
            FROM apidistribuicao.processo AS p 
            WHERE p.deleted = 0
        """

        params = []

        # Filtros opcionais
        if data_inicio and data_fim:
            query += " AND DATE(p.data_insercao) BETWEEN %s AND %s "
            params.extend([data_inicio, data_fim])

        if status:
            query += " AND p.status = %s "
            params.append(status)
        else:
            query += " AND p.status = 'S' "

        if codigo:
            query += " AND p.Cod_escritorio = %s "
            params.append(codigo)

        query += """ 
            GROUP BY p.numero_processo, p.Cod_escritorio, 
                     p.orgao_julgador, p.tipo_processo, 
                     p.uf, p.sigla_sistema, p.tribunal, 
                     ID_processo;
        """

        # Execução segura
        db_cursor.execute(query, tuple(params))
        resultados = db_cursor.fetchall()

        return resultados
    except mysql.connector.Error as err:
        logger.error(f"erro ao validar dados {err}")
        raise BancoError(f"Falha no banco: {err}")
    except Exception as e:
        logger.error(f"erro ao validar dados {e}")
        raise ErroInterno(f"Erro inesperado: {e}")


def formatar_data(data):
    if data:
        return data.strftime("%d/%m/%Y %H:%M:%S")
    return None

def historio_env(token, page=1, per_page=10):
    try:
        listnmes = []
        offset = (page - 1) * per_page

        db_connection = get_db_connection()
        db_cursor = db_connection.cursor(dictionary=True)

        # Consulta para contar o total de registros (sem paginação)
        count_query = """
            SELECT COUNT(*) as total
            FROM (
                SELECT 1
                FROM apidistribuicao.envio_emails e
                GROUP BY e.cod_escritorio, e.localizador, e.origem, e.total, e.status
            ) AS subquery;
        """
        db_cursor.execute(count_query)
        total_registros = db_cursor.fetchone()['total']

        # Consulta principal com paginação
        query = f"""
            SELECT 
                e.cod_escritorio,
                e.localizador,
                e.origem,
                e.total,
                MAX(e.data_hora_envio) AS ultima_data_envio,
                e.status
            FROM 
                apidistribuicao.envio_emails e
            GROUP BY 
                e.cod_escritorio, e.localizador, e.origem, e.total, e.status
            ORDER BY
                ultima_data_envio DESC
            LIMIT {per_page} OFFSET {offset};
        """
        db_cursor.execute(query)
        dados = db_cursor.fetchall()

        indexed_data = {i: registro for i, registro in enumerate(dados)}

        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(fetch_cliente_api_dashboard, registro['cod_escritorio'], token): index
                for index, registro in indexed_data.items()
            }

            for future in as_completed(futures):
                index = futures[future]
                try:
                    nome_do_cliente = future.result()
                    indexed_data[index]['nome_cliente'] = nome_do_cliente if nome_do_cliente else 'Cliente não cadastrado'
                except concurrent.futures.TimeoutError:
                    logger.error(f"Timeout ao obter nome do cliente para o índice {index}.")
                    indexed_data[index]['nome_cliente'] = 'Timeout ao obter cliente'
                except concurrent.futures.CancelledError:
                    logger.error(f"Operação cancelada ao obter nome do cliente para o índice {index}.")
                    indexed_data[index]['nome_cliente'] = 'Operação cancelada'
                except Exception as e:
                    logger.error(f"Erro ao obter nome do cliente: {e}")
                    indexed_data[index]['nome_cliente'] = 'Erro ao obter cliente'

        for registro in indexed_data.values():
            registro['ultima_data_envio'] = formatar_data(registro['ultima_data_envio'])

        listnmes = [indexed_data[i] for i in sorted(indexed_data)]

        return listnmes, total_registros

    except mysql.connector.Error as err:
        logger.error(f"Erro ao puxar historico de envio {err}")
        raise BancoError(f"Falha no banco: {err}")
    except Exception as e:
        logger.error(f"Erro ao puxar historico de envio {e}")
        raise ErroInterno(f"Erro inesperado: {e}")


def pendentes_envio(token):
    try:
        listnmes = []
        db_connection = get_db_connection()
        db_cursor = db_connection.cursor(dictionary=True)
        query = """SELECT
                    p.Cod_escritorio,
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
                executor.submit(fetch_cliente_api_dashboard, registro['Cod_escritorio'], token): index
                for index, registro in indexed_data.items()
            }

            for future in as_completed(futures):
                index = futures[future]
                try:
                    nome_do_cliente = future.result()
                    indexed_data[index]['nome_cliente'] = nome_do_cliente if nome_do_cliente else 'Cliente não cadastrado'
                except Exception as e:
                    logger.error(f"Erro ao obter nome do cliente: {e}")
                    indexed_data[index]['nome_cliente'] = 'Erro ao obter cliente'

        # Reconstruindo a lista na ordem original
        listnmes = [indexed_data[i] for i in sorted(indexed_data)]

        return listnmes

    except mysql.connector.Error as err:
        logger.error(f"Erro ao puxar pendentes {err}")
        raise BancoError(f"Falha no banco: {err}")
    except Exception as e:
        logger.error(f"Erro ao puxar pendentes {e}")
        raise ErroInterno(f"Erro inesperado: {e}")


def total_geral(token, start_date=None, end_date=None):
    data = datetime.now()
    ano = data.year
    mes = data.month
    data_inicio_obj = data.strftime("%Y-%m-%d")
    try:
        listnmes = []
        db_connection = get_db_connection()
        db_cursor = db_connection.cursor(dictionary=True)
        query = f"""SELECT
                        p.Cod_Escritorio AS Codigo_VSAP,
                        COUNT(p.ID_processo) AS totalDistribuicoes
                    FROM
                        apidistribuicao.processo AS p
                    WHERE
                        p.deleted = 0
                    """
        
        # Condição para a data atual (sem filtro de data)
        if not start_date and not end_date:
            query += f" AND DATE(p.data_insercao) BETWEEN '{ano}-{mes}-01' AND '{data_inicio_obj}' "
        
        # Condição para o filtro de data especificado (com start_date e end_date)
        if start_date and end_date:
            query += f" AND DATE(p.data_insercao) BETWEEN '{start_date}' AND '{end_date}' "
        
        query += """ GROUP BY 
                        Codigo_VSAP 
                    ORDER BY totalDistribuicoes DESC;"""
        
        db_cursor.execute(query)
        dados = db_cursor.fetchall()

        total_geral_distribuicoes = sum([registro['totalDistribuicoes'] for registro in dados if 'totalDistribuicoes' in registro])

        # Mapeando registros com índices
        indexed_data = {i: registro for i, registro in enumerate(dados)}

        # Usando threading
        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(fetch_cliente_api_dashboard, registro['Codigo_VSAP'],token): index
                for index, registro in indexed_data.items()
            }

            for future in as_completed(futures):
                index = futures[future]
                try:
                    nome_do_cliente = future.result()
                    indexed_data[index]['nome_cliente'] = nome_do_cliente if nome_do_cliente else 'Cliente não cadastrado'
                except Exception as e:
                    logger.error(f"Erro ao obter nome do cliente: {e}")
                    indexed_data[index]['nome_cliente'] = 'Erro ao obter cliente'

        # Reconstruindo a lista na ordem original
        listnmes = [indexed_data[i] for i in sorted(indexed_data)]

        resultado = {
            "detalhes": listnmes,
            "total_distribuicoes": total_geral_distribuicoes
        }
        return resultado

    except mysql.connector.Error as err:
        logger.error(f"Erro ao puxar historico total {err}")
        raise BancoError(f"Falha no banco: {err}")
    except Exception as e:
        logger.error(f"Erro ao puxar historico total {e}")
        raise ErroInterno(f"Erro inesperado: {e}")
        


def log_error(ID_processo,cod_escritorio,numero_processo,motivo,localizador):
    try:
        db_connection = get_db_connection()
        db_cursor = db_connection.cursor(dictionary=True)
        query = """insert into log_erro (ID_processo, cod_escritorio, numero_processo, motivo, created_date,modified_date,localizador)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)"""
        db_cursor.execute(query, (ID_processo,cod_escritorio,numero_processo,motivo, datetime.now(), datetime.now(),localizador))
        db_connection.commit()

    except mysql.connector.Error as err:
        logger.error(f"Erro ao Inserir log de erro {err}")
        raise BancoError(f"Falha no banco: {err}")
    except Exception as e:
        logger.error(f"Erro ao Inserir log de erro {e}")  
        raise ErroInterno(f"Erro inesperado: {e}")    

def numeros_processos_pendentes(cod_escritorio):
    try:
        processos = []
        db_connection = get_db_connection()
        db_cursor = db_connection.cursor(dictionary=True)
        query = """SELECT
                    p.numero_processo
                FROM 
                    apidistribuicao.processo p
                WHERE 
                    p.deleted = 0
                    AND p.Cod_escritorio = %s
                    AND p.status = 'P'
                GROUP BY
                    p.numero_processo
                ORDER BY
                    p.Cod_escritorio;"""
        db_cursor.execute(query, (cod_escritorio,))
        dados = db_cursor.fetchall()
        for item in dados:
            processos.append(item['numero_processo'])

        return processos

    except mysql.connector.Error as err:
        logger.error(f"Erro ao puxar pendentes {err}")
        raise BancoError(f"Falha no banco: {err}")
    except Exception as e:
        logger.error(f"Erro ao puxar pendentes {e}")
        raise ErroInterno(f"Erro inesperado: {e}")



def fetchLog(localizador):
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor(dictionary=True) as db_cursor:
                query = """
                    SELECT 
                        ID_processo,
                        numero_processo,
                        email_envio,
                        menssagem,
                        numero_envio,
                        link_s3,
                        data_hora_envio
                    FROM envio_emails
                    WHERE localizador =%s
                """
                db_cursor.execute(query, (localizador,))
                results = db_cursor.fetchall()

                if not results:
                    return {}

                # Pegamos motivo e data do primeiro registro (são iguais para todos)
                emails = results[0]["email_envio"]
                menssagem = results[0]["menssagem"]
                numero_envio = results[0]["numero_envio"]
                link_s3 = results[0]["link_s3"]
                created_date = formatar_data(results[0]["data_hora_envio"]) if results[0]["data_hora_envio"] else None

                processos = [
                    {
                        "ID_processo": row["ID_processo"],
                        "numero_processo": row["numero_processo"]
                    }
                    for row in results
                ]

                return {
                    "menssagem": menssagem,
                    "email_envio": emails,
                    "numero_envio": numero_envio,
                    "hora_envio": created_date,
                    "link_s3": link_s3,
                    "processos": processos
                }

    except Exception as err:
        logger.error(f"Erro na consulta do banco log_erro: {err}")
        raise ErroInterno(f"Erro inesperado: {err}")

def cadastrar_cliente(cod_escritorio):
    db_connection = get_db_connection()
    db_cursor = db_connection.cursor(dictionary=True)
    token = get_random_cached_token(Refresh=True)
    try:
        # verifica se tem cliente
        db_cursor.execute("""SELECT * from clientes where Cod_escritorio = %s""",(cod_escritorio,))
        cliente = db_cursor.fetchone()
        fetch_cliente = fetch_cliente_api(cod_escritorio,token)
        cliente_nome = fetch_cliente[0]

        if cliente:
            db_cursor.execute(
                """UPDATE clientes SET recebe_resumo = true where Cod_escritorio = %s""",
                (cod_escritorio,)
            )
            db_connection.commit()
            if cliente['Cliente_VSAP'] == "ALTERAR CLIENTE":
                db_cursor.execute(
                    """UPDATE clientes SET Cliente_VSAP = %s where Cod_escritorio = %s""",
                    (cliente_nome,cod_escritorio)
                )
                db_connection.commit()
            return {"nome": cliente_nome, "status": "existente"}

        else:
            db_cursor.execute(
                """INSERT INTO clientes(Cod_escritorio,Cliente_VSAP,status,recebe_resumo)
                   VALUES (%s,%s,"L",true)""",
                (cod_escritorio,cliente_nome)
            )
            db_connection.commit()
            return {"nome": cliente_nome, "status": "novo"}

    except mysql.connector.Error as err:
        logger.error(f"erro na consulta do banco clientes: {err}")
        raise BancoError(f"Falha no banco: {err}")
    except Exception as e:
        logger.error(f"erro na consulta do banco clientes: {e}")
        raise ErroInterno(f"Erro inesperado: {e}")


BATCH_SIZE = 100
RETRIES = 3
RETRY_SLEEP_BASE = 1.5  # segundos

def status_envio_resumo_bulk(lista_registros):
    """
    lista_registros contém tuplas:
    (cod_escr, data_envio, local_email, subj, email, msg, link, origem, total_proc, status, arquivo_blob)
    """
    # monta aqui a lista com datetime.now() ANTES do status, como seu SQL pede
    lista_com_data = [
        (
            cod_escr, data_envio, local_email,
            subj, email, msg, link, origem, total_proc,
            datetime.now(), status, arquivo_blob
        )
        for (cod_escr, data_envio, local_email,
             subj, email, msg, link, origem, total_proc, status, arquivo_blob)
        in lista_registros
    ]

    sql = ("""
        INSERT INTO publicacao_envio_resumo (
            cod_escritorio,
            data_envio, localizador_email, subject, email_envio, menssagem,
            link_s3, Origem, total, data_hora_envio, status, arquivo_base64
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """)

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        # cursor preparado = protocolo binário (melhor p/ BLOBs grandes)
        cur = conn.cursor(prepared=True)
        total = len(lista_com_data)
        for start in range(0, total, BATCH_SIZE):
            chunk = lista_com_data[start:start+BATCH_SIZE]

            # retries para quedas transitórias
            for attempt in range(1, RETRIES+1):
                try:
                    cur.executemany(sql, chunk)
                    conn.commit()
                    break
                except OperationalError as e:
                    # 2006 = MySQL server has gone away, 2013 = Lost connection during query
                    if getattr(e, "errno", None) in (2006, 2013) or e.args and e.args[0] in (2006, 2013):
                        conn.rollback()
                        # reconectar e reconfigurar sessão
                        time.sleep(RETRY_SLEEP_BASE * attempt)
                        if cur:
                            cur.close()
                        if conn:
                            conn.close()
                        conn = get_db_connection()
                        cur = conn.cursor(prepared=True)
                        continue
                    else:
                        raise
                except DatabaseError:
                    conn.rollback()
                    raise

    except Exception as err:
        logger.error(f"Erro ao inserir emails no banco de dados: {err}")
        raise ErroInterno(f"Erro inesperado: {err}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def puxarClientesResumo():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""SELECT * FROM clientes WHERE recebe_resumo = true and status = 'L'""")
        clientes = cursor.fetchall()

        return clientes

    except mysql.connector.Error as err:
        logger.error(f"Erro ao puxar pendentes {err}")
        raise BancoError(f"Falha no banco: {err}")
    except Exception as e:
        logger.error(f"Erro ao puxar pendentes {e}")
        raise ErroInterno(f"Erro inesperado: {e}")
    


def historio_env_resumo(page=1, per_page=10):
    try:
        listnmes = []
        offset = (page - 1) * per_page

        db_connection = get_db_connection()
        db_cursor = db_connection.cursor(dictionary=True)

        # Consulta para contar o total de registros (sem paginação)
        count_query = """
            SELECT COUNT(*) as total
            FROM (
                SELECT 1
                FROM publicacao_envio_resumo e
                GROUP BY e.cod_escritorio, e.localizador_email, e.Origem, e.total, e.status
            ) AS subquery;
        """
        db_cursor.execute(count_query)
        total_registros = db_cursor.fetchone()['total']

        # Consulta principal com paginação
        query = f"""
            SELECT 
                e.cod_escritorio,
                e.localizador_email,
                c.Cliente_VSAP,
                e.Origem,
                e.total,
                MAX(e.data_hora_envio) AS ultima_data_envio,
                e.status
            FROM 
                apidistribuicao.publicacao_envio_resumo e
                join apidistribuicao.clientes as c on c.cod_escritorio = e.cod_escritorio
            GROUP BY 
                e.cod_escritorio, e.localizador_email, e.Origem, e.total, e.status,c.Cliente_VSAP
            ORDER BY
                ultima_data_envio DESC
            LIMIT {per_page} OFFSET {offset};
        """
        db_cursor.execute(query)
        dados = db_cursor.fetchall()

        indexed_data = {i: registro for i, registro in enumerate(dados)}

        for registro in indexed_data.values():
            registro['ultima_data_envio'] = formatar_data(registro['ultima_data_envio'])

        listnmes = [indexed_data[i] for i in sorted(indexed_data)]

        return listnmes, total_registros

    except mysql.connector.Error as err:
        logger.error(f"Erro ao puxar historico de envio {err}")
        raise BancoError(f"Falha no banco: {err}")
    except Exception as e:
        logger.error(f"Erro ao puxar historico de envio {e}")
        raise ErroInterno(f"Erro inesperado: {e}")
    
def fetch_anexo_resumo(localizador):
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor(dictionary=True) as db_cursor:
                query = """
                    SELECT 
                        arquivo_base64
                    FROM apidistribuicao.publicacao_envio_resumo
                    WHERE localizador_email = %s
                    LIMIT 1
                """
                db_cursor.execute(query, (localizador,))
                result = db_cursor.fetchone()
                
                if result and result['arquivo_base64']:
                    return result['arquivo_base64']
                else:
                    return None

    except mysql.connector.Error as err:
        logger.error(f"Erro ao puxar fetch_anexo_resumo {err}")
        raise BancoError(f"Falha no banco: {err}")
    except Exception as e:
        logger.error(f"Erro ao puxar fetch_anexo_resumo {e}")
        raise ErroInterno(f"Erro inesperado: {e}")
    
def fetch_log_resumo(localizador):
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor(dictionary=True) as db_cursor:
                query = """
                    SELECT 
                        email_envio,
                        menssagem,
                        link_s3,
                        localizador_email,
                        data_hora_envio
                    FROM publicacao_envio_resumo
                    WHERE localizador_email =%s
                """
                db_cursor.execute(query, (localizador,))
                results = db_cursor.fetchall()

                if not results:
                    return {}

                # Pegamos menssagem, email_envio, numero_envio, link_s3 e data_hora_envio do primeiro registro (são iguais para todos)
                emails = results[0]["email_envio"]
                menssagem = results[0]["menssagem"]
                link_s3 = results[0]["link_s3"]
                localizador_email = results[0]["localizador_email"]
                created_date = formatar_data(results[0]["data_hora_envio"]) if results[0]["data_hora_envio"] else None


                return {
                    "menssagem": menssagem,
                    "email_envio": emails,
                    "hora_envio": created_date,
                    "link_s3": link_s3,
                    "localizador_email": localizador_email,
                }

    except Exception as err:
        logger.error(f"Erro na consulta do banco fetch_log_resumo: {err}")
        raise ErroInterno(f"Erro inesperado: {err}")
    

def cadastrar_cliente_cobranca(codigo_escritorio: int, emails_cobranca):
    """
    Novo comportamento (com tabela de e-mails separada):
      - Se o cliente (Cod_escritorio) não existe -> cria cliente em clientes_cobranca e insere TODOS os e-mails em emails_clientes_cobranca.
      - Se já existe -> insere/reativa APENAS os e-mails novos (ou que estavam deleted=1).
    """
    db = get_db_connection()
    cur = db.cursor(dictionary=True)

    emails_norm = {str(e).strip().lower() for e in (emails_cobranca or []) if str(e).strip()}
    if not emails_norm:
        return {"message": "Lista de e-mails vazia após normalização.", "status": "error"}, 400

    now = datetime.now()

    try:
        try:
            db.autocommit = False
        except Exception:
            pass

        # 1) Obter (ou criar) o cliente por Cod_escritorio
        cur.execute("""
            SELECT id_cliente_cobranca, cliente, deleted, is_active
            FROM clientes_cobranca
            WHERE Cod_escritorio = %s
            LIMIT 1
        """, (codigo_escritorio,))
        row = cur.fetchone()

        if not row:
            # valida escritório na API externa
            nome_escritorio, office_id, status_escritorio = fetch_cliente_api(
                codigo_escritorio,
                get_random_cached_token(Refresh=True)
            )
            if status_escritorio != "L":
                return {"message": "Escritório não está liberado para cadastro", "status": "error"}, 400

            # cria cliente
            cur.execute("""
                INSERT INTO clientes_cobranca
                    (Cod_escritorio, cliente, is_active, deleted, created_at)
                VALUES (%s, %s, 1, 0, %s)
            """, (codigo_escritorio, nome_escritorio, now))
            id_cliente = cur.lastrowid
            cliente_nome = nome_escritorio
            status_inicial = "novo"
        else:
            id_cliente = row["id_cliente_cobranca"]
            cliente_nome = row["cliente"]
            # Se estava deletado/inativo, reativa de forma transparente
            if row["deleted"] or not row["is_active"]:
                cur.execute("""
                    UPDATE clientes_cobranca
                    SET deleted=0, is_active=1, modified_at=%s
                    WHERE id_cliente_cobranca=%s
                """, (now, id_cliente))
            status_inicial = "atualizado"

        inserted = 0
        reactivated = 0
        skipped = 0

        # 2) Buscar e-mails atuais (ativos e deletados)
        cur.execute("""
            SELECT LOWER(email) AS email, deleted
            FROM emails_clientes_cobranca
            WHERE id_cliente_cobranca = %s
        """, (id_cliente,))
        rows = cur.fetchall() or []
        existentes_ativos   = {r["email"] for r in rows if not r["deleted"]}
        existentes_deletado = {r["email"] for r in rows if r["deleted"]}

        for email in emails_norm:
            if email in existentes_ativos:
                skipped += 1
                continue
            if email in existentes_deletado:
                # reativa se já existia como deletado
                cur.execute("""
                    UPDATE emails_clientes_cobranca
                    SET deleted=0, modified_at=%s
                    WHERE id_cliente_cobranca=%s AND LOWER(email)=%s
                """, (now, id_cliente, email))
                reactivated += (cur.rowcount or 0)
            else:
                try:
                    cur.execute("""
                        INSERT INTO emails_clientes_cobranca
                            (id_cliente_cobranca, email, created_at, deleted)
                        VALUES (%s, %s, %s, 0)
                    """, (id_cliente, email, now))
                    inserted += 1
                except mysql.connector.IntegrityError as ie:
                    if ie.errno == errorcode.ER_DUP_ENTRY:
                        skipped += 1
                    else:
                        raise

        db.commit()

        # 3) total de e-mails ativos
        cur.execute("""
            SELECT COUNT(*) AS total_emails
            FROM emails_clientes_cobranca
            WHERE id_cliente_cobranca = %s AND deleted = 0
        """, (id_cliente,))
        total_emails = cur.fetchone()["total_emails"]

        status = status_inicial
        if inserted == 0 and reactivated == 0:
            status = "sem_novos"

        return {
            "message": f"E-mails inseridos: {inserted}, reativados: {reactivated}, ignorados: {skipped}",
            "status": status,
            "inserted": inserted,
            "reactivated": reactivated,
            "skipped": skipped,
            "total_emails": total_emails,
            "cliente": cliente_nome,
            "Cod_escritorio": codigo_escritorio,
            "id_cliente_cobranca": id_cliente
        }, (201 if inserted or reactivated else 200)

    except mysql.connector.Error as err:
        try:
            if getattr(db, "in_transaction", False):
                db.rollback()
        except Exception:
            pass
        logger.error(f"erro na consulta do banco clientes/emails_cobranca: {err}")
        raise BancoError(f"Falha no banco: {err}")

    except Exception as e:
        try:
            if getattr(db, "in_transaction", False):
                db.rollback()
        except Exception:
            pass
        logger.error(f"erro na consulta do banco clientes/emails_cobranca: {e}")
        raise ErroInterno(f"Erro inesperado: {e}")

    finally:
        try: cur.close()
        except Exception: pass
        try: db.close()
        except Exception: pass


def fetch_cliente_cobranca(cod_escritorio: int):
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor(dictionary=True) as cur:
                cur.execute("""
                    SELECT
                        c.Cod_escritorio,
                        c.cliente,
                        GROUP_CONCAT(e.email ORDER BY e.email SEPARATOR ', ') AS emails_cobranca
                    FROM clientes_cobranca c
                    LEFT JOIN emails_clientes_cobranca e
                      ON e.id_cliente_cobranca = c.id_cliente_cobranca
                     AND e.deleted = 0
                    WHERE c.Cod_escritorio = %s
                      AND c.deleted = 0
                    GROUP BY c.Cod_escritorio, c.cliente
                """, (cod_escritorio,))
                return cur.fetchone()
    except mysql.connector.Error as err:
        logger.error(f"Erro ao puxar fetch_cliente_cobranca {err}")
        raise BancoError(f"Falha no banco: {err}")
    except Exception as e:
        logger.error(f"Erro ao puxar fetch_cliente_cobranca {e}")
        raise ErroInterno(f"Erro inesperado: {e}")


def status_envio_cobranca(cod_escritorio:int,email_receiver:str,subject:str,content:str,status:str,menssagem:str,autor:str):
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor() as db_cursor:
                db_cursor.execute("""
                    INSERT INTO cobranca_emails (cod_escritorio, email_envio, subject, content, status, menssagem, autor, data_hora_envio)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (cod_escritorio, email_receiver, subject, content, status, menssagem, autor, datetime.now()))
                
                db_connection.commit()

    except mysql.connector.Error as err:
        logger.error(f"Erro ao inserir o email de cobrança no banco de dados: {err}")
        raise BancoError(f"Falha no banco: {err}")

    except Exception as err:
        logger.error(f"Erro ao inserir o email de cobrança no banco de dados: {err}")
        raise ErroInterno(f"Erro inesperado: {err}")



# Colunas permitidas para ordenação
SORTABLE_COLS = {
    "Cod_escritorio": "c.Cod_escritorio",
    "cliente": "c.cliente",
    "total_emails": "total_emails",  # campo derivado
}

def listar_clientes_cobranca(
    page: int = 1,
    per_page: int = 20,
    q: str | None = None,
    sort: str = "cliente",
    order: str = "asc",
):
    """
    Lista clientes (clientes_cobranca) e conta e-mails ativos (emails_clientes_cobranca.deleted=0).
    Busca opcional em Cod_escritorio, cliente e e-mail (via EXISTS).
    """
    try:
        page = max(1, int(page or 1))
        per_page = max(1, min(int(per_page or 20), 100))
        order = "desc" if (order or "asc").lower() == "desc" else "asc"

        sort_col = SORTABLE_COLS.get(sort or "cliente", "c.cliente")

        where = ["c.deleted = 0"]
        params = []

        if q:
            like = f"%{q.strip()}%"
            where.append("("
                         "CAST(c.Cod_escritorio AS CHAR) LIKE %s OR "
                         "LOWER(c.cliente) LIKE LOWER(%s) OR "
                         "EXISTS (SELECT 1 FROM emails_clientes_cobranca e"
                         "        WHERE e.id_cliente_cobranca = c.id_cliente_cobranca"
                         "          AND e.deleted = 0"
                         "          AND LOWER(e.email) LIKE LOWER(%s))"
                         ")")
            params.extend([like, like, like])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        # total de clientes
        count_sql = f"""
            SELECT COUNT(*) AS total_clientes
            FROM clientes_cobranca c
            {where_sql}
        """

        # dados da página (com total_emails por cliente)
        data_sql = f"""
            SELECT
                c.Cod_escritorio,
                c.cliente,
                (
                  SELECT COUNT(*)
                  FROM emails_clientes_cobranca e
                  WHERE e.id_cliente_cobranca = c.id_cliente_cobranca
                    AND e.deleted = 0
                ) AS total_emails
            FROM clientes_cobranca c
            {where_sql}
            ORDER BY {sort_col} {order}
            LIMIT %s OFFSET %s
        """

        offset = (page - 1) * per_page

        with get_db_connection() as db:
            with db.cursor(dictionary=True) as cur:
                cur.execute(count_sql, params)
                row = cur.fetchone()
                total = int(row["total_clientes"] if row and row.get("total_clientes") is not None else 0)

                cur.execute(data_sql, params + [per_page, offset])
                rows = cur.fetchall() or []

        items = [{
            "Cod_escritorio": r["Cod_escritorio"],
            "cliente": r["cliente"],
            "total_emails": r["total_emails"] or 0,
            "emails_cobranca": fetch_emails_cobranca(r["Cod_escritorio"])["emails"] if r["total_emails"] else []
        } for r in rows]

        total_pages = max(1, math.ceil(total / per_page)) if total else 1

        return {
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        }

    except mysql.connector.Error as err:
        logger.error(f"Erro ao paginar clientes_cobranca: {err}")
        raise BancoError(f"Falha no banco: {err}")
    except Exception as e:
        logger.error(f"Erro inesperado ao paginar clientes_cobranca: {e}")
        raise ErroInterno(f"Erro inesperado: {e}")



def remover_emails_cobranca(
    codigo_escritorio: int,
    *,
    id_email: int | None = None,
    ids_email: list[int] | tuple[int, ...] | None = None,
    email: str | None = None,
    emails: list[str] | tuple[str, ...] | None = None,
):
    """
    Soft delete de e-mails de cobrança.
    Prioridade:
      1) ids (id_email ou ids_email)
      2) emails (email único ou lista)
    Retorna (dict, status_code).
    """
    db = get_db_connection()
    cur = db.cursor(dictionary=True)
    now = datetime.now()

    # ----------------- Normalização de entrada -----------------
    ids_norm: set[int] = set()
    emails_norm: set[str] = set()

    if id_email is not None:
        try:
            ids_norm.add(int(id_email))
        except Exception:
            pass

    if ids_email:
        for _id in ids_email:
            try:
                ids_norm.add(int(_id))
            except Exception:
                pass

    if email:
        emails_norm.add(str(email).strip().lower())

    if emails:
        emails_norm |= {str(e).strip().lower() for e in emails if str(e).strip()}

    if not ids_norm and not emails_norm:
        return {"message": "Informe ao menos um id_email/ids_email OU um e-mail/emails válido."}, 400

    # ----------------- Execução -----------------
    try:
        try:
            db.autocommit = False
        except Exception:
            pass

        # obter id_cliente via Cod_escritorio
        cur.execute("""
            SELECT id_cliente_cobranca
            FROM clientes_cobranca
            WHERE Cod_escritorio = %s AND deleted = 0
            LIMIT 1
        """, (codigo_escritorio,))
        row = cur.fetchone()
        if not row:
            return {"message": "Cliente não encontrado."}, 404

        id_cliente = row["id_cliente_cobranca"]
        deleted_rows = 0

        # --- Prioriza remoção por ID ---
        if ids_norm:
            placeholders = ",".join(["%s"] * len(ids_norm))
            params = [now, id_cliente, *ids_norm]
            sql = f"""
                UPDATE emails_clientes_cobranca
                SET deleted = {id_email}, modified_at = %s
                WHERE id_cliente_cobranca = %s
                  AND id_email_cobranca IN ({placeholders})
                  AND deleted = 0
            """
            cur.execute(sql, params)
            deleted_rows += (cur.rowcount or 0)

        # --- Fallback: remoção por e-mail (se fornecido) ---
        if emails_norm:
            placeholders = ",".join(["%s"] * len(emails_norm))
            params = [now, id_cliente, *emails_norm]
            sql = f"""
                UPDATE emails_clientes_cobranca
                SET deleted = 1, modified_at = %s
                WHERE id_cliente_cobranca = %s
                  AND LOWER(email) IN ({placeholders})
                  AND deleted = 0
            """
            cur.execute(sql, params)
            deleted_rows += (cur.rowcount or 0)

        db.commit()

        # total restante (ativos)
        cur.execute("""
            SELECT COUNT(*) AS total_emails
            FROM emails_clientes_cobranca
            WHERE id_cliente_cobranca = %s AND deleted = 0
        """, (id_cliente,))
        total_restante = cur.fetchone()["total_emails"]

        return {
            "message": ("E-mail(s) removido(s)." if deleted_rows else "Nenhum e-mail correspondente para remover."),
            "status": "removido" if deleted_rows else "sem_efeito",
            "removed": deleted_rows,
            "total_emails": total_restante,
            "Cod_escritorio": codigo_escritorio,
            "id_cliente_cobranca": id_cliente
        }, 200

    except mysql.connector.Error as err:
        try:
            if getattr(db, "in_transaction", False):
                db.rollback()
        except Exception:
            pass
        logger.error(f"Erro ao remover e-mails: {err}")
        raise BancoError(f"Falha no banco: {err}")

    except Exception as e:
        try:
            if getattr(db, "in_transaction", False):
                db.rollback()
        except Exception:
            pass
        logger.error(f"Erro inesperado ao remover e-mails: {e}")
        raise ErroInterno(f"Erro inesperado: {e}")

    finally:
        try: cur.close()
        except: pass
        try: db.close()
        except: pass



def fetch_emails_cobranca(cod_escritorio: int):
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor(dictionary=True) as cur:
                cur.execute("""
                    SELECT e.id_email_cobranca, e.email
                    FROM clientes_cobranca c
                    JOIN emails_clientes_cobranca e
                      ON e.id_cliente_cobranca = c.id_cliente_cobranca
                    WHERE c.Cod_escritorio = %s
                      AND c.deleted = 0
                      AND e.deleted = 0
                    ORDER BY e.email
                """, (cod_escritorio,))
                rows = cur.fetchall() or []
                return {"emails": rows}
    except mysql.connector.Error as err:
        logger.error(f"Erro ao puxar fetch_emails_cobranca {err}")
        raise BancoError(f"Falha no banco: {err}")
    except Exception as e:
        logger.error(f"Erro ao puxar fetch_emails_cobranca {e}")
        raise ErroInterno(f"Erro inesperado: {e}")
