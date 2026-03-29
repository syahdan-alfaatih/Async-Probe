# 🔍 AsyncProbe — Async HTTP Load Testing Tool

> **For authorized, internal defensive testing only.**  
> Use this tool exclusively on systems you own or have explicit written permission to test.

---

## Overview

**AsyncProbe** is a high-concurrency asynchronous HTTP load probe written in Python, built for stress testing and capacity planning on internal infrastructure. It uses `asyncio` and `aiohttp` to simulate realistic concurrent traffic patterns and collect detailed performance metrics.

Intended use cases:
- Pre-launch stress testing of APIs and web services
- Measuring response latency and throughput under load
- Identifying bottlenecks before production incidents happen
- Authorized red team / blue team lab exercises

---

## Features

- Async, non-blocking — handles hundreds of concurrent workers efficiently
- Configurable concurrency, request count, rate limit, and timeout
- Randomized paths, user agents, and payloads for realistic traffic simulation
- Detailed summary: latency stats (avg, min, max, median, stdev), throughput, status code distribution
- Graceful shutdown on keyboard interrupt or duration limit

---

## Requirements

- Python 3.9+
- `aiohttp`

```bash
pip install aiohttp
```

---

## Usage

```bash
python probe_final2.py --target https://your-internal-server.local
```

### Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--target` | *(required)* | Base URL to probe |
| `--concurrency` | `100` | Number of concurrent async workers |
| `--requests` | `100000` | Target number of successful requests |
| `--rate` | `0.0` | Max req/sec per worker (`0` = uncapped) |
| `--duration` | `300.0` | Hard time limit in seconds |
| `--timeout` | `10.0` | Per-request timeout in seconds |
| `--probe-paths` | `/`, `/status`, `/health`, `/api/v1/ping` | Paths to probe (space-separated) |
| `--user-agents` | *(3 built-in)* | User agent strings to rotate through |

### Example

```bash
# Conservative test — 20 workers, max 500 requests, 60s limit
python probe_final2.py \
  --target http://localhost:8080 \
  --concurrency 20 \
  --requests 500 \
  --duration 60 \
  --probe-paths /api/health /api/status
```

---

## Sample Output

```
[14:22:10] total=1240 | succ=1198 | err=42 | crash=0

============================================================
LOAD PROBE SUMMARY (POST MODE)
============================================================
Target       : http://localhost:8080
Duration     : 45.32s
Concurrency  : 20
------------------------------------------------------------
Success      : 1198
Errors       : 42
Crashes      : 0
Total        : 1240
Bytes rx     : 3.81 MiB
------------------------------------------------------------
Avg latency  : 0.0371s
Min / Max    : 0.0089s / 0.4812s
Median       : 0.0284s
Std dev      : 0.0412s
Throughput   : 26.44 req/s
------------------------------------------------------------
Status codes:
  200 →   1198
  503 →     42
============================================================
```

---

## How It Works

Each worker:
1. Picks a random path from `--probe-paths`
2. Appends a random query parameter to avoid caching
3. Sends a `POST` request with a randomized JSON payload (~512 bytes of junk data)
4. Records latency, status code, and bytes received

All workers run concurrently under a shared `asyncio.Semaphore` and stop when the success target, duration limit, or a keyboard interrupt is reached.

---

## ⚠️ Legal & Ethical Disclaimer

This tool sends a high volume of HTTP requests to a target server. **Unauthorized use against systems you do not own or have explicit permission to test is illegal** and may violate laws including:

- Indonesia: **UU ITE (Undang-Undang Informasi dan Transaksi Elektronik)**
- United States: **Computer Fraud and Abuse Act (CFAA)**
- EU: **Directive on Attacks Against Information Systems**
- And equivalent laws in your jurisdiction

**Always obtain written authorization before running this tool against any system.**  
The author assumes no liability for misuse.

---

## Project Context

This tool was developed as part of an internal red team defensive tooling exercise. It is published here for portfolio and educational purposes, demonstrating:

- Async Python patterns with `asyncio` and `aiohttp`
- Concurrent workload design with semaphores and shared state
- Performance metrics collection (latency distribution, throughput, error rates)
- Security engineering mindset: building tools that are scoped, observable, and stoppable

---

## License

MIT License — see [LICENSE](LICENSE) for details.

**Additional restriction:** This software may not be used to conduct unauthorized access, denial-of-service attacks, or any activity that violates applicable law. Use is strictly limited to authorized testing on systems you own or have explicit permission to test.
