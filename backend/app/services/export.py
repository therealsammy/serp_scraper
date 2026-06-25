"""CSV / JSON export of extracted results."""
from __future__ import annotations

import csv
import io
import json

from ..schemas import ExtractedResult

FIELDS = ["rank", "title", "url", "domain", "snippet", "word_count",
          "status", "source_provider", "full_text"]


def to_json(results: list[ExtractedResult]) -> str:
    return json.dumps([r.model_dump(mode="json") for r in results], indent=2)


def to_csv(results: list[ExtractedResult]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDS, extrasaction="ignore")
    writer.writeheader()
    for r in results:
        writer.writerow(r.model_dump(mode="json"))
    return buf.getvalue()
