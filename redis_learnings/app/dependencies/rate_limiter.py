from fastapi import Request,HTTPException,status
from app.redis_client import redis_client


def rate_limit(request:Request):
    client_ip=request.client.host
    key = f"rate_limit:{client_ip}"

    count = redis_client.incr(key)

    if count == 1:
        redis_client.expire(key, 30)

    if count > 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many requests "
        )


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