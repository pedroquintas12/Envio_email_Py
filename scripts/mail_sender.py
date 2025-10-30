from email.mime.application import MIMEApplication
from pathlib import Path
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config.logger_config import logger


def send_email(smtp_config, email_body, email_receiver, bcc_receivers=None , cc_receiver=None, subject = None, attachment=None, cliente=None, data= None):
    
    smtp_host, smtp_port, smtp_user, smtp_password, smtp_from_email, smtp_from_name,smtp_reply_to,smtp_cc_emails,smtp_bcc_emails,logo = smtp_config


    from_address = f"{smtp_from_name} <{smtp_from_email}>"


    # Envio do e-mail
    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['To'] = email_receiver
    
    if bcc_receivers:
        msg['Bcc'] = bcc_receivers
    if cc_receiver:
        msg['Cc'] = cc_receiver
        
    msg['Subject'] = subject
    msg.attach(MIMEText(email_body, 'html'))
    
    try:
        if attachment:  
            anexo_excel = MIMEApplication(attachment, Name=f"{cliente}-{data}.xlsx")
            anexo_excel["Content-Disposition"] = f'attachment; filename="{cliente}-{data}.xlsx"'
            msg.attach(anexo_excel)
            
        # Envio do e-mail usando SMTP   
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls() 
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
    except Exception as err:
        logger.error(f"Erro ao enivar email: {err}")
        return {"status": "error", "message": str(err)}, 500