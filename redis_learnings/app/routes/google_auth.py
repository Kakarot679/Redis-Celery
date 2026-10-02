import httpx
import jwt
import uuid
import secrets
from fastapi import APIRouter, Depends, HTTPException, Cookie
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import urlencode
from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from app.database import get_db
from app.models.user import User
from app.auth.jwt import create_access_token, create_refresh_token
from app.redis_client import redis_client

router = APIRouter(
    prefix="/auth/google",
    tags=["Google OAuth"]
)


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
REDIRECT_URI = "http://127.0.0.1:8000/auth/google/callback"
jwks_client = jwt.PyJWKClient(GOOGLE_JWKS_URL)


@router.get("/login")
def google_login():
    state = secrets.token_urlsafe(16)
    params={
        "client_id":GOOGLE_CLIENT_ID,
        "redirect_uri":REDIRECT_URI,
        "response_type":"code",
        "scope":"openid email profile",
        "access_type":"offline",
        "state":state,

    }

    url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    response= RedirectResponse(url)
    response.set_cookie("oauth_state",state,max_age=300,httponly=True)
    return response


@router.get("/callback")
def google_callback(code: str,state: str,oauth_state: str|None=Cookie(default=None), db: Session = Depends(get_db)):
    if oauth_state is None or oauth_state != state:
        raise HTTPException(status_code=400, detail="Invalid or missing OAuth state")

    token_response = httpx.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    token_data = token_response.json()
    id_token = token_data.get("id_token")
    if id_token is None:
        raise HTTPException(status_code=400, detail="Google token exchange failed")

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=GOOGLE_CLIENT_ID,
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid Google ID token")

    if not claims.get("email_verified"):
        raise HTTPException(status_code=401, detail="Google email not verified")

    email = claims["email"]

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(name=claims.get("name", ""), city="", email=email, password="", is_verified=True)
        db.add(user)
        db.commit()
        db.refresh(user)

    session_id = str(uuid.uuid4())
    redis_client.set(f"session:{session_id}", str(user.id), ex=1800)

    access_token = create_access_token({"user_id": user.id, "session_id": session_id})
    refresh_token = create_refresh_token({"user_id": user.id, "session_id": session_id})
    redis_client.set(f"refresh:{session_id}", refresh_token, ex=7 * 24 * 60 * 60)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer"
    }
