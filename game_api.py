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

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=6379,
    decode_responses=True
)

app = FastAPI()


class InitRequest(BaseModel):
    game_id: str
    size: int


class ClickRequest(BaseModel):
    game_id: str
    x: int
    y: int


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


@app.post("/game/init")
def init_game(request: InitRequest):
    state = engine.Field(request.size)

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
