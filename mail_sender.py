import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_email(smtp_config, email_body, email_receiver, bcc_receivers,cc_receiver, subject):
    smtp_host, smtp_port, smtp_user, smtp_password, smtp_from_email, smtp_from_name,smtp_reply_to,smtp_cc_emails,smtp_bcc_emails,logo = smtp_config


    from_address = f"{smtp_from_name} <{smtp_from_email}>"


    # Envio do e-mail
    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['To'] = email_receiver
    msg['Bcc'] = bcc_receivers
    msg['Subject'] = subject
    msg['Cc'] = cc_receiver
    msg.attach(MIMEText(email_body, 'html'))

    # Envio do e-mail usando SMTP
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls() 
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
