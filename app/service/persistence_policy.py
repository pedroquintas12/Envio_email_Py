from typing import Iterable, Optional
from config import config
from config.logger_config import logger

def format_numbers_for_db(numbers: Optional[Iterable[str]]) -> str:
    """
    Decide o que vai para a coluna 'numero' no banco, conforme flags.
    """
    if not config.WHATSAPP_ENABLED == True:
        logger.info("Envio de WhatsApp está desativado nas configurações.")
        if config.SAVE_WHATSAPP_IN_DB == True:
            if numbers:
                return ", ".join(numbers)
        # Placeholder padrão
        return config.WHATSAPP_PLACEHOLDER 

    # WhatsApp ligado:
    if not numbers:
        return "Cliente não tem número cadastrado na API"
    return ", ".join(numbers)
