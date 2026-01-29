from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from pathlib import Path
import smtplib
import re
from config.logger_config import logger


def safe_header(text: str) -> str:
    """
    Remove caracteres inválidos de headers SMTP
    """
    if not text:
        return ""
    text = str(text)
    text = re.sub(r'[\r\n]', '', text)
    return text.strip()


def safe_filename(text: str) -> str:
    """
    Garante nome de arquivo compatível com SMTP
    """
    if not text:
        return "anexo"
    text = str(text)
    return re.sub(r'[^A-Za-z0-9._-]', '_', text)


def send_email(
    smtp_config,
    email_body: str,
    email_receiver: str | list[str],
    bcc_receivers: str | list[str] | None = None,
    cc_receiver: str | list[str] | None = None,
    subject: str | None = None,
    attachment: bytes | str | Path | None = None,
    cliente: str | None = None,
    data: str | None = None,
    tipo: str | None = None
):
    (smtp_host, smtp_port, smtp_user, smtp_password,
     smtp_from_email, smtp_from_name, smtp_reply_to,
     smtp_cc_emails, smtp_bcc_emails, logo) = smtp_config

    # -----------------------------
    # Normalização de listas
    # -----------------------------
    def _to_list(x):
        if not x:
            return []
        if isinstance(x, str):
            return [i.strip() for i in x.split(",") if i.strip()]
        return list(x)

    to_list = _to_list(email_receiver)
    cc_list = _to_list(cc_receiver) or _to_list(smtp_cc_emails)
    bcc_list = _to_list(bcc_receivers) or _to_list(smtp_bcc_emails)

    if not to_list:
        return {"status": "error", "message": "Destinatário 'To' ausente"}, 400

    # -----------------------------
    # Montagem do e-mail (CORRETA)
    # -----------------------------
    msg = MIMEMultipart("alternative")

    msg["From"] = formataddr(
        (safe_header(smtp_from_name), smtp_from_email)
    )
    msg["To"] = ", ".join(to_list)

    if cc_list:
        msg["Cc"] = ", ".join(cc_list)

    if smtp_reply_to:
        msg.add_header("Reply-To", smtp_reply_to)

    msg["Subject"] = safe_header(subject or "(sem assunto)")
    msg["Message-ID"] = make_msgid()

    # -----------------------------
    # Corpo (texto + HTML)
    # -----------------------------
    msg.attach(
        MIMEText(
            "Este e-mail contém conteúdo em HTML. "
            "Caso não visualize corretamente, utilize um cliente compatível.",
            "plain",
            "utf-8"
        )
    )

    msg.attach(
        MIMEText(email_body or "", "html", "utf-8")
    )

    # -----------------------------
    # Anexo (opcional)
    # -----------------------------
    try:
        if attachment:
            if isinstance(attachment, (str, Path)):
                p = Path(attachment)
                if not p.exists():
                    return {
                        "status": "error",
                        "message": f"Arquivo não encontrado: {p}"
                    }, 400
                file_bytes = p.read_bytes()
                default_name = p.name
            else:
                file_bytes = attachment
                default_name = None

            if not isinstance(file_bytes, (bytes, bytearray)):
                return {
                    "status": "error",
                    "message": "Attachment deve ser bytes"
                }, 400

            ext = ".pdf" if tipo == "pdf" else ".xlsx"

            if cliente and data:
                raw_name = f"{cliente}-{data}{ext}"
            else:
                raw_name = default_name or f"anexo{ext}"

            filename = safe_filename(raw_name)

            if tipo == "pdf":
                part = MIMEApplication(file_bytes, _subtype="pdf")
            else:
                part = MIMEApplication(
                    file_bytes,
                    _subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{filename}"'
            )
            msg.attach(part)

    except Exception as e:
        logger.error(f"Erro ao preparar anexo: {e}")
        return {
            "status": "error",
            "message": f"Erro ao preparar anexo: {e}"
        }, 500

    # -----------------------------
    # Envio SMTP
    # -----------------------------
    try:
        all_rcpts = to_list + cc_list + bcc_list

        if not all_rcpts:
            return {
                "status": "error",
                "message": "Nenhum destinatário para envio"
            }, 400

        if str(smtp_port) == "465":
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(
                    msg,
                    from_addr=smtp_from_email,
                    to_addrs=all_rcpts
                )
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(
                    msg,
                    from_addr=smtp_from_email,
                    to_addrs=all_rcpts
                )

        return {"status": "ok", "message": "E-mail enviado"}, 200

    except Exception as err:
        logger.error(f"Erro ao enviar email: {err}")
        return {
            "status": "error",
            "message": str(err)
        }, 500
