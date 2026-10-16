import asyncio
from celery import Celery
from app.config import REDIS_URL
from app.utils.email import send_email

celery_app = Celery("redis_learnings", broker=REDIS_URL, backend=REDIS_URL)


@celery_app.task
def send_reset_email_task(email: str, reset_link: str):
    asyncio.run(send_email(
        email,
        "Reset your password",
        f"Click this link to reset your password:\n\n{reset_link}"
    ))
