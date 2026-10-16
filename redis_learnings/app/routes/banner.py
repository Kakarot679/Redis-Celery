import time
import uuid
import redis
from fastapi import APIRouter, HTTPException
from ..redis_client import redis_client

router = APIRouter()

_release_lock_script = redis_client.register_script("""
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
""")


@router.post("/lock/acquire")
def acquire_lock():
    owner = str(uuid.uuid4())
    acquired = redis_client.set("lock:daily_digest", owner, nx=True, ex=30)
    if not acquired:
        raise HTTPException(409, "Lock already held by someone else")
    return {"message": "Lock acquired", "owner": owner}


@router.post("/lock/release")
def release_lock(owner: str):
    result = _release_lock_script(keys=["lock:daily_digest"], args=[owner])
    if result == 0:
        raise HTTPException(409, "Not your lock (expired or already released)")
    return {"message": "Lock released"}


@router.post("/send-daily-digest")
def send_daily_digest():
    owner = str(uuid.uuid4())
    acquired = redis_client.set("lock:daily_digest", owner, nx=True, ex=30)
    if not acquired:
        return {"message": "Another server is already sending the digest, skipping"}

    try:
        # --- the actual protected work goes here ---
        time.sleep(10)  # simulating "building and sending the digest email"
        return {"message": "Digest sent"}
    finally:
        _release_lock_script(keys=["lock:daily_digest"], args=[owner])


@router.post("/stock/init")
def init_stock(quantity: int = 10):
    redis_client.set("stock", quantity)
    return {"stock": quantity}


@router.post("/buy-unsafe")
def buy_unsafe():
    stock = int(redis_client.get("stock") or 0)
    if stock <= 0:
        raise HTTPException(400, "Out of stock")

    time.sleep(2)  # artificial delay to make the race condition easy to trigger by hand

    redis_client.set("stock", stock - 1)
    return {"message": "Purchased", "remaining": stock - 1}


@router.post("/buy-safe")
def buy_safe():
    with redis_client.pipeline() as pipe:
        while True:
            try:
                pipe.watch("stock")
                stock = int(pipe.get("stock") or 0)
                if stock <= 0:
                    pipe.unwatch()
                    raise HTTPException(400, "Out of stock")

                time.sleep(2)  # same artificial delay, to prove this version is safe under the same race window

                pipe.multi()
                pipe.set("stock", stock - 1)
                pipe.execute()
                return {"message": "Purchased", "remaining": stock - 1}
            except redis.WatchError:
                continue  # "stock" changed under us between watch() and execute() - retry from scratch


@router.post("/banner")
def create_banner(message: str):
    redis_client.set("banner", message,ex=30)

    return {
        "message": "Banner Stored"
    }
@router.get("/banner")
def get_banner():
    banner=redis_client.get("banner")

    return {
        "banner": banner
    }


@router.delete("/banner")
def delete_banner():
    deleted=redis_client.delete("banner")

    return{
        "deleted":deleted
    }

@router.get("/banner_exist")
def exist_banner():
    exist_banner=redis_client.exists("banner")

    
    return{
        "exists":bool(exist_banner)
    }





@router.post("/hash-user")
def create_user():
    redis_client.hset(
        "user:1",
        mapping={
            "name":"Hardik",
            "city":"Ghaziabad",
            "email":"hard@gmail.com"

        }
    )
    return{
        "user":"user_created"
    }

@router.get("/hash-user")
def get_user():
    user=redis_client.hgetall("user:1")

    return {
        "user_details":user
    }

@router.post("/notification")
def add_notification(message:str):

    redis_client.lpush(
        "notification",
        message
    )

    return{
        "message":"Notification Added"
    }

@router.get("/notification")
def get_notification():

    notifications=redis_client.lrange(
        "notification",0,-1
    )

    return {
        "notification":notifications
    }

@router.delete("/notification/left")
def delete_notification_left():
    deleted=redis_client.lpop("notification")

    return {
        "deleted":deleted
    }
@router.delete("/notification/right")
def delete_notification_right():
    deleted=redis_client.rpop("notification")

    return {
        "deleted":deleted
    }

#SETS SADD online_users Hardik IN TERMINAL REDIS CLI
# 127.0.0.1:6379> SISMEMBER online_users A
# (integer) 1
# 127.0.0.1:6379> 

@router.post("/online")
def add_online_user(name: str):

    redis_client.sadd(
        "online_users",
        name
    )

    return {
        "message": "User Added"
    }
@router.get("/online")
def get_online_users():

    users = redis_client.smembers(
        "online_users"
    )

    return {
        "users": list(users)
    }

@router.get("/online/check")
def check_user(name: str):

    exists = redis_client.sismember(
        "online_users",
        name
    )

    return {
        "exists": exists
    }


@router.delete("/online")
def remove_user(name: str):

    redis_client.srem(
        "online_users",
        name
    )

    return {
        "message":"Removed"
    }

# ZADD leaderboard 250 Hardik
# ZRANGE leaderboard 0 -1 WITHSCORES
# ZREVRANGE leaderboard 0 -1 WITHSCORES


@router.post("/leaderboard")
def add_player(name: str, score: int):

    redis_client.zadd(
        "leaderboard",
        {
            name: score
        }
    )

    return {
        "message": "Player Added"
    }

@router.get("/leaderboard")
def get_player():
    player=redis_client.zrevrange(
        "leaderboard",0,-1,
        withscores=True

    )

    return{
        "leaderboard":player
    }