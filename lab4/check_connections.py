import asyncio
import httpx
import os

async def check_services():
    leader = "http://localhost:8000"
    followers = [
        "http://localhost:8001",
        "http://localhost:8002", 
        "http://localhost:8003",
        "http://localhost:8004",
        "http://localhost:8005"
    ]
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        print("Checking leader...")
        try:
            r = await client.get(f"{leader}/health")
            print(f"✓ Leader: {r.json()}")
            
            # Check leader's configuration
            r = await client.get(f"{leader}/debug/followers")
            print(f"Leader followers config: {r.json()}")
        except Exception as e:
            print(f"✗ Leader error: {e}")
        
        print("\nChecking followers...")
        for i, follower in enumerate(followers, 1):
            try:
                r = await client.get(f"{follower}/health")
                print(f"✓ Follower {i}: {r.json()}")
            except Exception as e:
                print(f"✗ Follower {i} error: {e}")
        
        print("\nTesting write and read...")
        try:
            # Write
            r = await client.post(
                f"{leader}/write",
                json={"key": "test", "value": "hello"},
                params={"write_quorum": 1}
            )
            print(f"Write status: {r.status_code}, {r.text}")
            
            # Read from leader
            r = await client.get(f"{leader}/kv/test")
            print(f"Read from leader: {r.json()}")
            
            # Read from followers
            for i, follower in enumerate(followers, 1):
                try:
                    r = await client.get(f"{follower}/kv/test")
                    print(f"Follower {i} value: {r.json()}")
                except:
                    print(f"Follower {i}: No value yet")
                    
        except Exception as e:
            print(f"Test error: {e}")

if __name__ == "__main__":
    asyncio.run(check_services())