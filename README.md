# TradeDelta

Explain a change in trade value by destination, product or both. TradeDelta turns two periods of CSV data into a contribution table and a shareable HTML report. Python 3.10+ is the only requirement.

[한국어](#한국어) · [Demo report](docs/index.html)

## Local AI service

The browser app combines export comparisons with source-linked explanations. The built-in sample works without credentials. The optional live mode queries Korea Customs by country and HS code. The optional agent uses OpenAI Responses API function calls and structured outputs. See the [Korean walkthrough](#ai-엔지니어링-실습).

## Quick start

```sh
python tradedelta.py
python tradedelta.py --format html --output trade-report.html
```

Open `trade-report.html` in a browser. The demo uses published Korean cosmetics exports for 2024 and 2025. Exports grew by **$1.240 billion (+12.19%)**. The US added **$285 million**, China subtracted **$474 million**, and the aggregate of all other destinations excluding the US, China and Japan added **$1.378 billion**.

The demo uses the totals and three individual destinations from the [Ministry of Food and Drug Safety release](https://www.mfds.go.kr/brd/m_99/view.do?seq=50010), 22 May 2026, attachment p. 15, table 10. The source table credits Korea Customs Service and Korea International Trade Association. We convert USD thousands to whole USD. The `Other destinations` line is the published world total minus the three named destinations. This demo covers one product category.

## Bring your own CSV

```csv
period,partner,product,value_usd
2024-10,US,090121,100
2024-10,JP,090121,200
2025-10,US,090121,150
2025-10,JP,090121,190
```

```sh
python tradedelta.py exports.csv --base 2024-10 --target 2025-10 --group pair --format json
```

- Use one frequency per file (`YYYY` or `YYYY-MM`) and nonnegative whole USD values. Both comparison periods must be present. Use one reporting country, one trade flow, consistent commodity codes and mutually exclusive destinations and products. Remove totals and overlapping subtotals before loading the CSV.
- Each `period,partner,product` key must be unique. The same partner–product pairs must appear in both comparison periods. Use `--missing-as-zero` only if your source defines an absent pair as zero trade. The report counts these substitutions. Pairs missing from both periods cannot be detected from the file alone.
- `--group` accepts `partner`, `product` or `pair`. `--format` accepts `text`, `json` or `html`. Importing from an API requires converting the source to this CSV schema first.

## Method

For group *g*, its contribution in percentage points is `100 × (target_g − base_g) / total_base`. Dividing by the same base total means the group contributions add up to overall growth before rounding. A group’s own growth rate uses that group’s base as its denominator. Dollar changes are calculated exactly with integers. If `total_base` is zero, growth and percentage-point contribution are undefined, while dollar changes still reconcile.

The report attributes a numerical change to the destinations and products where it occurred. Explaining why it occurred requires additional evidence, such as quantities, unit values, exchange rates or demand indicators.

```sh
python -m unittest -v
python tradedelta.py --format html --output docs/index.html
```

## 한국어

무역 CSV 두 시점을 비교해 **어느 국가·품목에서 늘거나 줄었는지** 달러와 성장률 기여도(%p)로 보여주는 도구다. 예를 들어 기준 수출 총액이 $100이고 미국에서 $10가 늘고 중국에서 $5가 줄었다면, 두 시장은 각각 +10%p와 −5%p를 기여해 총 수출은 5% 늘어난다.

첫 데모는 식약처가 발표한 2024~2025년 한국 화장품 수출 실적이다. `python tradedelta.py`로 확인할 수 있다. 각 시장에 사업을 하는 기업의 매출을 분석할 때는 공시, 유통 채널, 생산거점 자료도 함께 대조해야 한다.

### AI 엔지니어링 실습

TradeDelta의 웹 화면에서 화장품 수출을 비교하고 통계 용어를 질문할 수 있다. 먼저 Python 3.11 이상에서 샘플로 흐름을 확인한다. 아래는 Windows PowerShell에서 저장소 폴더를 연 뒤 실행하는 명령이다.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn service.app:app
```

브라우저에서 [서비스 화면](http://127.0.0.1:8000/)을 열어 기본 질문으로 **결과 보기**를 누른다. 전체 수출 증가액 `1,240,258,000 USD`, 국가별 기여도와 출처를 확인할 수 있다. [FastAPI 명세](http://127.0.0.1:8000/docs)에서 `/api/compare`와 `/api/ask`에 요청을 보내 JSON 응답도 직접 볼 수 있다.

| 실습 | 코드 | 확인할 것 |
| --- | --- | --- |
| 데이터 수집 | `service/customs.py` | 관세청 XML의 월·국가·HS 코드·수출액이 기존 계산기에 어떻게 들어가는지 확인 |
| 수치 계산 | `tradedelta.py` | 비교 대상 국가들의 기준 기간 합계가 분모로 쓰이는지 확인 |
| RAG 검색 | `service/assistant.py`, `service/knowledge.json` | 먼저 `FOB와 CIF는 어떤 기준이야?`를 물어 어떤 문서가 선택되는지 확인 |
| 에이전트와 LLM | `service/assistant.py` | 실제 모델 사용 시 고른 도구와 답변 문장별 출처가 연결되는지 확인 |
| API와 화면 | `service/app.py`, `service/index.html` | 브라우저 입력이 `/api/ask`의 JSON 요청으로 바뀌고, 응답이 화면에 표시되는 과정 확인 |
| 평가와 Docker | `test_service.py`, `Dockerfile` | 정답 문서를 찾는지, 관측값 누락과 0을 구분하는지, 같은 샘플이 컨테이너에서도 결과를 내는지 확인 |

**검색 실습.** 데이터에서 **통계 문서만 검색**을 선택하고 `수출 금액기준이 뭐야?`와 `시험 점수는 어떻게 계산해?`를 각각 물어본다. **실행한 도구**를 펼치면 사용한 검색어와 근거 문서 수가 나온다. 모델 모드에서는 검색한 문서의 요약 문장과 출처도 함께 볼 수 있다. 검색은 한국어 띄어쓰기와 전각 글자를 정리한 뒤 주제별 키워드를 찾는다. `py -m unittest test_service.AssistantTests.test_retrieval_evaluation`으로 정답 문서와 관련 없는 질문을 함께 검사한다.

#### 실제 데이터와 모델 연결

- `KCS_SERVICE_KEY`에 [공공데이터포털 관세청 API](https://www.data.go.kr/data/15100475/openapi.do)의 디코딩 키를 설정하고 서버를 다시 실행한다. 화면에서 **관세청 월별 조회**를 고르면 월 두 개, 서로 다른 국가 코드 1~3개, HS 코드 하나를 조회한다. 요청당 한 달을 불러오므로 두 비교 월을 1년보다 멀리 고를 수 있다. 라이브 비교 표는 선택한 국가만 집계한다.
- `OPENAI_API_KEY`를 서버의 환경변수에 설정한다. 모델은 기본값 `gpt-6.2-sol`을 사용하며 `OPENAI_MODEL`로 바꿀 수 있다. 화면에서 **LLM 에이전트로 설명**을 켠 요청만 OpenAI API로 보낸다. 에이전트는 문서 검색과 수출 비교 중 필요한 도구를 각각 최대 한 번 호출한다. 서버는 도구의 인수와 인용 ID를 확인한다. 응답의 수출 표는 Python 계산 결과를 직접 보여준다.
- 키 없이 사용하는 기본 모드는 간단한 키워드 검색으로 찾은 문서 발췌와 계산 표를 보여준다. 답변 생성 모델 없이도 검색 결과와 수치의 관계를 확인할 수 있다. 검색은 `knowledge.json`의 소형 문서 모음으로 제한된다. 모델의 문장과 인용의 의미적 타당성은 사례별로 검토한다.

#### 실행 검증과 컨테이너

```powershell
py -m unittest -v
docker build -t tradedelta .
docker run --rm -p 127.0.0.1:8000:8000 tradedelta
```

이미 로컬 서버가 8000번 포트를 사용 중이면 먼저 `Ctrl+C`로 종료한다. Docker 명령은 8000번 포트를 로컬 컴퓨터에 연결한다. 컨테이너에서 실제 API를 쓰려면 현재 셸에 설정된 키를 `docker run`의 `-e KCS_SERVICE_KEY` 또는 `-e OPENAI_API_KEY`로 전달한다. 컨테이너를 띄운 뒤 새로운 셸에서 `py scripts/smoke_service.py`를 실행하면 화면 경로, API 명세, 샘플 수치와 인용을 함께 검사한다.

자료는 [관세청 데이터 명세](https://www.data.go.kr/data/15100475/openapi.do), [OpenAI 함수 호출](https://developers.openai.com/api/docs/guides/function-calling), [구조화된 출력](https://developers.openai.com/api/docs/guides/structured-outputs), [FastAPI 컨테이너 문서](https://fastapi.tiangolo.com/deployment/docker/)에서 확인할 수 있다.
