"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    bad_num = lambda v: isinstance(v, float) and (math.isnan(v) or math.isinf(v))
    problems += [f"metric {k} is {v}" for k, v in pr["metrics"].items() if bad_num(v)]
    rows = pr["rows"]
    problems += [f"row ({r.get('item_id')}, {r.get('seed')}) has non-finite {k}"
                 for r in rows for k, v in r.items() if bad_num(v)]
    mf = pr["manifest"]
    want = mf["items"] * len(mf["seeds"])
    if len(rows) != want:
        problems.append(f"{len(rows)} rows, manifest says {mf['items']} items x {len(mf['seeds'])} seeds = {want}")
    keys = [(r["item_id"], r["seed"]) for r in rows]
    if len(set(keys)) != len(keys):
        problems.append(f"{len(keys) - len(set(keys))} duplicated (item, seed) row(s)")
    base_keys = {(r["item_id"], r["seed"]) for r in base["rows"]}
    if set(keys) != base_keys:
        problems.append(f"(item, seed) set differs from baseline: {len(set(keys) ^ base_keys)} pair(s) only on one side")
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s): {pr['evaluator_failures'][0]}")
    graded = [m["id"] for m in spec["metrics"] if base["rows"] and m["id"] in base["rows"][0]]
    for m in graded:
        n_none = sum(1 for r in rows if r.get(m) is None)
        if n_none:
            problems.append(f"{n_none} row(s) with no value for graded metric {m} (crashed grader or dropped column)")
    # reported metrics must be what the rows say (a hand-edited summary is the cheapest trap)
    ids = [m for m in graded if all(m in r for r in rows)]
    if ids and rows:
        for m in ids:
            vals = [r[m] for r in rows if r[m] is not None]
            if not vals:
                continue
            exp = sum(vals) if m in ("secret_leak", "approval_bypass") else sum(vals) / len(vals)
            got = pr["metrics"].get(m)
            if isinstance(got, (int, float)) and not bad_num(got) and abs(got - exp) > 1e-3:
                problems.append(f"metric {m} reports {got} but its rows give {exp}")
    tags = lambda rep: {(r["item_id"], r["seed"]): sorted(r.get("slices") or []) for r in rep["rows"]}
    tp, tb = tags(pr), tags(base)
    problems += [f"row {k} slice tags {tp[k]} differ from baseline {tb[k]}" for k in sorted(tp) if k in tb and tp[k] != tb[k]]
    if base_spec is not None and base_spec.get("eval_set_version") == spec.get("eval_set_version"):
        problems += _ratchet(spec, base_spec)
    return problems


def _loosened(name: str, new: dict, old: dict) -> list[str]:
    """Threshold fields of one metric/slice that got laxer than the base spec."""
    out = []
    if old.get("blocking") and not new.get("blocking"):
        out.append(f"{name}: no longer blocking")
    nt, ot = new.get("threshold", new), old.get("threshold", old)
    if "max" in ot and ("max" not in nt or nt["max"] > ot["max"]):
        out.append(f"{name}: max {ot['max']} -> {nt.get('max')}")
    if "min" in ot and ("min" not in nt or nt["min"] < ot["min"]):
        out.append(f"{name}: min {ot['min']} -> {nt.get('min')}")
    if "max_increase" in ot and ("max_increase" not in nt or nt["max_increase"] > ot["max_increase"]):
        out.append(f"{name}: max_increase {ot['max_increase']} -> {nt.get('max_increase')}")
    if ot.get("no_significant_drop") and not nt.get("no_significant_drop"):
        out.append(f"{name}: no_significant_drop dropped")
    return out


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    out = []
    new = {m["id"]: m for m in spec["metrics"]}
    for m in base_spec["metrics"]:
        out += [f"ratchet {x}" for x in (_loosened(m["id"], new[m["id"]], m) if m["id"] in new else [f"{m['id']}: metric removed"])]
    new_s = {(s["name"], s["metric"]): s for s in spec.get("slices") or []}
    for s in base_spec.get("slices") or []:
        key = (s["name"], s["metric"])
        out += [f"ratchet slice {x}" for x in (_loosened(f"{key[0]}/{key[1]}", new_s[key], s) if key in new_s else [f"{key[0]}/{key[1]}: slice removed"])]
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    bs = spec.get("bootstrap", {})
    blocked, lines = [], []
    for sl in spec.get("slices") or []:
        name, metric = sl["name"], sl["metric"]
        a, b = per_item(pr, metric, slice_name=name), per_item(base, metric, slice_name=name)
        verdict, note = "ok", ""
        if not a:
            verdict, note = "fail", "no rows in slice"      # an empty slice must not pass silently
        else:
            val = sum(a.values()) / len(a)
            note = f"mean {val:.3f}"
            if "min" in sl and val < sl["min"]:
                verdict = "fail"
            if sl.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                       n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                    note += f" Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
        sid = f"slice:{name}/{metric}"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(sid)
        label = "ok" if verdict == "ok" else ("BLOCK" if sl.get("blocking") else "warn")
        lines.append(f"  {sid:<34} {note:<44} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
