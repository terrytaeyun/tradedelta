"""Exercise the browser route and sample pipeline against a running service."""

import json
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


def main(base_url="http://127.0.0.1:8000"):
    for attempt in range(20):
        try:
            with urlopen(f"{base_url}/api/status", timeout=2) as response:
                status = json.load(response)
            break
        except URLError:
            if attempt == 19:
                raise
            time.sleep(1)
    assert "model_configured" in status

    with urlopen(f"{base_url}/", timeout=5) as response:
        assert "TradeDelta" in response.read().decode("utf-8")
    with urlopen(f"{base_url}/openapi.json", timeout=5) as response:
        assert "/api/ask" in json.load(response)["paths"]

    request = Request(f"{base_url}/api/ask", data=json.dumps({
        "question": "수출 성장률 기여도 분모는?", "trade": {"source": "sample"}, "use_model": False,
    }).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=5) as response:
        result = json.load(response)
    assert result["mode"] == "evidence"
    assert result["comparison"]["change_usd"] == 1_240_258_000
    assert result["claims"][0]["source_ids"] == ["contribution"]
    assert "get_trade_comparison" in result["tools"]
    print("FastAPI health, browser route, API schema, comparison and citations passed.")


if __name__ == "__main__":
    main(*sys.argv[1:])
