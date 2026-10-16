import redis
from app.config import REDIS_URL

# --- Cluster version tried for learning purposes - app not actually compatible (login's multi-key pipeline hits CROSSSLOT) ---
# from redis.cluster import RedisCluster
# redis_client=RedisCluster(
#     startup_nodes=[redis.cluster.ClusterNode("redis-node-1", 7000),redis.cluster.ClusterNode("redis-node-2", 7001),redis.cluster.ClusterNode("redis-node-3", 7002)],
#     decode_responses=True
# )

redis_client=redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_timeout=10
)