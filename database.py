import asyncpg
from datetime import datetime, timedelta
from config import DATABASE_URL


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL)
        await self.create_tables()

    async def create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT DEFAULT '',
                    full_name TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS movies (
                    id SERIAL PRIMARY KEY,
                    code TEXT UNIQUE,
                    title TEXT NOT NULL,
                    year TEXT DEFAULT '',
                    genre TEXT DEFAULT '',
                    rating TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    file_id TEXT DEFAULT '',
                    link TEXT DEFAULT '',
                    is_premium BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS subscriptions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    started_at TIMESTAMP DEFAULT NOW(),
                    expires_at TIMESTAMP NOT NULL,
                    UNIQUE(user_id)
                );

                CREATE TABLE IF NOT EXISTS views (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    movie_id INT NOT NULL,
                    viewed_at TIMESTAMP DEFAULT NOW()
                );
            """)

    # ─── USERS ───────────────────────────────────────────────────────────────

    async def add_user(self, telegram_id: int, username: str, full_name: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (telegram_id, username, full_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (telegram_id) DO UPDATE
                SET username = $2, full_name = $3
            """, telegram_id, username, full_name)

    async def get_user(self, telegram_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT *, (SELECT COUNT(*) FROM views WHERE user_id = $1) as views FROM users WHERE telegram_id = $1",
                telegram_id
            )
            return dict(row) if row else None

    async def get_all_users(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT u.*, 
                       CASE WHEN s.expires_at > NOW() THEN TRUE ELSE FALSE END as has_sub
                FROM users u
                LEFT JOIN subscriptions s ON s.user_id = u.telegram_id
                ORDER BY u.created_at DESC
            """)
            return [dict(r) for r in rows]

    # ─── MOVIES ──────────────────────────────────────────────────────────────

    async def add_movie(self, title, year, genre, rating, description, is_premium) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO movies (title, year, genre, rating, description, is_premium)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
            """, title, year, genre, rating, description, is_premium)
            return row['id']

    async def set_movie_code(self, movie_id: int, code: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE movies SET code = $1 WHERE id = $2",
                code, movie_id
            )

    async def get_movie_by_code(self, code: str):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM movies WHERE code = $1", code
            )
            return dict(row) if row else None

    async def get_free_movies(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM movies WHERE is_premium = FALSE ORDER BY created_at DESC"
            )
            return [dict(r) for r in rows]

    async def get_premium_movies(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM movies WHERE is_premium = TRUE ORDER BY created_at DESC"
            )
            return [dict(r) for r in rows]

    async def delete_movie_by_code(self, code: str) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM movies WHERE code = $1", code
            )
            return result != "DELETE 0"

    # ─── SUBSCRIPTIONS ───────────────────────────────────────────────────────

    async def give_subscription(self, user_id: int, days: int):
        expires = datetime.now() + timedelta(days=days)
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO subscriptions (user_id, expires_at)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE
                SET expires_at = GREATEST(subscriptions.expires_at, $2),
                    started_at = NOW()
            """, user_id, expires)

    async def check_subscription(self, user_id: int) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT expires_at FROM subscriptions WHERE user_id = $1 AND expires_at > NOW()",
                user_id
            )
            return row is not None

    async def get_subscription(self, user_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM subscriptions WHERE user_id = $1 AND expires_at > NOW()",
                user_id
            )
            return dict(row) if row else None

    # ─── VIEWS & STATS ───────────────────────────────────────────────────────

    async def log_view(self, user_id: int, movie_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO views (user_id, movie_id) VALUES ($1, $2)",
                user_id, movie_id
            )

    async def get_stats(self):
        async with self.pool.acquire() as conn:
            users = await conn.fetchval("SELECT COUNT(*) FROM users")
            movies = await conn.fetchval("SELECT COUNT(*) FROM movies")
            premium_users = await conn.fetchval(
                "SELECT COUNT(*) FROM subscriptions WHERE expires_at > NOW()"
            )
            today_views = await conn.fetchval(
                "SELECT COUNT(*) FROM views WHERE viewed_at::date = CURRENT_DATE"
            )
            return {
                'users': users,
                'movies': movies,
                'premium_users': premium_users,
                'today_views': today_views
            }


db = Database()
