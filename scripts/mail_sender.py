from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from pathlib import Path
import smtplib
from datetime import date
from config.logger_config import logger

def send_email(
    smtp_config,
    email_body: str,
    email_receiver: str | list[str],
    bcc_receivers: str | list[str] | None = None,
    cc_receiver: str | list[str] | None = None,
    subject: str | None = None,
    attachment: bytes | str | Path | None = None,  # aceita bytes ou caminho
    cliente: str | None = None,
    data: str | None = None,
    tipo: str = None 
):
    """
    Envia e-mail via SMTP com anexo opcional (PDF/XLSX).
    - attachment: bytes OU caminho (str/Path) para arquivo.
    - bcc não aparece nos cabeçalhos (envio real em 'all_rcpts').
    """
    (smtp_host, smtp_port, smtp_user, smtp_password,
     smtp_from_email, smtp_from_name, smtp_reply_to,
     smtp_cc_emails, smtp_bcc_emails, logo) = smtp_config

    # Normaliza destinatários
    def _to_list(x):
        if not x:
            return []
        if isinstance(x, str):
            # suporta lista separada por vírgula
            return [i.strip() for i in x.split(",") if i.strip()]
        return list(x)

    to_list = _to_list(email_receiver)
    cc_list = _to_list(cc_receiver) or _to_list(smtp_cc_emails)
    bcc_list = _to_list(bcc_receivers) or _to_list(smtp_bcc_emails)

    if not to_list:
        return {"status": "error", "message": "Destinatário 'To' ausente"}, 400

    # Cabeçalhos
    msg = MIMEMultipart()
    msg['From'] = formataddr((smtp_from_name, smtp_from_email))
    msg['To'] = ", ".join(to_list)
    if cc_list:
        msg['Cc'] = ", ".join(cc_list)
    if smtp_reply_to:
        msg.add_header('Reply-To', smtp_reply_to)
    msg['Subject'] = subject or "(sem assunto)"
    msg['Message-ID'] = make_msgid()

    # Corpo
    msg.attach(MIMEText(email_body or "", 'html', _charset="utf-8"))

    # Anexo (opcional)
    try:
        if attachment:
            # Carrega bytes se veio caminho
            if isinstance(attachment, (str, Path)):
                p = Path(attachment)
                if not p.exists():
                    return {"status": "error", "message": f"Arquivo não encontrado: {p}"}, 400
                file_bytes = p.read_bytes()
                # Se nome não vier de cliente/data, usa o próprio nome do arquivo
                default_name = p.name
            else:
                file_bytes = attachment
                default_name = None

            if not isinstance(file_bytes, (bytes, bytearray)):
                return {"status": "error", "message": "Attachment deve ser bytes"}, 400

            ext = ".pdf" if tipo == "pdf" else ".xlsx"
            # nome do arquivo
            if cliente and data:
                filename = f"{cliente}-{data}{ext}"
            else:
                filename = default_name or f"anexo{ext}"

            # Cria o MIMEApplication (base64 já aplicado automaticamente)
            if tipo == "pdf":
                part = MIMEApplication(file_bytes, _subtype="pdf")
            else:
                part = MIMEApplication(file_bytes, _subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            msg.attach(part)
    except Exception as e:
        logger.error(f"Erro ao preparar anexo: {e}")
        return {"status": "error", "message": f"Erro ao preparar anexo: {e}"}, 500

    # Envio
    try:
        all_rcpts = to_list + cc_list + bcc_list
        if not all_rcpts:
            return {"status": "error", "message": "Nenhum destinatário para envio"}, 400

        # TLS/SSL conforme porta
        if str(smtp_port) == "465":
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg, from_addr=smtp_from_email, to_addrs=all_rcpts)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg, from_addr=smtp_from_email, to_addrs=all_rcpts)

        return {"status": "ok", "message": "E-mail enviado"}, 200

    except Exception as err:
        logger.error(f"Erro ao enviar email: {err}")
        return {"status": "error", "message": str(err)}, 500
