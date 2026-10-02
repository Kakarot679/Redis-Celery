import enum
from app.database import Base
from sqlalchemy import Column,Integer,String,Boolean,Enum

class UserRole(str,enum.Enum):
    user="user"
    admin="admin"

class User(Base):
    __tablename__="users"

    id=Column(Integer,primary_key=True,index=True)
    name=Column(String)
    city=Column(String)
    email=Column(String,unique=True)
    password=Column(String)
    is_verified=Column(Boolean,default=False)
    role=Column(Enum(UserRole),default=UserRole.user)