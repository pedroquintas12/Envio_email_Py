import pytest
from config import config
from app.repository.envio_repository import EnvioRepository

@pytest.fixture
def processo_exemplo():
    return {
        "ID_processo": 123,
        "numero_processo": "0001234-56.2025.8.00.0001",
        "cod_escritorio": 42,
        "localizador": "abc-123"
    }

def test_marcar_processado_se_automatico_chama_status_processo(monkeypatch, processo_exemplo):
    called = {"count": 0, "last_id": None}

    def fake_status_processo(pid):
        called["count"] += 1
        called["last_id"] = pid

    # monkeypatch da função real usada dentro do repo
    import app.repository.envio_repository as repo_mod
    monkeypatch.setattr(repo_mod, "status_processo", fake_status_processo)

    # quando origem = "Automatico" deve chamar
    EnvioRepository.marcar_processado_se_automatico(processo_exemplo["ID_processo"], "Automatico")
    assert called["count"] == 1
    assert called["last_id"] == processo_exemplo["ID_processo"]

    # quando origem != "Automatico" NÃO chama
    EnvioRepository.marcar_processado_se_automatico(processo_exemplo["ID_processo"], "API")
    assert called["count"] == 1  # não incrementou

def test_registrar_sucesso_chama_status_envio_com_parametros(monkeypatch, processo_exemplo):
    captured = {"args": None, "kwargs": None}

    def fake_status_envio(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

    import app.repository.envio_repository as repo_mod
    monkeypatch.setattr(repo_mod, "status_envio", fake_status_envio)

    data_str = "2025-09-03"
    localizador = "loc-123"
    email_receiver = ["contato@cliente.com"]
    numero_para_db = "WHATSAPP DESATIVADO"
    permanent_url = "https://s3/link.html"
    origem = "Automatico"
    total = 7
    subject = "ASSUNTO TESTE"

    EnvioRepository.registrar_sucesso(
        processo=processo_exemplo,
        data_str=data_str,
        localizador=localizador,
        email_receiver=email_receiver,
        numero_para_db=numero_para_db,
        permanent_url=permanent_url,
        origem=origem,
        total_processos=total,
        subject=subject
    )

    # Verifica a ordem/valores passados ao status_envio
    assert captured["args"] == (
        processo_exemplo["ID_processo"],
        processo_exemplo["numero_processo"],
        processo_exemplo["cod_escritorio"],
        processo_exemplo["localizador"],
        data_str,
        localizador,
        email_receiver,
        "SUCESSO",
        numero_para_db,
        permanent_url,
        origem,
        total,
        "S",
        subject
    )
