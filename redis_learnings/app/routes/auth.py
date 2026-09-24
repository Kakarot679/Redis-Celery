from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.auth.jwt import create_access_token
from app.core.security import verify_password
import uuid
import json
from app.redis_client import redis_client
from app.dependencies.auth import get_current_user



router=APIRouter(
    prefix="/auth",
    tags=["Authentication"]
    )


@router.post("/login")
def login(email:str,password:str,db:Session=Depends(get_db)):
    user=db.query(User).filter(User.email==email).first()



    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Credentials"
        )

    if not verify_password(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Credentials"
        )

    session_id=str(uuid.uuid4())
    redis_client.set(
        f"session:{session_id}",
      json.dumps( {   "user_id":user.id,
            
       }),ex=1800
        
    )
    token=create_access_token(
        {
            "user_id":user.id,
            "session_id":session_id
        }

    )
    return{
        "access token":token,
        "token_type":"Bearer"
    }


@router.post("/logout")
def logout(
    current:User=Depends(get_current_user)):
    session_id = current["session_id"]

    redis_client.delete(f"session:{session_id}")

    return {
    "message": "Logged out successfully"
}

