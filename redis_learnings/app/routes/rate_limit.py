from fastapi import APIRouter,Request
from app.redis_client import redis_client


router = APIRouter(
    prefix="/rate-limit",
    tags=["Rate Limiter"]
)

@router.get("/")
def rate_limit(request:Request):
    client_ip=request.client.host
    key = f"rate_limit:{client_ip}"

    count = redis_client.incr(key)

    if count == 1:
        redis_client.expire(key, 30)

    if count > 5:
        return {
        "message": "Too many requests"
    }

    return {
    "count": count
} 

#     count = redis_client.incr("counter")
#     if count==1:
#         redis_client.expire("counter", 30)

#     if count>5:
#         return{
#             "message":"too many request"
#         }

#     return {
#         "count": count
#     }