import os
import asyncio
import random
from typing import Dict, List, Optional
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

store: Dict[str, str] = {}

FOLLOWERS_ENV = os.getenv("FOLLOWERS", "")
FOLLOWER_URLS: List[str] = [
    url.strip() for url in FOLLOWERS_ENV.split(",") if url.strip()
]
DEFAULT_WRITE_QUORUM = int(os.getenv("WRITE_QUORUM", "3"))
MIN_DELAY_MS = int(os.getenv("MIN_DELAY_MS", "0"))
MAX_DELAY_MS = int(os.getenv("MAX_DELAY_MS", "1000"))
REPLICATION_TIMEOUT = float(os.getenv("REPLICATION_TIMEOUT", "5.0"))

class HTTPClientManager:
    def __init__(self):
        self.client = None
    
    async def get_client(self):
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=REPLICATION_TIMEOUT,
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
                follow_redirects=True,
            )
        return self.client
    
    async def close(self):
        if self.client:
            await self.client.aclose()

http_client_manager = HTTPClientManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Leader starting with {len(FOLLOWER_URLS)} followers")
    yield
    await http_client_manager.close()

app = FastAPI(title="KV Leader", lifespan=lifespan)

class KVItem(BaseModel):
    key: str
    value: str

@app.get("/health")
async def health():
    return {
        "status": "ok", 
        "role": "leader", 
        "followers": len(FOLLOWER_URLS),
        "quorum": DEFAULT_WRITE_QUORUM,
    }

@app.get("/kv/{key}")
async def get_key(key: str):
    if key not in store:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"key": key, "value": store[key]}

async def replicate_to_follower(follower_url: str, key: str, value: str) -> bool:
    if MAX_DELAY_MS > 0:
        delay_ms = random.randint(MIN_DELAY_MS, MAX_DELAY_MS)
        await asyncio.sleep(delay_ms / 1000.0)
    
    replication_url = f"{follower_url}/replicate"
    
    try:
        client = await http_client_manager.get_client()
        resp = await client.post(
            replication_url,
            json={"key": key, "value": value},
            timeout=REPLICATION_TIMEOUT
        )
        
        if resp.status_code == 200:
            return True
        else:
            logger.warning(f"Replication failed to {follower_url}: HTTP {resp.status_code}")
            return False
            
    except httpx.TimeoutException:
        logger.warning(f"Timeout replicating to {follower_url}")
        return False
    except httpx.ConnectError as e:
        logger.warning(f"Connection error to {follower_url}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error replicating to {follower_url}: {e}")
        return False

@app.post("/write")
async def write(
    item: KVItem,
    write_quorum: Optional[int] = Query(
        None,
        description="Optional override for write quorum",
    ),
):
    effective_quorum = write_quorum if write_quorum is not None else DEFAULT_WRITE_QUORUM
    
    if effective_quorum > len(FOLLOWER_URLS):
        effective_quorum = len(FOLLOWER_URLS)
    effective_quorum = max(0, effective_quorum)
    
    logger.info(f"Write request: key={item.key}, quorum={effective_quorum}")
    
    store[item.key] = item.value
    
    if not FOLLOWER_URLS or effective_quorum == 0:
        logger.info(f"Write completed instantly")
        return {
            "status": "ok",
            "key": item.key,
            "value": item.value,
            "acks": 0,
            "quorum": effective_quorum,
            "total_followers": len(FOLLOWER_URLS),
        }
    
    replication_tasks = []
    for follower_url in FOLLOWER_URLS:
        task = asyncio.create_task(
            replicate_to_follower(follower_url, item.key, item.value)
        )
        replication_tasks.append(task)
    
    successful_replications = 0
    failed_replications = 0
    completed_count = 0
    
    max_delay_seconds = MAX_DELAY_MS / 1000.0 if MAX_DELAY_MS > 0 else 0
    total_timeout = REPLICATION_TIMEOUT + max_delay_seconds + 2.0
    
    try:
        start_time = asyncio.get_event_loop().time()
        
        while replication_tasks and successful_replications < effective_quorum:
            done, replication_tasks = await asyncio.wait(
                replication_tasks,
                timeout=total_timeout,
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in done:
                completed_count += 1
                try:
                    if await task:
                        successful_replications += 1
                        
                        if successful_replications >= effective_quorum:
                            elapsed = asyncio.get_event_loop().time() - start_time
                            logger.info(f"Write completed with quorum: {successful_replications}/{effective_quorum}")
                            
                            for remaining_task in replication_tasks:
                                remaining_task.cancel()
                            
                            return {
                                "status": "ok",
                                "key": item.key,
                                "value": item.value,
                                "acks": successful_replications,
                                "quorum": effective_quorum,
                                "total_followers": len(FOLLOWER_URLS),
                                "elapsed_seconds": round(elapsed, 3),
                            }
                    else:
                        failed_replications += 1
                        
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error processing task: {e}")
                    failed_replications += 1
            
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > total_timeout:
                logger.warning(f"Timeout waiting for quorum")
                break
                
    except asyncio.TimeoutError:
        logger.warning(f"Replication timeout")
    
    elapsed = asyncio.get_event_loop().time() - start_time if 'start_time' in locals() else 0
    
    if successful_replications >= effective_quorum:
        logger.info(f"Write completed with quorum: {successful_replications}/{effective_quorum}")
        return {
            "status": "ok",
            "key": item.key,
            "value": item.value,
            "acks": successful_replications,
            "quorum": effective_quorum,
            "total_followers": len(FOLLOWER_URLS),
            "elapsed_seconds": round(elapsed, 3),
        }
    else:
        logger.warning(f"Write failed: only {successful_replications}/{effective_quorum} acks")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "reason": "insufficient_acks",
                "key": item.key,
                "value": item.value,
                "acks": successful_replications,
                "failed": failed_replications,
                "completed": completed_count,
                "required_quorum": effective_quorum,
                "total_followers": len(FOLLOWER_URLS),
                "elapsed_seconds": round(elapsed, 3),
            },
        )

@app.get("/debug/store")
async def debug_store():
    return {
        "count": len(store),
        "store": store,
    }

@app.get("/debug/followers")
async def debug_followers():
    return {
        "followers": FOLLOWER_URLS,
        "count": len(FOLLOWER_URLS),
        "default_quorum": DEFAULT_WRITE_QUORUM,
        "delay_range_ms": f"{MIN_DELAY_MS}-{MAX_DELAY_MS}",
    }