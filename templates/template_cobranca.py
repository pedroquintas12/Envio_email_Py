from datetime import datetime
import html

def generate_email_cobranca(
    cliente: str,
    empresa_nome: str,
    conteudo: str,                  # texto digitado no front
    conteudo_e_html: bool = False,  # True = insere HTML do front como veio (sanitizado)
    logo: str | None = None,
):
    data_fmt = datetime.now().strftime("%d/%m/%Y")

    styles = """
    body { margin:0; padding:0; background:#f4f4f4; -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }
    .wrapper { width:100%; background:#f4f4f4; padding:24px 0; }
    .container { max-width:640px; margin:0 auto; background:#ffffff; border-radius:8px; overflow:hidden; }
    .header { padding:20px 24px; border-bottom:1px solid #eaeaea; }
    .brand { display:flex; align-items:center; gap:12px; }
    .brand img { max-height:48px; display:block; }
    .brand h1 { margin:0; font:600 18px Arial,Helvetica,sans-serif; color:#111111; }
    .meta { margin-top:6px; font:400 12px Arial,Helvetica,sans-serif; color:#666666; }
    .content { padding:20px 24px; font:400 14px/1.6 Arial,Helvetica,sans-serif; color:#222222; }
    .content p { margin:0 0 12px 0; }
    .box { background:#f7f9fc; border:1px solid #e6edf7; border-radius:6px; padding:12px; margin:12px 0; }
    @media (prefers-color-scheme: dark) {
      body { background:#0b0b0b; }
      .container { background:#151515; }
      .header { border-color:#2a2a2a; }
      .meta { color:#aaaaaa !important; }
      .content { color:#e9e9e9 !important; }
      .box { background:#1b2530; border-color:#263342; }
    }
    """

    logo_html = f'<img src="{logo}" alt="{empresa_nome}">' if logo else ""
    conteudo_html = conteudo if conteudo_e_html else html.escape(conteudo).replace("\n", "<br>")

    return f"""\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width">
  <title>{empresa_nome} — Lembrete</title>
  <style>{styles}</style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      <div class="header">
        <div class="brand">
          {logo_html}
          <h1>{empresa_nome}</h1>
        </div>
        <div class="meta">Data: {data_fmt}</div>
      </div>

      <div class="content">
        <p>Olá, <strong>{cliente}</strong>! Tudo bem?</p>

        <div class="box">
          <div class="content-body">{conteudo_html}</div>
        </div>

        <p style="font-size:12px; color:#666; margin-top:16px;">
          Caso já tenha regularizado, por gentileza desconsidere esta mensagem.
        </p>

        <p style="font-size:12px; color:#666;">
          Atenciosamente,<br>
          <strong>Neide Quintas</strong>
        </p>
      </div>
    </div>
  </div>
</body>
</html>
"""
