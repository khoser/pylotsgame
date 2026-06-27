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
    colors: dict | None = None


class HiScoreRequest(BaseModel):
    game_id: str
    name: str


def ensure_table_exists():
    """Create game_results and game_moves tables if they don't exist."""
    if not mysql_enabled:
        return

    try:
        with mysql_conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS game_results (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    game_id VARCHAR(255) NOT NULL UNIQUE,
                    name VARCHAR(255) NOT NULL,
                    steps INT NOT NULL,
                    size INT NOT NULL,
                    finished_at DATETIME NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS game_moves (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    game_id VARCHAR(255) NOT NULL,
                    name VARCHAR(255),
                    move_number INT NOT NULL,
                    field_state JSON NOT NULL,
                    created_at DATETIME NOT NULL
                )
                """
            )
    except Exception as e:
        print(f"MySQL table creation error: {e}")


def save_result(game_id: str, name: str, state):
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
                    game_id,
                    name,
                    steps,
                    size,
                    finished_at
                )
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (
                    game_id,
                    name,
                    state.steps,
                    len(state.squares)
                )
            )
    except Exception as e:
        print(f"MySQL save error: {e}")


def save_move_to_redis(game_id: str, state, colors: dict = None):
    """Append the current field state to Redis list after a move."""
    field_data = json.dumps({
        "steps": state.steps,
        "matrix": [[s.state for s in row] for row in state.squares],
        "colors": colors or {}
    })
    redis_client.rpush(f"game_moves:{game_id}", field_data)


def save_moves_to_mysql(game_id: str, name: str):
    """Read all move states from Redis and save to MySQL."""
    if not mysql_enabled:
        return

    ensure_table_exists()

    try:
        moves = redis_client.lrange(f"game_moves:{game_id}", 0, -1)
        
        if not moves:
            return

        with mysql_conn.cursor() as cursor:
            for move_number, move_json in enumerate(moves, 1):
                cursor.execute(
                    """
                    INSERT INTO game_moves (
                        game_id,
                        name,
                        move_number,
                        field_state,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, NOW())
                    """,
                    (
                        game_id,
                        name,
                        move_number,
                        move_json
                    )
                )
    except Exception as e:
        print(f"MySQL save_moves error: {e}")




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


def get_top_hiscores(size: int, limit: int = 3):
    """Get top N scores (fewest steps) for a specific board size."""
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
                (size, limit)
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
    while not state.solvable():
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
        "top_hiscores": get_top_hiscores(request.size, 3)
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
    
    save_move_to_redis(request.game_id, state, request.colors)
    
    # print(state)
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

    save_result(request.game_id, request.name, state)
    
    save_moves_to_mysql(request.game_id, request.name)

    redis_client.delete(f"game:{request.game_id}")
    redis_client.delete(f"game_moves:{request.game_id}")

    return {
        "success": True,
        "step": state.steps,
        "top_hiscores": get_top_hiscores(len(state.squares), 3)
    }
