from datetime import datetime
from collections import defaultdict
from config.db_conexão import get_db_ligcontato_connection
from config.logger_config import logger
from flask import jsonify
import concurrent.futures
from app.apiLig import fetch_cliente_api

def processar_envio_publicacoes(companies_id=None, cod_escritorio=None, data_disponibilizacao=None, token=None):
    # defaultdict que cria outro defaultdict que cria lista
    clientes_data = {}

    try:
        conn = get_db_ligcontato_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT
            p.publications_id ,
            p.num_processo AS numero_processo,
            p.data_disponibilizacao AS data_distribuicao,
            p.deleted,
            p.cod_escritorio,
            p.sigla_diario,
            p.uf
        FROM publications p
        JOIN publications_published p2 
            ON p2.publications_published_id = p.publications_published_id
            AND (p2.send_email_status = 'S' OR p2.send_whatsapp_status = 'S')
            AND p2.companies_id = p.companies_id
        WHERE p.deleted = 0
        """

        params = {}
        if companies_id:
            query += " AND p.companies_id = %(companies_id)s"
            params["companies_id"] = companies_id
        if cod_escritorio:
            query += " AND p.cod_escritorio = %(cod_escritorio)s"
            params["cod_escritorio"] = cod_escritorio
        if data_disponibilizacao:
            if isinstance(data_disponibilizacao, datetime):
                data_disponibilizacao = data_disponibilizacao.strftime("%Y-%m-%d")
            query += " AND p.data_disponibilizacao = %(data_disponibilizacao)s"
            params["data_disponibilizacao"] = data_disponibilizacao

        cursor.execute(query, params)
        registros = cursor.fetchall()
        cursor.close()
        conn.close()

        if not registros:
            logger.info(
                f"Nenhum registro encontrado para os critérios fornecidos: companies_id={companies_id}, cod_escritorio={cod_escritorio}, data_disponibilizacao={data_disponibilizacao}"
            )
            return jsonify({"error": "Nenhum registro encontrado"}), 404

        # Processa em paralelo
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for process in registros:
                futures.append(
                    executor.submit(process_result, process, clientes_data, token)
                )
            concurrent.futures.wait(futures)

    except Exception as e:
        logger.error(f"Erro ao processar envio de publicações: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
        cursor.close()
    return clientes_data


def process_result(process, clientes_data, token):
    try:
        clienteVSAP, Office_id, office_status = fetch_cliente_api(process['cod_escritorio'], token)

        uf = process['uf']
        diario = process['sigla_diario']
        
        # Adiciona os dados ao cliente
        if clienteVSAP not in clientes_data:
            clientes_data[clienteVSAP] = []

        clientes_data[clienteVSAP].append({
            'Office_id': Office_id,
            'office_status': office_status,
            'publications_id': process['publications_id'],
            'cod_escritorio': process['cod_escritorio'],
            'numero_processo': process['numero_processo'],
            'data_distribuicao': process['data_distribuicao'],
            'sigla_diario': diario,
            'uf': uf,
        })

    except Exception as e:
        logger.error(f"Erro ao processar resultado do processo {process.get('numero_processo')}: {e}", exc_info=True)

