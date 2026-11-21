"""Compare two periods of trade data and reconcile each contribution to the total."""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path
from string import Template


ROOT = Path(__file__).resolve().parent
FIELDS = ("period", "partner", "product", "value_usd")
GROUPS = {"partner": (0,), "product": (1,), "pair": (0, 1)}
DEMO_SOURCE = "https://www.mfds.go.kr/brd/m_99/view.do?seq=50010"


@dataclass(frozen=True)
class Contribution:
    group: tuple[str, ...]
    base_usd: int
    target_usd: int
    change_usd: int
    contribution_pp: float | None


@dataclass(frozen=True)
class Report:
    base_period: str
    target_period: str
    group_by: str
    base_usd: int
    target_usd: int
    change_usd: int
    growth_pct: float | None
    assumed_zero_pairs: int
    rows: list[Contribution]


def is_period(value):
    return bool(re.fullmatch(r"[0-9]{4}(?:-(?:0[1-9]|1[0-2]))?", value)) and value[:4] != "0000"


def load_csv(path):
    """Return {(period, partner, product): USD}, preserving codes as text."""
    values = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)) or not set(FIELDS).issubset(columns):
            raise ValueError("CSV must have unique headers and include " + ", ".join(FIELDS))

        for row in reader:
            if None in row or None in row.values():
                raise ValueError(f"CSV line {reader.line_num}: wrong number of fields")
            period, partner, product, value = (row[field].strip() for field in FIELDS)
            if not is_period(period):
                raise ValueError(f"CSV line {reader.line_num}: period must be YYYY or YYYY-MM")
            if not partner or not product:
                raise ValueError(f"CSV line {reader.line_num}: partner and product are required")
            if partner.casefold() in {"world", "wld", "all", "total"} or product.casefold() in {"all", "total"}:
                raise ValueError(f"CSV line {reader.line_num}: remove aggregate World/All/Total rows")
            if not re.fullmatch(r"[0-9]{1,18}", value):
                raise ValueError(f"CSV line {reader.line_num}: value_usd must be a nonnegative whole USD value")
            key = (period, partner, product)
            if key in values:
                raise ValueError(f"CSV line {reader.line_num}: duplicate record for {key}")
            values[key] = int(value)

    if len({len(period) for period, _, _ in values}) > 1:
        raise ValueError("Use one frequency per CSV. Annual and monthly rows cannot be mixed.")
    return values


def compare(values, base, target, group_by="partner", missing_as_zero=False):
    """Decompose the change using each group's delta over the same base total."""
    if not (is_period(base) and is_period(target) and len(base) == len(target) and base < target):
        raise ValueError("Choose an earlier base and a later target with the same YYYY or YYYY-MM format.")
    before = {(partner, product): value for (period, partner, product), value in values.items() if period == base}
    after = {(partner, product): value for (period, partner, product), value in values.items() if period == target}
    if not before or not after:
        raise ValueError("Both comparison periods must appear in the CSV.")

    missing = before.keys() ^ after.keys()
    if missing and not missing_as_zero:
        example = " / ".join(min(missing))
        raise ValueError(
            f"{len(missing)} partner/product pairs lack one period, e.g. {example}. "
            "Add the missing records or use --missing-as-zero if the source defines absence as zero."
        )

    base_total = sum(before.values())
    target_total = sum(after.values())
    change = target_total - base_total
    groups = defaultdict(lambda: [0, 0])
    for pair in before.keys() | after.keys():
        group = tuple(pair[index] for index in GROUPS[group_by])
        groups[group][0] += before.get(pair, 0)
        groups[group][1] += after.get(pair, 0)

    rows = [
        Contribution(group, old, new, new - old, (new - old) * 100 / base_total if base_total else None)
        for group, (old, new) in groups.items()
    ]
    rows.sort(key=lambda row: (-row.change_usd, row.group))
    return Report(base, target, group_by, base_total, target_total, change,
                  change * 100 / base_total if base_total else None, len(missing), rows)


def signed(value, unit):
    return "—" if value is None else f"{value:+,.2f}{unit}"


def render_text(report):
    lines = [
        f"{report.base_period} to {report.target_period} | grouped by {report.group_by}",
        f"Totals (USD): {report.base_usd:,} to {report.target_usd:,} | "
        f"{report.change_usd:+,} ({signed(report.growth_pct, '%')})",
        f"{'Group':<25} {'Change (USD)':>20} {'Contribution':>15}",
    ]
    for row in report.rows:
        lines.append(f"{' / '.join(row.group):<25} {row.change_usd:>+20,} {signed(row.contribution_pp, ' pp'):>15}")
    if report.assumed_zero_pairs:
        lines.append(f"Assumed zero in the missing period for {report.assumed_zero_pairs} pairs.")
    return "\n".join(lines) + "\n"


def render_html(report, demo):
    maximum = max(abs(row.change_usd) for row in report.rows) or 1
    bars = []
    details = []
    for row in report.rows:
        label = escape(" / ".join(row.group))
        width = abs(row.change_usd) / maximum * 50
        direction = "negative" if row.change_usd < 0 else "positive"
        delta = f"{row.change_usd:+,}"
        bars.append(
            f'<div class="bar-row"><span>{label}</span><div class="track" aria-hidden="true">'
            f'<i class="{direction}" style="width:{width:.4f}%"></i></div><strong>{delta}</strong></div>'
        )
        details.append(
            f"<tr><th scope=\"row\">{label}</th><td>{row.base_usd:,}</td><td>{row.target_usd:,}</td>"
            f"<td>{delta}</td><td>{signed(row.contribution_pp, ' pp')}</td></tr>"
        )

    coverage = (
        "South Korea’s cosmetics exports to the US, China, Japan and all other destinations. "
        "Other destinations equal the published world total minus the three named markets."
        if demo else "The totals describe the rows supplied in the input CSV."
    )
    if report.assumed_zero_pairs:
        coverage += f" The missing period was filled with zero for {report.assumed_zero_pairs} pairs."
    source = f'<a href="{DEMO_SOURCE}">MFDS release, 22 May 2026, p. 15</a>' if demo else "Input CSV"
    template = Template((ROOT / "report_template.html").read_text(encoding="utf-8"))
    return template.substitute(
        headline="What moved Korea’s cosmetics exports?" if demo else "What moved trade?",
        coverage=escape(coverage), source=source, group_by=report.group_by,
        base_period=report.base_period, target_period=report.target_period,
        base_usd=f"{report.base_usd:,}", target_usd=f"{report.target_usd:,}",
        change_usd=f"{report.change_usd:+,}", growth=signed(report.growth_pct, "%"),
        bars="\n".join(bars), rows="\n".join(details),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="?", type=Path, help="omit to run the Korean cosmetics demo")
    parser.add_argument("--base", help="base period, YYYY or YYYY-MM")
    parser.add_argument("--target", help="target period in the same format")
    parser.add_argument("--group", choices=GROUPS, default="partner")
    parser.add_argument("--format", choices=("text", "json", "html"), default="text")
    parser.add_argument("--output", type=Path, help="write to a file instead of stdout")
    parser.add_argument("--missing-as-zero", action="store_true", help="fill missing partner/product pairs with zero")
    args = parser.parse_args(argv)
    demo = args.csv is None
    if not demo and (not args.base or not args.target):
        parser.error("--base and --target are required for a custom CSV")

    try:
        input_path = args.csv or ROOT / "examples" / "korea_cosmetics.csv"
        if args.output and args.output.resolve() == input_path.resolve():
            raise ValueError("Choose an output path different from the input CSV.")
        report = compare(load_csv(input_path), args.base or "2024", args.target or "2025",
                         args.group, args.missing_as_zero)
        if args.format == "json":
            output = json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n"
        elif args.format == "html":
            output = render_html(report, demo)
        else:
            output = render_text(report)
        if args.output:
            args.output.write_text(output, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(output)
    except (OSError, ValueError, csv.Error) as error:
        parser.exit(2, f"TradeDelta: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
