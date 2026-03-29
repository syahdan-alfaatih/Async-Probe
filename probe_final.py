import asyncio
import argparse
import random
import time
import sys
import string 
from urllib.parse import urljoin, urlparse
import aiohttp
from aiohttp import ClientSession, TCPConnector, ClientError, ClientTimeout

parser = argparse.ArgumentParser(
    description="Internal defensive load probe — authorised testing only",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
parser.add_argument("--target", required=True, help="Base URL to test")
parser.add_argument("--concurrency", type=int, default=100, help="Concurrent workers")
parser.add_argument("--requests", type=int, default=100000, help="Target successful requests")
parser.add_argument("--rate", type=float, default=0.0, help="Max req/sec per worker (0 = uncapped)")
parser.add_argument("--duration", type=float, default=300.0, help="Hard time limit (s)")
parser.add_argument("--timeout", type=float, default=10.0, help="Per-request timeout (s)")
parser.add_argument("--probe-paths", nargs="+", default=["/", "/status", "/health", "/api/v1/ping"])
parser.add_argument("--user-agents", nargs="+", default=[
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "curl/7.88.1",
    "Byp0sProbe/0.1 (Research only you animals)"
])
args = parser.parse_args()


async def probe_worker(
    worker_id: int,
    session: ClientSession,
    semaphore: asyncio.Semaphore,
    counter: dict,
    lock: asyncio.Lock,
    stop_event: asyncio.Event,
):
    timeout_obj = ClientTimeout(total=args.timeout, connect=3, sock_connect=2, sock_read=5)

    while not stop_event.is_set():
        async with semaphore:
            if stop_event.is_set():
                return

            path = random.choice(args.probe_paths)
            url = urljoin(args.target, f"{path}?rand={random.random()}")
            
            headers = {
                "User-Agent": random.choice(args.user_agents),
                "X-Probe-Worker": str(worker_id),
                "Content-Type": "application/json" # Kasih tahu server kalau kita kirim JSON
            }

            dummy_payload = {
                "worker_id": worker_id,
                "timestamp": time.time(),
                "junk_data": "".join(random.choices(string.ascii_letters + string.digits, k=512))
            }

            start = time.monotonic()
            try:
                async with session.post(url, headers=headers, json=dummy_payload, timeout=timeout_obj) as resp:
                    elapsed = time.monotonic() - start
                    body = await resp.read()

                    async with lock:
                        counter['success'] += 1
                        counter['bytes_received'] += len(body)
                        counter['latencies'].append(elapsed)
                        counter['status_codes'][resp.status] = counter['status_codes'].get(resp.status, 0) + 1

            except (ClientError, asyncio.TimeoutError):
                async with lock:
                    counter['errors'] += 1

            except Exception:
                async with lock:
                    counter['crashes'] += 1

            async with lock:
                counter['total'] += 1
                if counter['success'] >= args.requests:
                    stop_event.set()
                    return


async def progress_printer(counter: dict, lock: asyncio.Lock, stop_event: asyncio.Event):
    while not stop_event.is_set():
        await asyncio.sleep(10)  
        async with lock:
            print(f"[{time.strftime('%H:%M:%S')}] "
                  f"total={counter['total']} | succ={counter['success']} | "
                  f"err={counter['errors']} | crash={counter['crashes']}")


async def main():
    if not urlparse(args.target).hostname:
        print("Error: Invalid target URL")
        return

    counter = {
        'total': 0, 'success': 0, 'errors': 0, 'crashes': 0,
        'bytes_received': 0, 'latencies': [], 'status_codes': {}
    }
    lock = asyncio.Lock()
    stop_event = asyncio.Event()

    connector = TCPConnector(
        limit=args.concurrency,
        limit_per_host=args.concurrency // 2 + 1,
        force_close=True, 
        enable_cleanup_closed=True,
        ttl_dns_cache=300,
    )

    start_time = time.monotonic()

    async with ClientSession(connector=connector) as session:
        semaphore = asyncio.Semaphore(args.concurrency)

        progress_task = asyncio.create_task(progress_printer(counter, lock, stop_event))

        workers = [
            asyncio.create_task(probe_worker(i, session, semaphore, counter, lock, stop_event))
            for i in range(args.concurrency)
        ]

        try:
            await asyncio.wait_for(
                asyncio.gather(*workers, return_exceptions=True),
                timeout=args.duration
            )
        except asyncio.TimeoutError:
            print(f"[!] Duration limit ({args.duration}s) reached")
            stop_event.set()
        finally:
            stop_event.set()
            await asyncio.gather(progress_task, return_exceptions=True)
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

    elapsed = time.monotonic() - start_time

    print("\n" + "="*60)
    print("LOAD PROBE SUMMARY (POST MODE)")
    print("="*60)
    print(f"Target       : {args.target}")
    print(f"Duration     : {elapsed:.2f}s")
    print(f"Concurrency  : {args.concurrency}")
    print("-"*60)
    print(f"Success      : {counter['success']}")
    print(f"Errors       : {counter['errors']}")
    print(f"Crashes      : {counter['crashes']}")
    print(f"Total        : {counter['total']}")
    print(f"Bytes rx     : {counter['bytes_received'] / 1024 / 1024:.2f} MiB")
    print("-"*60)

    if counter['latencies']:
        latencies = counter['latencies']
        avg = sum(latencies) / len(latencies)
        print(f"Avg latency  : {avg:.4f}s")
        print(f"Min / Max    : {min(latencies):.4f}s / {max(latencies):.4f}s")
        if len(latencies) >= 2:
            from statistics import stdev, median
            print(f"Median       : {median(latencies):.4f}s")
            print(f"Std dev      : {stdev(latencies):.4f}s")

    if elapsed > 0:
        print(f"Throughput   : {counter['success'] / elapsed:.2f} req/s")

    if counter['status_codes']:
        print("-"*60)
        print("Status codes:")
        for code, cnt in sorted(counter['status_codes'].items()):
            print(f"  {code:3d} → {cnt:6d}")

    print("="*60 + "\n")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Interrupted — shutting down")
    except Exception as e:
        print(f"\n[!] Fatal: {e}")