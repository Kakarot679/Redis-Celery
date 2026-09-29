from fastapi import APIRouter,Depends,HTTPException,status
from app.models.user import User
from app.schemas.user import UserCreate,UserRead,UserUpdate
from sqlalchemy.orm import Session
from app.database import get_db
from app.redis_client import redis_client
from app.dependencies.rate_limiter import rate_limit
import json
from app.dependencies.auth import get_current_user
from app.core.security import hash_password

router = APIRouter(
    prefix="/user",
    tags=["user_router"],
    dependencies=[Depends(rate_limit)]
)


@router.post("/" ,response_model=UserRead)
def create_user(user:UserCreate,db:Session=Depends(get_db)):
 


 data=user.model_dump()
 dp_email=db.query(User).filter(User.email==user.email).first()

 if dp_email is not None:
    raise HTTPException(
       status_code=status.HTTP_400_BAD_REQUEST,
       detail="Email already registered"
    )
 data["password"]=hash_password(data["password"])
 new_user=User(**data)
 db.add(new_user)
 db.commit()
 db.refresh(new_user)

 return new_user



@router.get("/{id}",response_model=UserRead)
def get_user(id:int,db:Session=Depends(get_db),Current=Depends(get_current_user)):

    if Current["user"].id!=id:
       raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Not Authorized")
    cache_key=f"user:{id}"
    print("Checking Redis...")
    cached_user=redis_client.get(cache_key)

    if cached_user:
       print("Cache Hit")
       return json.loads(cached_user)
    print("Cache Miss")
    print("Fetching from PostgreSQL")

    
    user=db.query(User).where(User.id==id).first()
    if not user:
       raise HTTPException(
          status_code=status.HTTP_404_NOT_FOUND,
          detail="user not found"
       )
    
    ans=UserRead.model_validate(user).model_dump()
    redis_client.set(cache_key,json.dumps(ans),ex=60)


    return ans


 

@router.put("/{id}")
def update_user(
   id:int,user:UserUpdate,db:Session=Depends(get_db),Current=Depends(get_current_user)):

    if Current["user"].id!=id:
       raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Not Authorized")

    to_update=db.query(User).where(User.id==id).first()
    if not to_update:
        raise HTTPException(status_code=404, detail="User not found")

    for key,value in user.model_dump(exclude_unset=True).items():
       setattr(to_update,key,value)


    

    db.commit()
    db.refresh(to_update)
    redis_client.delete(f"user:{id}")
    return to_update

   