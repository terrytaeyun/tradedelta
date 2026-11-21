# TradeDelta

Explain a change in trade value by destination, product or both. TradeDelta turns two periods of CSV data into a contribution table and a shareable HTML report. Python 3.10+ is the only requirement.

[한국어](#한국어) · [Demo report](docs/index.html)

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
