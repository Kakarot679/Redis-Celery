from fastapi import APIRouter,Depends,HTTPException
from app.models.user import User
from app.schemas.user import UserCreate,UserRead,UserUpdate
from sqlalchemy.orm import Session
from app.database import get_db
from app.redis_client import redis_client
from app.dependencies.rate_limiter import rate_limit
import json

router = APIRouter(
    prefix="/user",
    tags=["user_router"],
    dependencies=[Depends(rate_limit)]
)


@router.post("/" ,response_model=UserRead)
def create_user(user:UserCreate,db:Session=Depends(get_db)):
 
 new_user=User(**user.model_dump())
 db.add(new_user)
 db.commit()
 db.refresh(new_user)

 return new_user



@router.get("/{id}",response_model=UserRead)
def get_user(id:int,db:Session=Depends(get_db)):
    cache_key=f"user:{id}"
    print("Checking Redis...")
    cached_user=redis_client.get(cache_key)

    if cached_user:
       print("Cache Hit")
       return json.loads(cached_user)
    print("Cache Miss")
    print("Fetching from PostgreSQL")
    user=db.query(User).where(User.id==id).first()
    ans=UserRead.model_validate(user).model_dump()
    redis_client.set( cache_key,json.dumps(ans))


    return user

 
 

@router.put("/{id}")
def update_user(
   id:int,user:UserUpdate,db:Session=Depends(get_db)):

    to_update=db.query(User).where(User.id==id).first()
    if not to_update:
        raise HTTPException(status_code=404, detail="User not found")

    for key,value in user.model_dump(exclude_unset=True).items():
       setattr(to_update,key,value)


    

    db.commit()
    db.refresh(to_update)
    redis_client.delete(f"user:{id}")
    return to_update

   