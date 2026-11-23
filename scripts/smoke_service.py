"""Exercise the browser route and sample pipeline against a running service."""

import json
import sys
import time
from csv import DictReader
from http.client import HTTPException
from io import StringIO
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def post_json(url, payload):
    request = Request(url, data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=5) as response:
        return json.load(response)


def main(base_url="http://127.0.0.1:8000"):
    for attempt in range(20):
        try:
            with urlopen(f"{base_url}/api/status", timeout=2) as response:
                status = json.load(response)
            break
        except (OSError, HTTPException):
            if attempt == 19:
                raise
            time.sleep(1)
    assert "model_configured" in status

    with urlopen(f"{base_url}/", timeout=5) as response:
        assert "TradeDelta" in response.read().decode("utf-8")
    with urlopen(f"{base_url}/openapi.json", timeout=5) as response:
        assert "/api/ask" in json.load(response)["paths"]

    result = post_json(f"{base_url}/api/ask", {
        "question": "수출 성장률 기여도 분모는?", "trade": {"source": "sample"}, "use_model": False,
    })
    assert result["mode"] == "evidence"
    assert result["comparison"]["change_usd"] == 1_240_258_000
    assert result["claims"][0]["source_ids"] == ["contribution"]
    assert "get_trade_comparison" in result["tools"]
    assert result["retrieval"] == {"query": "수출 성장률 기여도 분모는?", "note_ids": ["contribution"]}

    rows = list(DictReader(StringIO(result["comparison_csv"])))
    comparison = result["comparison"]
    assert len(rows) == len(comparison["rows"])
    assert sum(int(row["change_usd"]) for row in rows) == comparison["change_usd"]
    assert all(row["coverage"] == comparison["coverage"] and row["source_url"] == comparison["source_url"]
               for row in rows)
    notes = post_json(f"{base_url}/api/ask", {"question": "FOB는 뭐야?"})
    assert notes["comparison_csv"] is None

    invalid = Request(f"{base_url}/api/compare", data=b'{"source":"sample","base":"2020"}',
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(invalid, timeout=5):
            raise AssertionError("An unsupported sample period was accepted")
    except HTTPError as error:
        assert error.code == 422
    print("FastAPI health, browser route, API schema, comparison, CSV export and citations passed.")


if __name__ == "__main__":
    main(*sys.argv[1:])
