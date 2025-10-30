from typing import Optional
from app.utils.processo_data import status_envio_cobranca


class cobrancaRepository:
    @staticmethod
    def registrar_sucesso(
        cod_escritorio: int,
        email_receiver,
        subject: str,
        content: str,
        autor: str
    ):
        """
        Encapsula a chamada ao status_envio para SUCESSO.
        Se amanhã mudar a assinatura de status_envio.
        """
        status_envio_cobranca(
            cod_escritorio,
            email_receiver,
            subject,
            content,
            "S",
            "SUCESSO",
            autor
        )

    @staticmethod
    def registrar_falha(
        cod_escritorio: int,
        email_receiver,
        subject: str,
        content: str,
        autor: str,
        messagem: Optional[str]
    ):
        """
        Encapsula a chamada ao status_envio para SUCESSO.
        Se amanhã mudar a assinatura de status_envio.
        """
        status_envio_cobranca(
            cod_escritorio,
            email_receiver,
            subject,
            content,
            "E",
            messagem,
            autor

        )