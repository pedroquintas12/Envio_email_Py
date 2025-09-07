import pytest
from unittest.mock import patch
from app.service.envio_whatsapp import WhatsappService

@pytest.fixture
def dados_whatsapp():
    return {
        "cod_cliente": 1,
        "cliente": "Cliente Teste",
        "cliente_number": ["5581999999999"],
        "processos": [{} for _ in range(3)],
        "ID_lig": 123,
        "url_Sirius": "https://sirius.url",
        "sirius_Token": "token",
        "permanent_url": "https://s3/link.html",
        "whatslogo": "logo.png",
        "env": "production",
        "Origem": "Automatico"
    }

def test_envio_whatsapp_envia_para_numeros(dados_whatsapp):
    with patch("app.service.envio_whatsapp.enviar_mensagem_whatsapp") as mock_envio, \
         patch("app.service.envio_whatsapp.logger") as mock_logger, \
         patch("config.config.WHATSAPP_ENABLED", True):
        WhatsappService().enviar_whatsapp(**dados_whatsapp)
        # Deve chamar enviar_mensagem_whatsapp para cada número
        assert mock_envio.call_count == len(dados_whatsapp["cliente_number"])
        mock_envio.assert_called_with(
            dados_whatsapp["ID_lig"],
            dados_whatsapp["url_Sirius"],
            dados_whatsapp["sirius_Token"],
            dados_whatsapp["cliente_number"][0],
            dados_whatsapp["permanent_url"],
            f"Distribuição de novas ações - {dados_whatsapp['cliente']}",
            f"Total: {len(dados_whatsapp['processos'])} Distribuições",
            dados_whatsapp["whatslogo"]
        )

def test_envio_whatsapp_sem_numero_log_warning(dados_whatsapp):
    dados_whatsapp["cliente_number"] = []
    with patch("app.service.envio_whatsapp.enviar_mensagem_whatsapp") as mock_envio, \
         patch("app.service.envio_whatsapp.logger") as mock_logger, \
         patch("config.config.WHATSAPP_ENABLED", True):
        WhatsappService().enviar_whatsapp(**dados_whatsapp)
        mock_logger.warning.assert_called()
        mock_envio.assert_not_called()