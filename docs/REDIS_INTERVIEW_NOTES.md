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

## 7. Common Interview Questions
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

---

## 8. Common Mistakes
- Forgetting to set TTL → cache entries live forever, causing stale data / memory bloat.
- Setting `EXPIRE` on every request in a rate limiter → window never actually resets (sliding, not fixed).
- Storing Python objects directly without `json.dumps()` → Redis client errors or stores garbage.
- Not invalidating cache after DB writes → stale reads until TTL expiry.
- Using `KEYS *` in production → blocks the single-threaded server (use `SCAN` instead).
- Treating Redis as a primary durable database without understanding persistence trade-offs (RDB/AOF).
- Not namespacing keys (e.g. `user:{id}`, `rate_limit:{ip}`) → key collisions across features.
