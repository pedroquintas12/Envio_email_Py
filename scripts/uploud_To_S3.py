from config.logger_config import logger
import boto3
import io
from botocore.exceptions import NoCredentialsError, ClientError

def upload_html_to_s3(email_body, bucket_name, object_name, aws_s3_access_key, aws_s3_secret_key,region,resumo):
    # Criação do cliente S3
    s3_client = boto3.client(
        's3',
        aws_access_key_id=aws_s3_access_key,
        aws_secret_access_key=aws_s3_secret_key
    )

    # Converta o email_body em bytes e crie um buffer de memória
    html_buffer = io.BytesIO(email_body.encode('utf-8'))

    try:
        # Faz o upload do arquivo HTML para o S3
        s3_client.upload_fileobj(html_buffer, bucket_name, object_name, ExtraArgs={'ContentType': 'text/html', 'ACL': 'public-read'})
        logger.info(f"Arquivo {object_name} enviado para o S3 com sucesso.")

        if resumo == True:
            return f"https://{bucket_name}.s3.{region}.amazonaws.com/{object_name}"

        # Retornar a URL permanente do arquivo
        return f"https://{bucket_name}/{object_name}"  
 

    except FileNotFoundError:
        logger.error(f"O arquivo {object_name} não foi encontrado.")
    except NoCredentialsError:
        logger.error("As credenciais do AWS não estão disponíveis.")
    except ClientError as e:
        logger.error(f"Erro ao enviar arquivo para o S3: {e}")
    except Exception as err:
        logger.error(f"erro não identificado ao enviar para S3: {err}")



def thread_function(email_body, bucket_s3, object_name, aws_s3_access_key, aws_s3_secret_key, region, resumo,queue):
    try:
        permanent_url = upload_html_to_s3(email_body, bucket_s3, object_name, aws_s3_access_key, aws_s3_secret_key,region,resumo)
        queue.put(permanent_url)  # Coloca o URL na fila para a função principal
    except Exception as e:
        logger.error(f"Erro ao enviar para S3: {e}")
        queue.put(None)