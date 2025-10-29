from flask import app, jsonify


class AppError(Exception):
    """Classe base para todos os erros da aplicação."""
    def __init__(self, mensagem, codigo, tipo="Erro"):
        self.mensagem = mensagem
        self.codigo = codigo
        self.tipo = tipo
        super().__init__(mensagem)

    def to_dict(self):
        return {    
            "mensagem": self.mensagem,
            "tipo": self.tipo,
            "status": "error",
            "codigo": self.codigo
        }


class BancoError(AppError):
    def __init__(self, mensagem="Erro no banco de dados", codigo=5001):
        super().__init__(mensagem, codigo, tipo="Banco de Dados")


class ApiError(AppError):
    def __init__(self, mensagem="Erro na API externa", codigo=5002):
        super().__init__(mensagem, codigo, tipo="API Externa")


class DadosInvalidosError(AppError):
    def __init__(self, mensagem="Dados inválidos recebidos", codigo=5003):
        super().__init__(mensagem, codigo, tipo="Dados Inválidos")


class ErroInterno(AppError):
    def __init__(self, mensagem="Erro interno inesperado", codigo=5000):
        super().__init__(mensagem, codigo, tipo="Interno")

