import html
from fastapi import APIRouter,Depends,HTTPException,status,Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.auth.jwt import create_access_token,create_refresh_token,verify_token
from app.core.security import verify_password,hash_password
import uuid
import json
from app.redis_client import redis_client
from app.dependencies.auth import get_current_user
import random
from app.utils.email import send_email
from fastapi.responses import HTMLResponse

router=APIRouter(
    prefix="/auth",
    tags=["Authentication"]
    )


@router.post("/login")
def login(email:str,password:str,db:Session=Depends(get_db)):
    fail_key=f"login_fail:{email}"
    if redis_client.get(fail_key) and int(redis_client.get(fail_key)) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later."
        )

    user=db.query(User).filter(User.email==email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Credentials"
        )

    if not user.is_verified:
        raise HTTPException(
        status_code=403,
        detail="Please verify your email first."
    )

    if not verify_password(password, user.password):
        fail_count = redis_client.incr(fail_key)
        if fail_count == 1:
            redis_client.expire(fail_key, 300)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Credentials"
        )

    redis_client.delete(fail_key)
        
    

    session_id=str(uuid.uuid4())
    redis_client.set(
        f"session:{session_id}",
      json.dumps( {   "user_id":user.id,
            
       }),ex=1800
        
    )

    access_token=create_access_token(

        {
            "user_id":user.id,
            "session_id":session_id
        })
    refresh_token=create_refresh_token(

        {
            "user_id":user.id,
            "session_id":session_id

        })

    redis_client.set(
        f"refresh:{session_id}",
        refresh_token,
        ex=7 * 24 * 60 * 60
    )

    return{
        "access_token":access_token,
        "refresh_token":refresh_token,
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


@router.post("/refresh")
def refresh(
    refresh_token:str
    ):

    payload=verify_token(refresh_token)
    user_id=payload.get("user_id")
    session_id=payload.get("session_id")
    if redis_client.get(f"session:{session_id}") is None:
        raise HTTPException(status_code=401, detail="Session expired or logged out")
    
    stored_refresh=redis_client.get(f"refresh:{session_id}")
    if (stored_refresh!= refresh_token):
        raise HTTPException(status_code=401, detail="Refresh token reused or invalid")


    new_refresh_token = create_refresh_token({"user_id": user_id, "session_id": session_id})
    redis_client.set(f"refresh:{session_id}", new_refresh_token, ex=7 * 24 * 60 * 60)
          
    new_access_token=create_access_token(
        {
            "user_id":user_id,
            "session_id":session_id
        }
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "Bearer"
    }

@router.post("/send-otp")
async def send_otp(email:str):
    otp=random.randint(100000,999999)
    redis_client.set(f"otp:{email}",otp,ex=300)

    await send_email(
        email,
        "Your verification code",
        f"Your OTP is {otp}. It expires in 5 minutes."
    )

    return{
        "message":"otp generated and sent to your email"
      
    
    }

@router.post("/verify-otp")
def verify_otp(
    email:str,
    otp:int,
    db:Session=Depends(get_db)
):

    stored_otp=redis_client.get(f"otp:{email}")
    if stored_otp is None:
        return {
        "message": "OTP Expired"
    }
    if int(stored_otp) != otp:
        return {
            "message": "Invalid OTP"
        }

    redis_client.delete(f"otp:{email}")

    user=db.query(User).filter(User.email==email).first()
    if not user:
        return {
        "message": "User not found"
    }
    user.is_verified=True
    db.commit()

    return{
            "message":"otp successfully verified"
        }

@router.post("/test-email")
async def test_email():
    await send_email(
        "hardikgupta08122003@gmail.com",
         "FastAPI Test",
        "Hello! This email was sent from my FastAPI application."
        )

    return {
            "message": "Email sent successfully"
        }

@router.post("/forgot-password")
async def forgot_password(
    email,
    db:Session=Depends(get_db)
):
    user=db.query(User).filter(User.email==email).first()

    if not user:
        return{
            "message":"If an account exists,a reset email has been sent."

        }
    reset_token=str(uuid.uuid1
                    ())
    redis_client.set(
        f"password_reset:{reset_token}",
        user.id,
        ex=600
    )        

    reset_link=(
        f"http://127.0.0.1:8000/auth/reset-password"
        f"?token={reset_token}"
    )
    await send_email(
        user.email,
        f"Reset your password",
        f"Click this link to reset your password:\n\n{reset_link}"
    )
    return {
        "message": "If an account exists, a reset email has been sent."
    }


from fastapi import Form
from fastapi.responses import HTMLResponse


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(token: str):
    safe_token = html.escape(token)
    return f"""
    <html>
        <body>
            <h2>Reset Password</h2>

            <form action="/auth/reset-password" method="post">

                <input type="hidden" name="token" value="{safe_token}">

                <label>New Password:</label>
                <input type="password" name="new_password" required>

                <button type="submit">Reset Password</button>

            </form>
        </body>
    </html>
    """


@router.post("/reset-password")
def reset_password(
    token: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    user_id = redis_client.get(
        f"password_reset:{token}"
    )

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    user = db.query(User).filter(
        User.id == int(user_id)
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user.password = hash_password(new_password)
    db.commit()

    redis_client.delete(
        f"password_reset:{token}"
    )

    return {
        "message": "Password reset successfully"
    }