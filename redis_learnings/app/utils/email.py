from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from app.config import MAIL_USERNAME, MAIL_PASSWORD


conf = ConnectionConfig(
    MAIL_USERNAME=MAIL_USERNAME,
    MAIL_PASSWORD=MAIL_PASSWORD,
    MAIL_FROM=MAIL_USERNAME,
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
)


async def send_email(to: str, subject: str, body: str):

    message = MessageSchema(
        subject=subject,
        recipients=[to],
        body=body,
        subtype="plain"
    )

    fm = FastMail(conf)

    await fm.send_message(message)