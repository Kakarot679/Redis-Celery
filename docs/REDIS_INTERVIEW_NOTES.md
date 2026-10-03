# Redis Interview Notes (10-min Revision)

## 1. Redis Basics
- In-memory key-value data store, used as cache, session store, rate limiter, queue, leaderboard.
- Single-threaded event loop → very fast (sub-ms), commands are atomic.
- Data optionally persisted to disk (RDB snapshots / AOF log), but primarily used for speed, not durability.

---

## 2. Commands

### SET
- **Syntax:** `SET key value [EX seconds]`
- **Purpose:** Store a string value, optionally with expiry.
- **Example:** `redis_client.set("banner", message, ex=30)`

### GET
- **Syntax:** `GET key`
- **Purpose:** Retrieve a string value.
- **Example:** `redis_client.get("banner")`

### DEL
- **Syntax:** `DEL key`
- **Purpose:** Delete a key. Returns number of keys deleted.
- **Example:** `redis_client.delete("banner")`

### EXISTS
- **Syntax:** `EXISTS key`
- **Purpose:** Check if key exists (returns 0/1).
- **Example:** `bool(redis_client.exists("banner"))`

### EXPIRE
- **Syntax:** `EXPIRE key seconds`
- **Purpose:** Set a TTL on an existing key.
- **Example:** `redis_client.expire(key, 30)`

### TTL
- **Syntax:** `TTL key`
- **Purpose:** Get remaining seconds before expiry (-1 = no expiry, -2 = key doesn't exist).
- **Example:** `redis_client.ttl("rate_limit:127.0.0.1")`

### INCR
- **Syntax:** `INCR key`
- **Purpose:** Atomically increment integer value by 1 (creates key at 1 if missing).
- **Example:** `count = redis_client.incr(key)`

### HSET
- **Syntax:** `HSET key field value` (or `mapping={...}`)
- **Purpose:** Store fields in a hash (like a dict).
- **Example:** `redis_client.hset("user:1", mapping={"name": "Hardik", "city": "Ghaziabad"})`

### HGET
- **Syntax:** `HGET key field`
- **Purpose:** Get one field's value from a hash.
- **Example:** `redis_client.hget("user:1", "name")`

### HGETALL
- **Syntax:** `HGETALL key`
- **Purpose:** Get all fields + values from a hash.
- **Example:** `redis_client.hgetall("user:1")`

### LPUSH
- **Syntax:** `LPUSH key value`
- **Purpose:** Push a value to the left/head of a list.
- **Example:** `redis_client.lpush("notification", message)`

### LRANGE
- **Syntax:** `LRANGE key start stop`
- **Purpose:** Read a range of list elements (`0 -1` = all).
- **Example:** `redis_client.lrange("notification", 0, -1)`

### SADD
- **Syntax:** `SADD key member`
- **Purpose:** Add a member to a set (unique, unordered).
- **Example:** `redis_client.sadd("online_users", name)`

### SMEMBERS
- **Syntax:** `SMEMBERS key`
- **Purpose:** Get all members of a set.
- **Example:** `list(redis_client.smembers("online_users"))`

### ZADD
- **Syntax:** `ZADD key score member`
- **Purpose:** Add member with a score to a sorted set.
- **Example:** `redis_client.zadd("leaderboard", {"Hardik": 250})`

### ZREVRANGE
- **Syntax:** `ZREVRANGE key start stop [WITHSCORES]`
- **Purpose:** Get sorted set members, highest score first.
- **Example:** `redis_client.zrevrange("leaderboard", 0, -1, withscores=True)`

---

## 3. Redis Data Structures

### String
- **When:** Simple values, counters, cached JSON blobs, flags.
- **Example:** `SET banner "Sale live"` / cached user JSON: `SET user:5 '{"name":"A"}'`

### Hash
- **When:** Object-like data with multiple fields (a user profile) without separate keys per field.
- **Example:** `HSET user:1 name Hardik city Ghaziabad`

### List
- **When:** Ordered data, queues, recent-activity feeds, notifications.
- **Example:** `LPUSH notification "New order"` then `LRANGE notification 0 -1`

### Set
- **When:** Unique unordered membership — online users, tags, dedup.
- **Example:** `SADD online_users Hardik`, check with `SISMEMBER`

### Sorted Set
- **When:** Ranked data — leaderboards, priority queues, time-ordered scores.
- **Example:** `ZADD leaderboard 250 Hardik` → `ZREVRANGE leaderboard 0 -1 WITHSCORES`

### TTL (Time To Live)
- **When:** Auto-expiring data — cache entries, rate-limit windows, temporary banners/sessions.
- **Example:** `SET banner "Hi" EX 30` or `EXPIRE key 30`

---

## 4. Cache-Aside Pattern
- **Cache Hit:** Data found in Redis → return directly, skip DB. (fast path)
- **Cache Miss:** Data not in Redis → query DB, then populate cache.
- **Cache Population:** After DB fetch, `SET` result into Redis (usually with TTL) so next read is a hit.
- **Cache Invalidation:** On update/delete, `DEL` the cache key so stale data isn't served; next read repopulates it.
- **Flow:**
```
Request → Check Redis
            ├── HIT  → return cached data
            └── MISS → query DB → store in Redis → return data

On Update/Delete → write to DB → DEL cache key
```
- **Real example** (`app/routes/user.py`):
  - `GET /user/{id}`: check `redis_client.get(f"user:{id}")` → hit returns `json.loads(cached)`; miss queries Postgres, then `redis_client.set(cache_key, json.dumps(ans))`.
  - `PUT /user/{id}`: updates DB, then `redis_client.delete(f"user:{id}")` to invalidate.

---

## 5. Fixed Window Rate Limiter
- **INCR:** Atomically bump request count per key (e.g. `rate_limit:{client_ip}`).
- **EXPIRE:** Set a TTL (e.g. 30s) on the counter key so it resets after the window.
- **Why EXPIRE only when count == 1:** That's the first request in a new window — setting TTL only then prevents resetting the window on every request (which would let users avoid ever expiring).
- **HTTP 429:** Returned via `HTTPException(status_code=429, ...)` when count exceeds the limit (e.g. > 5).
- **Dependency Injection:** FastAPI `Depends(rate_limit)` runs the limiter before the route logic — reusable across all routes in a router without duplicating code.
- **Per-IP rate limiting:** Key is namespaced by `request.client.host`, so each IP gets its own independent counter/window.

```python
def rate_limit(request: Request):
    key = f"rate_limit:{request.client.host}"
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, 30)
    if count > 5:
        raise HTTPException(status_code=429, detail="too many requests")
```

---

## 6. FastAPI + Redis
- **`json.dumps()`:** Convert a Python dict/object into a JSON string before storing in Redis (Redis strings only hold text/bytes).
- **`json.loads()`:** Parse the JSON string back from Redis into a Python dict when reading a cache hit.
- **Why Redis can't store Python objects directly:** Redis values are strings/bytes (or its native structures like hash/list/set) — it has no concept of a Python class instance, so objects must be serialized (JSON) first.
- **`decode_responses=True`:** Client config so Redis returns Python `str` instead of raw `bytes` — avoids manually calling `.decode()` on every response.

---

## 7. Redis Pub/Sub
- **What it is:** Live broadcast, zero persistence. `PUBLISH channel msg` sends now; `SUBSCRIBE channel` means "notify me of anything published from this moment on."
- **Core limitation:** if nobody is subscribed when you publish, the message is gone forever — no storage, no replay, no memory. Proven live: `PUBLISH news "x"` with no subscriber returns `(integer) 0`, and re-subscribing afterward never shows that message.
- **Fan-out, not work-split:** every subscriber receives every message. If 5 processes all subscribe to the same channel, all 5 react to every event — correct for broadcast use cases, wrong for "divide the work across workers" (causes duplicate processing, e.g. 5 duplicate emails per registration).
- **When Pub/Sub is still the right tool:** anything where only the *latest* value matters and missing old ones is fine — "user is typing" indicators, live cursor position in collaborative editing, "refresh your dashboard" signals. Persisting these would be pure overhead.
- **Commands:**
  - `PUBLISH channel message` → returns number of subscribers that received it.
  - `SUBSCRIBE channel` → blocks, prints `("subscribe", channel, n)` then `("message", channel, data)` for each arrival.
- **Python (redis-py):**
```python
pubsub = redis_client.pubsub()
pubsub.subscribe("news")
for message in pubsub.listen():
    if message["type"] == "message":
        print(message["data"])
```
`pubsub.listen()` also yields a `"subscribe"` confirmation event first — filter on `message["type"] == "message"` to skip it.
- **Real use case built in this project:** `create_user` originally published `{"email","name"}` as JSON on a `"new_registration"` channel; a standalone `subscriber.py` script subscribed and called `send_email(...)` — demonstrates decoupling (the registration route never calls `send_email` directly, doesn't know or care if anything's listening). Later replaced with Streams (see below) once reliability mattered.

---

## 8. Redis Streams
- **What it is:** A durable, ordered, appendable log — fixes Pub/Sub's "miss it and it's gone" problem by actually storing entries in Redis.
- **Core commands:**
  - `XADD stream * field value ...` → append an entry; `*` auto-generates an ID (`<ms-timestamp>-<sequence>`). Returns the ID.
  - `XRANGE stream - +` → read entries in a range (`-` = earliest, `+` = latest). Good for browsing/debugging, not how a worker normally reads.
  - `XLEN stream` → count of entries.
  - `XTRIM` / `XADD ... MAXLEN n` → cap stream size (memory management — streams never expire on their own like TTL'd keys do).
- **Consumer groups — what turns a log into a reliable job queue:**
  - `XGROUP CREATE stream group 0` → create a group reading from the start (`0`), or `$` for "only new entries from now." `mkstream=True` (Python) also creates the stream if missing.
  - `XREADGROUP GROUP group consumer COUNT n STREAMS stream >` → read as a named consumer within a group; `>` means "give me entries not yet delivered to this group." **Each entry goes to exactly one consumer in the group — never duplicated**, even if multiple consumers call this concurrently. Proven live: `consumer1` read 3 entries, `consumer2` immediately after got `(nil)`.
  - `XACK stream group entry_id` → consumer confirms it finished processing; clears the entry from "pending."
  - `XPENDING stream group` → list entries delivered but not yet acknowledged, and which consumer owns each.
  - `XCLAIM stream group new_consumer min_idle_ms entry_id` → reassign a pending entry to a different consumer (crash recovery). Proven live: claimed an entry from `consumer1` to `consumer2`, confirmed via `XPENDING` that ownership transferred, then `XACK`'d it to close it out.
- **Consumer name is just a string** — not a pre-registered entity. "Running more workers" means running more copies of the same script with a different consumer-name string (e.g. `worker1`, `worker2`), not defining multiple consumers inside one script.
- **Python (redis-py):**
```python
try:
    redis_client.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
except Exception:
    pass  # group already exists

while True:
    entries = redis_client.xreadgroup(GROUP, CONSUMER, {STREAM: ">"}, count=10, block=5000)
    if not entries:
        continue
    for stream_name, messages in entries:
        for entry_id, fields in messages:
            # process fields (a plain dict, already structured — no json.dumps needed, unlike Pub/Sub)
            redis_client.xack(STREAM, GROUP, entry_id)
```
- **No `json.dumps` needed:** unlike `PUBLISH` (which only sends one plain string, forcing manual JSON packing), `XADD` natively stores a dict of named fields — `redis_client.xadd("registrations", {"email": e, "name": n})` stores `email`/`name` as real separate fields.
- **Pub/Sub vs Streams, concretely (100 registrations, 5 workers):**
  - Pub/Sub: all 5 workers receive all 100 events → 500 emails sent (5 duplicates per user), and any event during worker downtime is lost forever.
  - Streams + group: the 100 entries are divided across the 5 workers (~20 each) → 100 emails sent total, and any entries from downtime remain queued until a worker comes back online.
- **What a production worker needs beyond this toy version:** retry logic using `XPENDING`/`XCLAIM` on a schedule (not just manual), error handling around the actual work (so one failure doesn't crash the whole loop), multiple real worker processes (not just one), process supervision (systemd/Docker/Kubernetes auto-restart), and logging/metrics. Frameworks like Celery build this hardening on top of a queue backend (can be Redis) so you don't hand-roll it.
- **Real use case built in this project:** replaced the Pub/Sub registration flow — `create_user` now does `XADD` to a `"registrations"` stream; `subscriber.py` is a real worker using `XREADGROUP`/`XACK`, surviving worker downtime without losing any registrations (the actual point of switching).
- **Crash recovery is real code, not just a CLI exercise:** `subscriber.py` calls `XAUTOCLAIM` at the top of every loop iteration — `redis_client.xautoclaim(STREAM, GROUP, CONSUMER, min_idle_time=MIN_IDLE_MS, start_id="0-0")` finds any entry pending longer than `MIN_IDLE_MS` (abandoned by a crashed consumer) and reassigns it to this consumer automatically, before checking for new work. `XAUTOCLAIM` combines `XPENDING` (find stale entries) + `XCLAIM` (reassign) into one call. Without this, Redis does **not** auto-recover abandoned entries — a plain `xreadgroup(..., ">")` loop on a different worker will never see them, since `>` only returns entries never yet delivered to anyone in the group.

---

## 9. Common Interview Questions
1. Why is Redis fast despite being single-threaded?
2. Difference between cache-aside, write-through, and write-behind caching.
3. How would you design a rate limiter with Redis? (fixed window vs sliding window)
4. Why use `EXPIRE` only on the first increment in a counter-based rate limiter?
5. What's the difference between `SET key val EX 30` and `SET` + `EXPIRE`?
6. When would you use a Hash vs storing JSON in a String?
7. How does Redis achieve atomicity for `INCR`?
8. What happens if two requests hit `INCR` at the exact same time — is there a race condition?
9. How do you invalidate cache on updates, and what's the risk of stale cache?
10. What's the difference between List, Set, and Sorted Set — and when would you pick each?
11. Pub/Sub vs Streams — what's the fundamental difference, and when would you pick each?
12. If you run multiple subscribers on the same Pub/Sub channel, what happens — and why is that wrong for a job-queue use case?
13. How does a Redis Stream consumer group guarantee each entry is processed exactly once across multiple workers?
14. What happens if a consumer reads an entry via `XREADGROUP` but crashes before calling `XACK`? How do you recover it?
15. Why doesn't `XADD` need `json.dumps()` the way `PUBLISH` does?
16. Why would you still choose Pub/Sub over Streams for something like a "user is typing" indicator?

---

## 10. Common Mistakes
- Forgetting to set TTL → cache entries live forever, causing stale data / memory bloat.
- Setting `EXPIRE` on every request in a rate limiter → window never actually resets (sliding, not fixed).
- Storing Python objects directly without `json.dumps()` → Redis client errors or stores garbage.
- Not invalidating cache after DB writes → stale reads until TTL expiry.
- Using `KEYS *` in production → blocks the single-threaded server (use `SCAN` instead).
- Treating Redis as a primary durable database without understanding persistence trade-offs (RDB/AOF).
- Not namespacing keys (e.g. `user:{id}`, `rate_limit:{ip}`) → key collisions across features.
- Using Pub/Sub for anything that must not be lost (job processing, financial events) → no persistence, silent data loss if no subscriber is connected at publish time.
- Running multiple Pub/Sub subscribers expecting them to split work → they don't; every subscriber gets every message (use Streams + consumer group instead).
- Letting a Stream grow forever without `MAXLEN`/`XTRIM` → unbounded memory growth (Redis is in-memory; nothing expires automatically like a TTL'd key).
- Never checking `XPENDING` in a real worker → crashed/stuck consumers' entries sit unprocessed forever with no recovery.
