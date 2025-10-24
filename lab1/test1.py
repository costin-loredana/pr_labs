import requests
import time
from concurrent.futures import ThreadPoolExecutor

URL = "http://127.0.0.1:8000"  

def make_request(i):
    try:
        r = requests.get(URL, timeout=15)
        return f"Request {i} completed with status {r.status_code}"
    except Exception as e:
        return f"Request {i} failed: {type(e).__name__}"


def main():
        start = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(make_request, range(1, 11)))
        end = time.time()

        for res in results:
            print(res)

        print(f"\nAll 10 requests completed in {end - start:.2f} seconds.")

if __name__ == "__main__":
    main()
