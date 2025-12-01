import asyncio
import os
import time
from typing import List, Dict

import httpx
import numpy as np
import matplotlib.pyplot as plt

LEADER_URL = os.getenv("LEADER_URL", "http://localhost:8000")
FOLLOWER_URLS = [
    os.getenv("FOLLOWER1_URL", "http://localhost:8001"),
    os.getenv("FOLLOWER2_URL", "http://localhost:8002"),
    os.getenv("FOLLOWER3_URL", "http://localhost:8003"),
    os.getenv("FOLLOWER4_URL", "http://localhost:8004"),
    os.getenv("FOLLOWER5_URL", "http://localhost:8005"),
]


async def single_write(client: httpx.AsyncClient, key: str, value: str, quorum: int) -> float:
    start = time.monotonic()
    resp = await client.post(
        f"{LEADER_URL}/write",
        params={"write_quorum": quorum},
        json={"key": key, "value": value},
    )
    end = time.monotonic()
    if resp.status_code != 200:
        # Treat failed writes as very slow for plotting; you can also choose to skip
        print(f"Write failed for key={key}, quorum={quorum}: {resp.status_code} {resp.text}")
    return (end - start) * 1000.0  # ms


async def run_load_for_quorum(quorum: int, total_writes: int = 100, batch_size: int = 10):
    keys = [f"key{i}" for i in range(10)]
    latencies: List[float] = []

    async with httpx.AsyncClient() as client:
        write_index = 0
        while write_index < total_writes:
            batch_tasks = []
            for _ in range(batch_size):
                if write_index >= total_writes:
                    break
                key = keys[write_index % len(keys)]
                value = f"value_q{quorum}_{write_index}"
                batch_tasks.append(single_write(client, key, value, quorum))
                write_index += 1

            batch_latencies = await asyncio.gather(*batch_tasks)
            latencies.extend(batch_latencies)

    return latencies


async def fetch_store_snapshot() -> Dict[str, str]:
    async with httpx.AsyncClient() as client:
        # We don't know all keys a priori here, so for demo we just query the 10 test keys
        keys = [f"key{i}" for i in range(10)]
        result = {}
        for key in keys:
            r = await client.get(f"{LEADER_URL}/kv/{key}")
            if r.status_code == 200:
                result[key] = r.json()["value"]
        return result


async def verify_replicas_match_leader():
    # Snapshot leader
    leader_snapshot = await fetch_store_snapshot()

    async with httpx.AsyncClient() as client:
        for follower in FOLLOWER_URLS:
            for key, leader_value in leader_snapshot.items():
                # Wait a bit for slow replicas
                deadline = time.monotonic() + 10.0
                while True:
                    r = await client.get(f"{follower}/kv/{key}")
                    if r.status_code == 200 and r.json()["value"] == leader_value:
                        break
                    if time.monotonic() > deadline:
                        raise AssertionError(
                            f"Follower {follower} does not match leader for key={key} "
                            f"(leader={leader_value}, follower_status={r.status_code}, follower_body={r.text})"
                        )
                    await asyncio.sleep(0.2)

    print("All followers match the leader for the tested keys.")


def summarize_latencies(latencies: List[float]):
    arr = np.array(latencies)
    return {
        "mean": float(arr.mean()),
        "median": float(np.quantile(arr, 0.5)),
        "p95": float(np.quantile(arr, 0.95)),
        "p99": float(np.quantile(arr, 0.99)),
    }


async def main():
    all_metrics = {}
    for quorum in range(1, 6):
        print(f"\n=== Measuring for write_quorum={quorum} ===")
        latencies = await run_load_for_quorum(quorum)
        stats = summarize_latencies(latencies)
        all_metrics[quorum] = stats
        print(
            f"Quorum={quorum}: "
            f"mean={stats['mean']:.1f}ms, median={stats['median']:.1f}ms, "
            f"p95={stats['p95']:.1f}ms, p99={stats['p99']:.1f}ms"
        )

    await verify_replicas_match_leader()

    # Plot quorum vs latency metrics
    quorums = sorted(all_metrics.keys())
    mean_vals = [all_metrics[q]["mean"] for q in quorums]
    median_vals = [all_metrics[q]["median"] for q in quorums]
    p95_vals = [all_metrics[q]["p95"] for q in quorums]
    p99_vals = [all_metrics[q]["p99"] for q in quorums]

    plt.figure()
    plt.plot(quorums, mean_vals, marker="o", label="Mean")
    plt.plot(quorums, median_vals, marker="o", label="Median")
    plt.plot(quorums, p95_vals, marker="o", label="p95")
    plt.plot(quorums, p99_vals, marker="o", label="p99")
    plt.xlabel("Write quorum (number of follower acks required)")
    plt.ylabel("Latency (ms)")
    plt.title("Write latency vs write quorum")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig("quorum_latency_metrics.png")
    print("\nSaved graph to quorum_latency_metrics.png")


if __name__ == "__main__":
    asyncio.run(main())
