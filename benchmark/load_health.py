"""Light load test: N concurrent users hit GET /health for D seconds. Prints JSON with p50/p95/p99 and error rate.

Usage: python benchmark/load_health.py [users=20] [seconds=30]
"""

import asyncio
import json
import math
import sys
import time

import httpx

URL = "https://ecotrace-api-frl7lolcea-el.a.run.app/health"


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


async def user(client: httpx.AsyncClient, until: float, lat: list[float], errors: list[str]) -> None:
    while time.perf_counter() < until:
        t0 = time.perf_counter()
        try:
            r = await client.get(URL)
            if r.status_code != 200:
                errors.append(str(r.status_code))
        except httpx.HTTPError as exc:
            errors.append(type(exc).__name__)
        lat.append((time.perf_counter() - t0) * 1000)


async def main(users: int, seconds: int) -> None:
    lat: list[float] = []
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=30, limits=httpx.Limits(max_connections=users)) as client:
        await client.get(URL)  # warm-up (excluded): avoid measuring a cold start
        until = time.perf_counter() + seconds
        await asyncio.gather(*(user(client, until, lat, errors) for _ in range(users)))
    print(json.dumps({
        "users": users, "seconds": seconds, "requests": len(lat), "rps": round(len(lat) / seconds, 1),
        "p50_ms": round(pct(lat, 0.50), 1), "p95_ms": round(pct(lat, 0.95), 1), "p99_ms": round(pct(lat, 0.99), 1),
        "max_ms": round(max(lat), 1), "errors": len(errors), "error_rate": round(len(errors) / len(lat), 4),
        "latencies_ms": [round(v, 1) for v in lat],
    }))


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 20, int(sys.argv[2]) if len(sys.argv) > 2 else 30))
