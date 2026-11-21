"""Convert Korean Customs Service observations to TradeDelta's data format."""

import re
from dataclasses import asdict
from os import getenv
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree

from tradedelta import ROOT, compare, is_period, load_csv


CUSTOMS_API = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
CUSTOMS_SOURCE = "https://www.data.go.kr/data/15100475/openapi.do"
SAMPLE_SOURCE = "https://www.mfds.go.kr/brd/m_99/view.do?seq=50010"
MAX_XML_BYTES = 256 * 1024


class TradeDataError(ValueError):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def parse_observation(payload, period, partner, hs):
    if len(payload) > MAX_XML_BYTES or re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", payload, re.I):
        raise TradeDataError("관세청 응답의 XML 형식을 확인할 수 없습니다.")
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        raise TradeDataError("관세청에서 해석할 수 없는 응답을 받았습니다.") from None

    if root.findtext(".//resultCode", "").strip() != "00":
        raise TradeDataError("관세청이 조회 요청을 승인하지 않았습니다. 인증키와 조회 범위를 확인하세요.")

    matches = []
    for item in root.findall(".//item"):
        row_period = item.findtext("year", "").strip().replace(".", "-")
        row_partner = item.findtext("statCd", "").strip()
        row_hs = item.findtext("hsCd", "").strip()
        if (row_period, row_partner, row_hs) == (period, partner, hs):
            matches.append(item.findtext("expDlr", "").strip())

    if not matches:
        raise TradeDataError(f"{period} · {partner} · {hs} 관측값이 응답에 없습니다.", status=404)
    if len(matches) != 1 or not re.fullmatch(r"[0-9]{1,18}", matches[0]):
        raise TradeDataError("관세청 응답에서 중복 행 또는 해석할 수 없는 수출액을 찾았습니다.")
    return int(matches[0])


def fetch_observation(period, partner, hs, service_key):
    month = period.replace("-", "")
    params = urlencode({"serviceKey": service_key, "strtYymm": month, "endYymm": month,
                        "cntyCd": partner, "hsSgn": hs})
    try:
        with urlopen(f"{CUSTOMS_API}?{params}", timeout=8) as response:
            payload = response.read(MAX_XML_BYTES + 1)
    except (URLError, OSError):
        raise TradeDataError("관세청과 통신하지 못했습니다. 잠시 뒤 다시 조회하세요.") from None
    return parse_observation(payload, period, partner, hs)


def build_comparison(source, base, target, partners=(), hs=None):
    if source == "sample":
        if (base, target) != ("2024", "2025") or partners or hs:
            raise TradeDataError("샘플은 2024–2025년 전체 화장품 수출을 비교합니다.", status=422)
        values = load_csv(ROOT / "examples" / "korea_cosmetics.csv")
        name = "식품의약품안전처 · 2024–2025 화장품 수출"
        coverage = "한국 화장품 전체 수출 · 미국, 중국, 일본, 기타 시장"
        url = SAMPLE_SOURCE
    else:
        if not (is_period(base) and is_period(target) and len(base) == len(target) == 7 and base < target):
            raise TradeDataError("관세청 조회에는 기간을 YYYY-MM 형식으로 두 개 입력하세요.", status=422)
        if (not hs or not re.fullmatch(r"(?:[0-9]{2}|[0-9]{4}|[0-9]{6}|[0-9]{10})", hs)
                or not 1 <= len(partners) <= 3 or len(set(partners)) != len(partners)
                or any(not re.fullmatch(r"[A-Z]{2}", partner) for partner in partners)):
            raise TradeDataError("HS 코드 하나와 서로 다른 두 글자 국가 코드 1–3개를 입력하세요.", status=422)
        key = getenv("KCS_SERVICE_KEY", "").strip()
        if not key:
            raise TradeDataError("서버에 KCS_SERVICE_KEY가 설정되어 있어야 합니다.", status=503)
        values = {(period, partner, hs): fetch_observation(period, partner, hs, key)
                  for period in (base, target) for partner in partners}
        name = "관세청 · 품목별 국가별 수출입실적"
        coverage = f"선택 국가 {', '.join(partners)}의 수출 합계 · HS {hs}"
        url = CUSTOMS_SOURCE

    return {**asdict(compare(values, base, target)), "source": source,
            "coverage": coverage, "source_name": name, "source_url": url}
