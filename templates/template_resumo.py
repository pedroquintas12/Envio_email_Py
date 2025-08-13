from collections import defaultdict


def generate_email_body(cliente, clientes_data, logo, localizador, data_do_dia):
    email_body = ""
    total_processos = len(clientes_data)

    # Agrupar antes de montar o HTML
    agrupado = defaultdict(lambda: defaultdict(list))
    for proc in clientes_data:
        uf = proc['uf']
        diario = proc['sigla_diario']
        agrupado[uf][diario].append(proc)

    for uf, diarios in agrupado.items():
        email_body += f"""
        <div class="estado">
            <h2>Estado: {uf}</h2>
        """
        for diario, processos in diarios.items():
            email_body += f"""
            <div class="diario">
                <h3>Diário: {diario}</h3>
            """
            for processo in processos:
                email_body += f"""
                <div class="processo">
                    <p><strong>Número do Processo:</strong> {processo['numero_processo']}</p>
                </div>
                """
            email_body += "</div>"
        email_body += "</div>"

    # HTML final
    email_body = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width">
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; }}
            .container {{ max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 8px; }}
            .estado {{ margin-bottom: 30px; padding: 10px; background: #eaeaea; border-radius: 6px; }}
            .diario {{ margin: 15px 0; padding: 10px; background: #f9f9f9; border-left: 4px solid #007BFF; }}
            .processo {{ padding: 8px; border: 1px solid #ccc; margin: 5px 0; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <img src="{logo}" alt="Logo" style="max-height:80px;">
                <h1>{cliente}</h1>
                <p>Data: {data_do_dia.strftime('%d/%m/%y')}</p>
                <p>Localizador: {localizador}</p>
                <p>Total de processos: {total_processos}</p>
            </div>
            {email_body}
        </div>
    </body>
    </html>
    """
    return email_body
