from typing import Optional
from app.utils.processo_data import status_envio, status_processo  

class EnvioRepository:
    @staticmethod
    def registrar_sucesso(
        processo: dict,
        data_str: str,
        localizador: str,
        email_receiver,
        numero_para_db: str,
        permanent_url: Optional[str],
        origem: str,
        total_processos: int,
        subject: str
    ):
        """
        Encapsula a chamada ao status_envio para SUCESSO.
        Se amanhã mudar a assinatura de status_envio,
        você só ajusta aqui.
        """
        status_envio(
            processo['ID_processo'],
            processo['numero_processo'],
            processo['cod_escritorio'],
            processo['localizador'],
            data_str,
            localizador,
            email_receiver,
            'SUCESSO',
            numero_para_db,
            permanent_url,
            origem,
            total_processos,
            "S",
            subject
        )

    @staticmethod
    def marcar_processado_se_automatico(processo_id: int, origem: str):
        if origem == "Automatico":
            status_processo(processo_id)
