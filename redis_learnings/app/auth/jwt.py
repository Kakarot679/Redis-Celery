from datetime import datetime,timedelta,time
import jwt
from datetime import datetime, timedelta, timezone
import jwt

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES,SECRET_KEY,ALGORITHM


def create_access_token(data: dict):
    payload = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload.update({"exp": expire})

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token


def verify_token(token: str):
    return jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM]
    )