import pytest
from app.service.persistence_policy import format_numbers_for_db
from config import config

@pytest.mark.parametrize(
    "whatsapp_enabled, save_in_db, numbers, expected",
    [
        # WHATSAPP DESLIGADO e NÃO salvar números => placeholder
        (False, False, ["5599999999999", "5588888888888"], "WHATSAPP DESATIVADO"),
        (False, False, None, "WHATSAPP DESATIVADO"),
        # WHATSAPP DESLIGADO mas salvar números (auditoria)
        (False, True, ["5599999999999", "5588888888888"], "5599999999999, 5588888888888"),
        (False, True, None, "WHATSAPP DESATIVADO"),  # sem números, cai no placeholder
        # WHATSAPP LIGADO, sem números
        (True, True, None, "Cliente não tem número cadastrado na API"),
        (True, False, None, "Cliente não tem número cadastrado na API"),
        # WHATSAPP LIGADO, com números
        (True, True, ["5599999999999"], "5599999999999"),
        (True, True, ["5599", "5588"], "5599, 5588"),
    ]
)
def test_format_numbers_for_db(monkeypatch, whatsapp_enabled, save_in_db, numbers, expected):
    # configura flags dinamicamente
    monkeypatch.setattr(config, "WHATSAPP_ENABLED", whatsapp_enabled, raising=False)
    monkeypatch.setattr(config, "SAVE_WHATSAPP_IN_DB", save_in_db, raising=False)
    monkeypatch.setattr(config, "WHATSAPP_PLACEHOLDER", "WHATSAPP DESATIVADO", raising=False)

    assert format_numbers_for_db(numbers) == expected
