from app.redis_client import redis_client
import redis
from fastapi import HTTPException 


buy_script=redis_client.register_script("""
local stock=tonumber(redis.call('GET',KEYS[1]))

if stock > 0 then 
redis.call('DECR',KEYS[1])
return stock - 1
else
return - 1

end
"""
                                        
)

result=buy_script(keys=["stock"])

if result ==- 1:
    raise HTTPException(400,"out of stock ")

return {"message": "Purchased", "remaining": result}

# EVAL "local stock = tonumber(redis.call('GET', KEYS[1])) local amount = tonumber(ARGV[1]) if stock >= amount then redis.call('DECRBY', KEYS[1], amount) return stock - amount else return -1 end" 1 stock 2

# SCRIPT LOAD "local stock = tonumber(redis.call('GET', KEYS[1])) if stock > 0 then redis.call('DECR', KEYS[1]) return stock - 1 else return -1 end"