"""Read-only: Gemini classification metrics from the live wasteRecords (no new Gemini calls).

Includes the development/smoke-test records (isTest) — they are the only real Gemini runs so far — and
labels them. Synthetic records (no Gemini involved) are excluded. Writes benchmark/results/live_gemini.json.
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.firebase import firestore_client  # noqa: E402

LOW = 0.6


def p95(values: list[int]) -> int | None:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)] if ordered else None


def main() -> None:
    rows = []
    for snap in firestore_client().collection("wasteRecords").stream():
        d = snap.to_dict()
        if d.get("isSynthetic") or d.get("source") == "synthetic":
            continue
        ai = d.get("aiResult") or {}
        items = ai.get("items", [])
        rows.append({
            "bag": snap.id, "status": d.get("status"), "source": d.get("source"), "isTest": d.get("isTest", False),
            "model": d.get("model"), "latencyMs": d.get("latencyMs"), "aiError": d.get("aiError"),
            "aiItems": len(items), "finalItems": len(d.get("finalItems") or []), "editCount": d.get("editCount"),
            "categories": [i.get("category") for i in items],
            "confidences": [round(i.get("confidence", 0), 2) for i in items],
            "segregation": ai.get("segregationQuality"),
        })
    analyzed = [r for r in rows if r["aiItems"] > 0]
    lat = [r["latencyMs"] for r in analyzed if r["latencyMs"] is not None]
    conf = [c for r in analyzed for c in r["confidences"]]
    summary = {
        "records": len(rows), "analyzed": len(analyzed), "allAreTestRuns": all(r["isTest"] for r in rows),
        "avgLatencyMs": round(sum(lat) / len(lat), 1) if lat else None, "p95LatencyMs": p95(lat),
        "minLatencyMs": min(lat, default=None), "maxLatencyMs": max(lat, default=None),
        "failures": sum(1 for r in rows if r["aiError"]), "invalidOutputs": sum(1 for r in rows if r["aiError"] == "invalid_output"),
        "manualFallbacks": sum(1 for r in rows if r["source"] == "manual"),
        "itemsPerBag": round(sum(r["aiItems"] for r in analyzed) / len(analyzed), 1) if analyzed else None,
        "lowConfidenceShare": round(sum(1 for c in conf if c < LOW) / len(conf), 3) if conf else None,
        "models": sorted({r["model"] for r in analyzed if r["model"]}),
    }
    out = Path(__file__).parent / "results" / "live_gemini.json"
    out.write_text(json.dumps({"summary": summary, "records": sorted(rows, key=lambda r: r["bag"])}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
