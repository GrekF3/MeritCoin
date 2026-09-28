from __future__ import annotations

import argparse
import time
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen


def wait_for_server(url: str, attempts: int, delay: float) -> bool:
    for _ in range(attempts):
        try:
            with urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return True
        except URLError:
            pass
        except OSError:
            pass
        time.sleep(delay)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Open a browser after the local server is ready.")
    parser.add_argument("url")
    parser.add_argument("--attempts", type=int, default=30)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    if wait_for_server(args.url, args.attempts, args.delay):
        if not webbrowser.open(args.url):
            print(f"Browser could not be opened automatically. Open this address manually: {args.url}")
        return

    print(f"Server address: {args.url}")


if __name__ == "__main__":
    main()
