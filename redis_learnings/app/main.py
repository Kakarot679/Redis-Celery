from fastapi import FastAPI
from app.redis_client import redis_client
from app.database import Base, engine
from app.models.user import User
from app.routes.banner import router as banner_router
from app.routes.user import router as user_router
from app.routes.rate_limit import router as rate_router


Base.metadata.create_all(bind=engine)

app=FastAPI()
app.include_router(banner_router)
app.include_router(user_router)
app.include_router(rate_router)

# @app.on_event("startup")
# def startup():
#     try:
#         redis_client.ping()
#         print("connected to redis ")
#     except Exception as e:
#         print(f"Redis connection failed: {e}")




@app.get("/")
def home():
    return {
        "message":"Redis Learning"
    }


# @app.get("/redis")
# def test():
#     redis_client.set("course", "Redis")
#     return {"message": "Stored"}