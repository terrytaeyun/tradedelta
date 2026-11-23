"""Serialize the exact trade comparison calculated for the current request."""

from csv import writer
from io import StringIO


def comparison_csv(report):
    buffer = StringIO(newline="")
    output = writer(buffer)
    output.writerow(("market", "base_period", "target_period", "base_usd", "target_usd",
                     "change_usd", "contribution_pp", "coverage", "source_url"))
    for row in report["rows"]:
        output.writerow((" / ".join(row["group"]), report["base_period"], report["target_period"],
                         row["base_usd"], row["target_usd"], row["change_usd"], row["contribution_pp"],
                         report["coverage"], report["source_url"]))
    return buffer.getvalue()
