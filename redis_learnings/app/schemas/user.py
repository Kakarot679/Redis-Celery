from pydantic import BaseModel,EmailStr


class UserBase(BaseModel):
    name:str
    city:str
    email:EmailStr

class UserCreate(UserBase):
    pass

class UserRead(UserBase):
    id:int

    class Config:
        from_attributes=True
class UserUpdate(UserBase):
    pass