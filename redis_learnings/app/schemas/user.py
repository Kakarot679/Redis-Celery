from pydantic import BaseModel,EmailStr


class UserBase(BaseModel):
    name:str
    city:str
    email:EmailStr

class UserCreate(UserBase):
    password:str

class UserRead(UserBase):
    id:int
    is_verified:bool

    class Config:
        from_attributes=True
class UserUpdate(UserBase):
    pass
