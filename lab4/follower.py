import os
from typing import Dict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

store: Dict[str, str] = {}
FOLLOWER_ID = os.getenv("FOLLOWER_ID", "unknown")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Follower {FOLLOWER_ID} starting")
    yield
    logger.info(f"Follower {FOLLOWER_ID} shutting down")

app = FastAPI(title=f"KV Follower {FOLLOWER_ID}", lifespan=lifespan)

class KVItem(BaseModel):
    key: str
    value: str

@app.get("/health")
async def health():
    return {
        "status": "ok", 
        "role": "follower", 
        "id": FOLLOWER_ID,
        "keys_count": len(store),
    }

@app.get("/kv/{key}")
async def get_key(key: str):
    if key not in store:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"key": key, "value": store[key]}

@app.post("/replicate")
async def replicate(item: KVItem):
    try:
        old_value = store.get(item.key)
        store[item.key] = item.value
        logger.info(f"Replicated: {item.key}={item.value}")
        return {
            "status": "ok",
            "key": item.key,
            "value": item.value,
            "follower_id": FOLLOWER_ID,
            "replaced": old_value is not None,
        }
    except Exception as e:
        logger.error(f"Replication failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/store")
async def debug_store():
    return {
        "follower_id": FOLLOWER_ID,
        "count": len(store),
        "store": store,
    }