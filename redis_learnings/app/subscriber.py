import asyncio
from app.redis_client import redis_client
from app.utils.email import send_email

# --- Previous approach: Pub/Sub (fire-and-forget, lost if no subscriber at publish time) ---
# import json
#
# pubsub=redis_client.pubsub()
# pubsub.subscribe("new_registration")
#
# print("Listening on news")
#
# for message in pubsub.listen():
#     if message["type"]=="message":
#         data = json.loads(message["data"])
#         print("New registration:", data["email"])
#         asyncio.run(send_email(
#             data["email"],
#             "Welcome!",
#             f"Hi {data['name']}, thanks for signing up."
#         ))

STREAM = "registrations"
GROUP = "welcome_email_workers"
CONSUMER = "worker1"
MIN_IDLE_MS = 30000  # an entry pending longer than this is treated as abandoned by a crashed consumer

try:
    redis_client.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
except Exception:
    pass  # group already exists, fine

print("Listening on stream 'registrations'...")


def process(entry_id, fields):
    print("New registration:", fields["email"])
    asyncio.run(send_email(
        fields["email"],
        "Welcome!",
        f"Hi {fields['name']}, thanks for signing up."
    ))
    redis_client.xack(STREAM, GROUP, entry_id)


while True:
    # Recover entries abandoned by a crashed/stuck consumer before reading new ones
    _, claimed, _ = redis_client.xautoclaim(STREAM, GROUP, CONSUMER, min_idle_time=MIN_IDLE_MS, start_id="0-0")
    for entry_id, fields in claimed:
        print("Recovered abandoned entry:", entry_id)
        process(entry_id, fields)

    entries = redis_client.xreadgroup(GROUP, CONSUMER, {STREAM: ">"}, count=10, block=5000)
    if not entries:
        continue
    for stream_name, messages in entries:
        for entry_id, fields in messages:
            process(entry_id, fields)