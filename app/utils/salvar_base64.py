import base64
from io import BytesIO
import re

from flask import send_file
from config.logger_config import logger

def salvar_arquivo_base64(base64_string, localizador):
    try:

        base64_string = re.sub(r"^data:.*;base64,", "", base64_string.strip())

        # Decodifica o base64 para bytes
        file_bytes = base64.b64decode(base64_string)

        # Cria um arquivo em memória
        buffer = BytesIO(file_bytes)

        # Retorna o arquivo diretamente para download
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"anexo_resumo_{localizador}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo: {e}")
