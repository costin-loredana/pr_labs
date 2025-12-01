import asyncio
import os
import pytest
import httpx

LEADER_URL = os.getenv("LEADER_URL", "http://localhost:8000")
FOLLOWER_URLS = [
    os.getenv("FOLLOWER1_URL", "http://localhost:8001"),
    os.getenv("FOLLOWER2_URL", "http://localhost:8002"),
    os.getenv("FOLLOWER3_URL", "http://localhost:8003"),
]

@pytest.mark.asyncio
async def test_write_replication_eventual_consistency():
    """Basic integration test."""
    key = "test_key"
    value = "test_value"

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1) Write via leader
        resp = await client.post(
            f"{LEADER_URL}/write",
            json={"key": key, "value": value},
            params={"write_quorum": 2}
        )
        assert resp.status_code == 200, f"Write failed: {resp.text}"
        
        # 2) Read from leader immediately
        resp = await client.get(f"{LEADER_URL}/kv/{key}")
        assert resp.status_code == 200
        assert resp.json()["value"] == value
        
        # 3) Wait for followers to catch up
        for follower in FOLLOWER_URLS:
            deadline = asyncio.get_event_loop().time() + 10.0
            while True:
                try:
                    resp = await client.get(f"{follower}/kv/{key}")
                    if resp.status_code == 200 and resp.json()["value"] == value:
                        break
                except:
                    pass
                
                if asyncio.get_event_loop().time() > deadline:
                    raise AssertionError(f"Follower {follower} didn't get value in time")
                await asyncio.sleep(0.2)

@pytest.mark.asyncio
async def test_quorum_behavior():
    """Test different quorum settings."""
    key = "quorum_test"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test quorum=1 (fastest)
        start = asyncio.get_event_loop().time()
        resp = await client.post(
            f"{LEADER_URL}/write",
            json={"key": key + "_1", "value": "val1"},
            params={"write_quorum": 1}
        )
        time1 = asyncio.get_event_loop().time() - start
        
        # Test quorum=3 (slower)
        start = asyncio.get_event_loop().time()
        resp = await client.post(
            f"{LEADER_URL}/write",
            json={"key": key + "_3", "value": "val3"},
            params={"write_quorum": 3}
        )
        time3 = asyncio.get_event_loop().time() - start
        
        print(f"Quorum 1: {time1:.3f}s, Quorum 3: {time3:.3f}s")
        # Note: time3 should generally be > time1