import json
import os

import fastapi
from fastapi import FastAPI
from pydantic import BaseModel

import redis

#
# Ваш игровой движок
#
# Должен содержать:
#
# field(size, custom_field=None)
# process_click(state,x,y)
#
import engine

REDIS_HOST = os.getenv(
    "REDIS_HOST",
    "redis"
)
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_DB = os.getenv("MYSQL_DB")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=6379,
    decode_responses=True
)

import pymysql

mysql_enabled = all([
    MYSQL_HOST,
    MYSQL_DB,
    MYSQL_USER,
    MYSQL_PASSWORD
])

mysql_conn = None

if mysql_enabled:
    mysql_conn = pymysql.connect(host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD,
                                 database=MYSQL_DB, autocommit=True)

app = FastAPI()


class InitRequest(BaseModel):
    game_id: str
    size: int


class ClickRequest(BaseModel):
    game_id: str
    x: int
    y: int


class HiScoreRequest(BaseModel):
    game_id: str
    name: str


def ensure_table_exists():
    """Create game_results table if it doesn't exist."""
    if not mysql_enabled:
        return

    try:
        with mysql_conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS game_results (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    steps INT NOT NULL,
                    size INT NOT NULL,
                    finished_at DATETIME NOT NULL
                )
                """
            )
    except Exception as e:
        print(f"MySQL table creation error: {e}")


def save_result(name: str, state):
    if not mysql_enabled:
        return

    if name is None:
        return

    if state is None:
        return

    # Ensure table exists before saving
    ensure_table_exists()

    try:
        with mysql_conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO game_results (
                    name,
                    steps,
                    size,
                    finished_at
                )
                VALUES (%s, %s, %s, NOW())
                """,
                (
                    name,
                    state.steps,
                    len(state.squares)
                )
            )
    except Exception as e:
        print(f"MySQL save error: {e}")


def save_state(game_id, state):
    redis_client.set(
        f"game:{game_id}",
        json.dumps(state.to_dict())
    )


def load_state(game_id):
    raw = redis_client.get(f"game:{game_id}")

    if raw is None:
        return None

    return engine.Field.from_dict(json.loads(raw))


def get_top_hiscores(size: int = 10, limit: int = 3):
    """Get top N scores (fewest steps) from database."""
    if not mysql_enabled:
        return []

    try:
        with mysql_conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT name, steps, size
                FROM game_results
                WHERE size = %s
                ORDER BY steps ASC
                LIMIT %s
                """,
                (size, limit,)
            )
            results = cursor.fetchall()
            return [
                {
                    "name": row[0],
                    "steps": row[1],
                    "size": row[2]
                }
                for row in results
            ]
    except Exception as e:
        print(f"MySQL get_top_hiscores error: {e}")
        return []


@app.post("/game/init")
def init_game(request: InitRequest):
    state = engine.Field(request.size)

    save_state(
        request.game_id,
        state
    )
    # print(state)
    return {
        "success": True,
        "matrix": [[s.state for s in row] for row in state.squares],
        "win": state.even(),
        "step": state.steps,
        "top_hiscores": get_top_hiscores(3)
    }


@app.post("/game/click")
def click(request: ClickRequest):
    state = load_state(
        request.game_id
    )

    if state is None:
        return {
            "success": False,
            "error": "game_not_found"
        }

    state.revert(
        request.y,
        request.x
    )

    save_state(
        request.game_id,
        state
    )
    print(state)
    return {
        "success": True,
        "matrix": [[s.state for s in row] for row in state.squares],
        "win": state.even(),
        "step": state.steps
    }


@app.post("/game/add_hiscore")
def add_hiscore(request: HiScoreRequest):
    state = load_state(
        request.game_id
    )

    if state is None:
        return {
            "success": False,
            "error": "game_not_found"
        }

    save_result(request.name, state)

    redis_client.delete(f"game:{request.game_id}")

    return {
        "success": True,
        "step": state.steps,
        "top_hiscores": get_top_hiscores(3)
    }
