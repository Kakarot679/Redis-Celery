from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.auth.jwt import verify_token
from app.database import get_db
from app.models.user import User
from app.redis_client import redis_client
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:

    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


    try:
        token=credentials.credentials
        payload = verify_token(token)
    except Exception:
        raise credential_exception

    user_id = payload.get("user_id")
    session_id = payload.get("session_id")

    if user_id is None or session_id is None:
        raise credential_exception

    session = redis_client.get(f"session:{session_id}")

    if session is None:
        raise credential_exception

    user = db.get(User, int(user_id))

    if user is None:
        raise credential_exception

    return {
        "user":user,
        "session_id":session_id
    }