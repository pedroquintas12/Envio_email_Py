import uuid
from datetime import datetime
import mysql.connector
import logging
from logger_config import logger
import os
from db_conexão import get_db_connection
from db_conexão import get_db_ligcontato


def fetch_processes_and_clients():


    db_connection = get_db_connection()
    db_cursor = db_connection.cursor()

    try:
        query = (
            "SELECT c.Cliente_VSAP as clienteVSAP, p.Cod_escritorio, p.numero_processo, "
            "MAX(p.data_distribuicao) as data_distribuicao, "
            "p.orgao_julgador, p.tipo_processo, p.status, "
            "p.uf, p.sigla_sistema, MAX(p.instancia), p.tribunal, MAX(p.ID_processo), MAX(p.LocatorDB), p.tipo_processo, MAX(c.emails) "
            "FROM apidistribuicao.processo AS p "
            "JOIN apidistribuicao.clientes AS c ON p.Cod_escritorio = c.Cod_escritorio "
            "WHERE p.status = 'P' "
            "GROUP BY p.numero_processo, clienteVSAP, p.Cod_escritorio, p.orgao_julgador, p.tipo_processo, p.uf, p.sigla_sistema, p.tribunal;"
        )

        db_cursor.execute(query)
        results = db_cursor.fetchall()
        clientes_data = {}

        for result in results:
            # Process the result and add to clientes_data
            process_result(result, clientes_data)

        return clientes_data

    except mysql.connector.Error as err:
        logger.error(f"Erro ao executar a consulta: {err}")
        return {}
    finally:
        db_cursor.close()
        db_connection.close()

def process_result(result, clientes_data):
    clienteVSAP = result[0]
    num_processo = result[2]
    data_distribuicao = datetime.strptime(str(result[3]), '%Y-%m-%d').strftime('%d/%m/%Y')
    tribunal = result[10]
    uf = result[7]
    instancia = result[9]
    comarca = result[8]
    emails= result[14]

    # Collect for the process
    links_list = fetch_links(result[11])
    autor_list = fetch_autor(result[11])
    reu_list = fetch_reu(result[11])
    status_cliente = validar_cliente(result[1])

    # Add process data to the clients' data
    if clienteVSAP not in clientes_data:
        clientes_data[clienteVSAP] = []

    clientes_data[clienteVSAP].append({
        'ID_processo' : result[11],
        'cod_escritorio': result[1],
        'numero_processo': num_processo,
        'data_distribuicao': data_distribuicao,
        'orgao': result[4],
        'classe_judicial': result[5],
        'autor': autor_list if autor_list else "[Nenhum dado disponível]",
        'reu': reu_list if reu_list else "[Nenhum dado disponível]",
        'links': links_list,
        'tribunal': tribunal,
        'uf': uf,
        'instancia': instancia,
        'comarca': comarca,
        'localizador': result[12],
        'tipo_processo': result[13],
        'emails': emails,
        'cliente_status' : status_cliente
    })

def fetch_links(process_id):
    db_connection = get_db_connection()
    db_cursor = db_connection.cursor()
    
    querylinks = "SELECT * FROM apidistribuicao.processo_docinicial WHERE ID_PROCESSO = %s AND doc_peticao_inicial= 0"
    db_cursor.execute(querylinks, (process_id,))
    results_links = db_cursor.fetchall()

    links_list = []
    for links in results_links:
        id_link = links[1]
        link_doc = links[2]
        tipoLink = links[3]
        links_list.append({'link_doc': link_doc,
                            'tipoLink': tipoLink,
                              'id_link': id_link})

    db_cursor.close()
    db_connection.close()

    return links_list

def fetch_autor(process_id):
    db_connection = get_db_connection()
    db_cursor = db_connection.cursor()
    
    queryautor = "SELECT * FROM apidistribuicao.processo_autor WHERE ID_processo = %s"
    db_cursor.execute(queryautor, (process_id,))
    results_autor = db_cursor.fetchall()

    autor_list= []
    for autores in results_autor:
        ID_autor = autores[1]
        Cod_Polo = autores[2]
        nome = autores[3]
        autor_list.append({'id_autor':ID_autor,
                           'cod_polo':Cod_Polo,
                           'nomeAutor':nome})
    db_cursor.close()
    db_connection.close()

    return autor_list


def fetch_reu(process_id):
    db_connection = get_db_connection()
    db_cursor = db_connection.cursor()
    
    queryreu = "SELECT * FROM apidistribuicao.processo_reu WHERE ID_processo = %s"
    db_cursor.execute(queryreu, (process_id,))
    results_reu = db_cursor.fetchall()

    reu_list = []
    for reus in results_reu:
        ID_reu= reus[1]
        Cod_polo = reus[2]
        nome = reus[3]
        reu_list.append({'id_reu': ID_reu,
                         'cod_polo': Cod_polo,
                         'nomeReu':nome})
    db_cursor.close()
    db_connection.close()

    return reu_list

def fetch_numero(cod_cliente):
        db_connection = get_db_ligcontato()
        db_cursor_lig = db_connection.cursor()
            #capturar numero para envio
        db_cursor_lig.execute("""SELECT nw.`number` FROM offices_whatsapp_numbers nw JOIN offices e ON nw.offices_id = e.offices_id 
                              WHERE e.office_code = %s AND nw.status = 'L'""",(cod_cliente,))
        cliente_number = db_cursor_lig.fetchall()
        list_numbers = []

        for number in cliente_number:
            numero = number[0]
            list_numbers.append({'numero': numero})
        db_connection.close()
        db_cursor_lig.close()

        return list_numbers

def validar_cliente(cod_cliente):
        db_connection = get_db_connection()
        db_cursor = db_connection.cursor()

        #faz a verficação se o cliente esta ativo (L) ou Bloqueado (B)
        db_cursor.execute("SELECT status FROM clientes WHERE Cod_escritorio = %s",(cod_cliente,))
        cliente_STATUS = db_cursor.fetchone()

        db_connection.close()
        db_cursor.close()

        return cliente_STATUS

def fetch_email(cod_cliente):
     
        db_connection = get_db_ligcontato()
        db_cursor_lig = db_connection.cursor()
        #capturar email para envio
        db_cursor_lig.execute("""SELECT GROUP_CONCAT(DISTINCT oe.email ORDER BY oe.email SEPARATOR ', ') 
                               FROM offices_emails oe JOIN offices e ON oe.offices_id = e.offices_id WHERE e.office_code = %s""",(cod_cliente,))
        email_cliente = db_cursor_lig.fetchone()

        return email_cliente
