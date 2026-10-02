from app.redis_client import redis_client

pubsub=redis_client.pubsub()
pubsub.subscribe("news")

print("Listening on news")

# {"type": "message", "pattern": None, "channel": "news", "data": "hello from another terminal"}


for message in pubsub.listen():
    if message["type"]=="message":
        print("Received:",message["data"])