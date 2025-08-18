from app.utils.envio_email_resumo import enviar_emails_resumo

# Teste no modo automático
enviar_emails_resumo(
    Origem="Automatico",
    data_inicial=None,
    email=None,
    codigo=None,
    token=None
)

# Ou no modo API
# enviar_emails_resumo(
#     Origem="API",
#     data_inicial="2025-08-10",
#     email="teste@teste.com",
#     codigo="1234",
#     token=None
# )
