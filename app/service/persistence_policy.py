from typing import Iterable, Optional
from config import config
from config.logger_config import logger

def format_numbers_for_db(numbers: Optional[Iterable[str]]) -> str:
    """
    Decide o que vai para a coluna 'numero' no banco, conforme flags.
    """
    if not getattr(config, "WHATSAPP_ENABLED", True):
        logger.info("Envio de WhatsApp está desativado nas configurações.")
        if getattr(config, "SAVE_WHATSAPP_IN_DB", False):
            if numbers:
                return ", ".join(numbers)
        # Placeholder padrão
        return getattr(config, "WHATSAPP_PLACEHOLDER", "WHATSAPP DESATIVADO")

    # WhatsApp ligado:
    if not numbers:
        return "Cliente não tem número cadastrado na API"
    return ", ".join(numbers)
