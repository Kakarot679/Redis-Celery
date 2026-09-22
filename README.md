# Redis Learnings

A FastAPI + PostgreSQL + Redis playground project for learning core Redis data
structures and patterns: caching (cache-aside), rate limiting, and the basic
Redis commands, applied through real API endpoints.

## Stack
- **FastAPI** — web framework
- **PostgreSQL** — primary database (via SQLAlchemy)
- **Redis** — cache, rate limiter, and data-structure playground
- **Docker Compose** — local Redis + Postgres

## Project Structure
```
redis_learnings/
  app/
    config.py              # env config (DATABASE_URL, REDIS_URL)
    database.py             # SQLAlchemy engine/session
    redis_client.py         # Redis connection
    main.py                 # FastAPI app entrypoint
    models/                 # SQLAlchemy models
    schemas/                 # Pydantic schemas
    dependencies/
      rate_limiter.py        # Redis-based fixed-window rate limiter
    routes/
      user.py                # user CRUD + cache-aside example
      banner.py               # string/hash/list/set/sorted-set demos
      rate_limit.py            # standalone rate-limit demo endpoint
docs/
  cheatsheet.md              # quick Redis command cheatsheet
  REDIS_INTERVIEW_NOTES.md    # interview-ready revision notes
docker-compose.yml            # Redis + Postgres containers
requirements.txt
.env.example
```

## Setup

1. Clone and enter the project:
   ```bash
   git clone <repo-url>
   cd redis
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   venv\Scripts\activate       # Windows
   source venv/bin/activate    # macOS/Linux
   pip install -r requirements.txt
   ```

3. Copy the example env file and adjust if needed:
   ```bash
   cp .env.example .env
   ```

4. Start Redis and Postgres:
   ```bash
   docker-compose up -d
   ```

5. Run the API:
   ```bash
   uvicorn app.main:app --reload --app-dir redis_learnings
   ```

6. Explore the interactive docs at `http://localhost:8000/docs`.

## Key Endpoints
| Endpoint | Demonstrates |
|---|---|
| `POST/GET/DELETE /banner` | String `SET`/`GET`/`DEL`/`EXISTS` with TTL |
| `POST/GET /user` (hash) | `HSET`/`HGETALL` |
| `POST/GET/DELETE /notification` | `LPUSH`/`LRANGE`/`LPOP`/`RPOP` |
| `POST/GET/DELETE /online` | `SADD`/`SMEMBERS`/`SISMEMBER`/`SREM` |
| `POST/GET /leaderboard` | `ZADD`/`ZREVRANGE` |
| `GET /user/{id}` | Cache-aside pattern (Postgres + Redis) |
| `GET /rate-limit` | Fixed-window rate limiter (`INCR` + `EXPIRE`, HTTP 429) |

## Notes
See [`docs/REDIS_INTERVIEW_NOTES.md`](docs/REDIS_INTERVIEW_NOTES.md) for a
condensed interview-revision summary, and
[`docs/cheatsheet.md`](docs/cheatsheet.md) for a quick command reference.
# Redis-Celery
