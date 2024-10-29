# Projeto de Envio de Notificações Processuais

Este projeto em Python automatiza o envio de notificações processuais via e-mail e WhatsApp para clientes, capturando dados de processos e configurando os parâmetros de envio com base nos registros do banco de dados.

## Funcionalidades

- Consulta de processos com status "P" (pendente) e coleta de dados relevantes.
- Geração de lista de clientes e processo detalhado com informações sobre autores, réus, links e status.
- Verificação de status de clientes para determinar se estão ativos ou bloqueados.
- Captura de números de telefone e e-mails para envio.
- Configuração SMTP para envio de e-mails e integração com API de WhatsApp.
- Atualização do status de processos após envio e armazenamento de logs.

## Estrutura do Código

### Funções Principais

- `fetch_processes_and_clients`: Captura dados dos processos pendentes para envio.
- `fetch_links`: Coleta links do processo com base no ID.
- `fetch_autor` e `fetch_reu`: Captura os autores e réus do processo.
- `fetch_numero`: Obtém os números de telefone de clientes ativos.
- `validar_cliente`: Verifica o status do cliente no banco de dados.
- `fetch_email`: Coleta e-mails válidos para envio.
- `fetch_companies`: Puxa dados de configuração da tabela `companies`.
- `status_envio`: Atualiza o status do processo e registra o envio de e-mails.
- `nome_cliente`: Obtém o nome do cliente pelo código do escritório.
- `cliente_erro`: Marca o processo com status de erro em caso de falha.

### Exemplo de Código

```python
import uuid
from datetime import datetime
import mysql.connector
import logging
from logger_config import logger
import os
from db_conexão import get_db_connection, get_db_ligcontato

# Captura todos os dados do processo
def fetch_processes_and_clients():
    db_connection = get_db_connection()
    db_cursor = db_connection.cursor()
    try:
        query = ("SELECT p.Cod_escritorio, p.numero_processo, MAX(p.data_distribuicao), "
                 "p.orgao_julgador, p.tipo_processo, p.status, p.uf, p.sigla_sistema, "
                 "MAX(p.instancia), p.tribunal, MAX(p.ID_processo), MAX(p.LocatorDB), p.tipo_processo "
                 "FROM apidistribuicao.processo AS p "
                 "WHERE p.status = 'P' "
                 "GROUP BY p.numero_processo, p.Cod_escritorio, p.orgao_julgador, "
                 "p.tipo_processo, p.uf, p.sigla_sistema, p.tribunal;")
        db_cursor.execute(query)
        results = db_cursor.fetchall()
        clientes_data = {}
        for result in results:
            process_result(result, clientes_data)
        return clientes_data
    except Exception as err:
        logger.error(f"Erro ao executar a consulta: {err}")
        return {}
    finally:
        db_cursor.close()
        db_connection.close()
```
Pré-requisitos
- Python 3.8+
- MySQL Connector
- Configuração de log personalizada (logger_config.py)
- Arquivo .env para variáveis de ambiente sensíveis, como credenciais de banco de dados e chaves de API.
### Como Executar
- Clone o repositório.
- Instale as dependências:
```
pip install mysql-connector-python
```
- Configure suas variáveis de ambiente no arquivo .env.
- Execute o script:
```
python main.py
```
### Estrutura do Banco de Dados:
- Tabela processo: Armazena dados dos processos para serem enviados.
- Tabela offices_whatsapp_numbers: Armazena os números de WhatsApp dos clientes.
- Tabela offices: Contém status e dados dos escritórios.
- Tabela companies: Armazena configurações SMTP e de API.
### Logs
O projeto inclui logs detalhados em um arquivo específico, com mensagens de erro para auxiliar na depuração.
