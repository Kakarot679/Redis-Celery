from app.database import Base
from sqlalchemy import Column,Integer,String

class User(Base):
    __tablename__="users"

    id=Column(Integer,primary_key=True,index=True)
    name=Column(String)
    city=Column(String)
    email=Column(String,unique=True)