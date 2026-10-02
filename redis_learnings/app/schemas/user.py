from pydantic import BaseModel,EmailStr,Field
from app.models.user import UserRole


class UserBase(BaseModel):
    name:str
    city:str
    email:EmailStr

class UserCreate(UserBase):
    password:str=Field(min_length=8)

class UserRead(UserBase):
    role:UserRole
    id:int
    is_verified:bool

    class Config:
        from_attributes=True
class UserUpdate(UserBase):
    pass
