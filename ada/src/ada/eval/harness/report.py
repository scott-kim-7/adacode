from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ada.eval.harness.config import eval_base_url, results_dir
from ada.eval.harness.results import compare_baseline, load_baseline, validate_result_schema
from ada.eval.harness.stack_check import stack_status

BENCHMARKS = ("tau2", "bfcl", "swe", "toolsandbox", "mcpagent")
BENCHMARK_LABELS = {
	"tau2": "τ²-bench",
	"bfcl": "BFCL v4",
	"swe": "SWE-bench Verified",
	"toolsandbox": "ToolSandbox",
	"mcpagent": "MCPAgentBench",
}


@dataclass(frozen=True)
class PytestSummary:
	passed: int
	failed: int
	skipped: int
	errors: int
	duration_sec: float
	status: str
	failures: tuple[tuple[str, str], ...]


def reports_dir() -> Path:
	path = results_dir().parent / "reports"
	path.mkdir(parents=True, exist_ok=True)
	(path / "history").mkdir(parents=True, exist_ok=True)
	return path


def _now_iso() -> str:
	return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _now_slug() -> str:
	return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _status_icon(ok: bool) -> str:
	return "PASS" if ok else "FAIL"


def parse_junit_xml(path: Path) -> PytestSummary:
	tree = ET.parse(path)
	root = tree.getroot()
	if root.tag == "testsuite":
		suites = [root]
	else:
		suites = root.findall("testsuite")

	passed = failed = skipped = errors = 0
	duration = 0.0
	failures: list[tuple[str, str]] = []

	for suite in suites:
		passed += int(suite.attrib.get("tests", 0))
		failed += int(suite.attrib.get("failures", 0))
		errors += int(suite.attrib.get("errors", 0))
		skipped += int(suite.attrib.get("skipped", 0))
		duration += float(suite.attrib.get("time", 0) or 0)
		for case in suite.findall("testcase"):
			name = f"{case.attrib.get('classname', '')}.{case.attrib.get('name', '')}".strip(".")
			for tag in ("failure", "error"):
				node = case.find(tag)
				if node is not None:
					text = (node.text or node.attrib.get("message") or "").strip()
					failures.append((name, text[:500]))

	passed = max(0, passed - failed - errors - skipped)
	status = "PASS" if failed == 0 and errors == 0 else "FAIL"
	return PytestSummary(
		passed=passed,
		failed=failed,
		skipped=skipped,
		errors=errors,
		duration_sec=round(duration, 2),
		status=status,
		failures=tuple(failures),
	)


def _format_pytest_section(summary: PytestSummary) -> list[str]:
	lines = [
		"## Pytest",
		"",
		"| 항목 | 값 |",
		"|------|-----|",
		f"| 결과 | **{summary.status}** |",
		f"| 통과 | {summary.passed} |",
		f"| 실패 | {summary.failed} |",
		f"| 에러 | {summary.errors} |",
		f"| 스킵 | {summary.skipped} |",
		f"| 소요 시간 | {summary.duration_sec}s |",
		"",
	]
	if summary.failures:
		lines.extend(["### 실패 상세", ""])
		for name, message in summary.failures:
			lines.append(f"- `{name}`")
			if message:
				lines.append(f"  ```")
				lines.append(f"  {message}")
				lines.append(f"  ```")
		lines.append("")
	return lines


def _load_benchmark_result(benchmark: str, mode: str) -> dict[str, Any] | None:
	path = results_dir() / f"{benchmark}-{mode}.json"
	if not path.is_file():
		return None
	raw = json.loads(path.read_text(encoding="utf-8"))
	if isinstance(raw, dict):
		return raw
	return None


def collect_benchmark_results(mode: str = "smoke") -> list[dict[str, Any]]:
	out: list[dict[str, Any]] = []
	for benchmark in BENCHMARKS:
		payload = _load_benchmark_result(benchmark, mode)
		if payload:
			out.append(payload)
	return out


def _format_benchmark_rows(results: list[dict[str, Any]]) -> list[str]:
	if not results:
		return ["_벤치마크 결과 파일 없음._", ""]

	lines = [
		"| 벤치마크 | 모드 | 통과 | 전체 | Pass rate | Baseline | 결과 | 소요 |",
		"|----------|------|------|------|-----------|----------|------|------|",
	]
	for payload in results:
		benchmark = str(payload.get("benchmark") or "?")
		label = BENCHMARK_LABELS.get(benchmark, benchmark)
		mode = str(payload.get("mode") or "?")
		passed = int(payload.get("tasks_passed") or 0)
		total = int(payload.get("tasks_total") or 0)
		rate = float(payload.get("pass_rate") or 0.0)
		duration = float(payload.get("duration_sec") or 0.0)
		ok, _baseline_msg = compare_baseline(benchmark, rate)
		baseline = load_baseline().get(benchmark, {})
		base_rate = baseline.get("pass_rate", "—")
		extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
		source = extra.get("source") or payload.get("source") or ""
		source_note = f" ({source})" if source else ""
		lines.append(
			f"| {label}{source_note} | {mode} | {passed} | {total} | {rate:.1%} | {base_rate} | {_status_icon(ok)} | {duration:.1f}s |"
		)
	lines.append("")
	return lines


def _format_stack_section() -> list[str]:
	status = stack_status()
	lines = [
		"## 스택",
		"",
		"| 구성요소 | 상태 |",
		"|----------|------|",
		f"| Agent API (`{eval_base_url()}`) | {'OK' if status['agent_reachable'] else 'DOWN'} |",
		f"| MLX upstream | {'OK' if status['mlx_reachable'] else 'DOWN'} |",
		"",
	]
	return lines


def _write_report_files(slug: str, markdown: str, meta: dict[str, Any]) -> tuple[Path, Path]:
	reports = reports_dir()
	reports.mkdir(parents=True, exist_ok=True)
	(reports / "history").mkdir(parents=True, exist_ok=True)
	md_latest = reports / f"{slug}-latest.md"
	json_latest = reports / f"{slug}-latest.json"
	history_md = reports / "history" / f"{_now_slug()}-{slug}.md"

	md_latest.write_text(markdown, encoding="utf-8")
	json_latest.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
	history_md.write_text(markdown, encoding="utf-8")
	return md_latest, json_latest


def write_contract_report(*, junit_path: Path | None = None, duration_sec: float | None = None) -> Path:
	summary = parse_junit_xml(junit_path) if junit_path and junit_path.is_file() else None
	if summary is None:
		summary = PytestSummary(0, 0, 0, 0, duration_sec or 0.0, "UNKNOWN", ())

	lines = [
		"# Ada 테스트 리포트 — Contract Regression",
		"",
		f"**생성 시각:** {_now_iso()}  ",
		f"**결과:** **{summary.status}**  ",
		f"**소요 시간:** {summary.duration_sec}s",
		"",
		"## 요약",
		"",
		"| Tier | Suite | 결과 |",
		"|------|-------|------|",
		f"| 1 | Contract regression | **{summary.status}** |",
		"",
	]
	lines.extend(_format_pytest_section(summary))
	lines.extend([
		"## 실행",
		"",
		"```bash",
		"./scripts/verify-regression.sh",
		"```",
		"",
	])

	meta = {
		"suite": "contract",
		"timestamp": _now_iso(),
		"status": summary.status,
		"pytest": summary.__dict__,
	}
	md_path, _ = _write_report_files("contract", "\n".join(lines), meta)
	return md_path


def write_eval_smoke_report(*, junit_path: Path | None = None) -> Path:
	summary = parse_junit_xml(junit_path) if junit_path and junit_path.is_file() else PytestSummary(
		0, 0, 0, 0, 0.0, "UNKNOWN", ()
	)
	benchmarks = collect_benchmark_results("smoke")

	lines = [
		"# Ada 테스트 리포트 — Eval Smoke",
		"",
		f"**생성 시각:** {_now_iso()}  ",
		f"**Pytest 결과:** **{summary.status}**  ",
		f"**소요 시간:** {summary.duration_sec}s",
		"",
		"## 요약",
		"",
		"| Tier | Suite | 결과 |",
		"|------|-------|------|",
		f"| 2 | Eval smoke pytest | **{summary.status}** |",
		"",
	]
	lines.extend(_format_stack_section())
	lines.extend(["## 벤치마크 (smoke JSON)", ""])
	lines.extend(_format_benchmark_rows(benchmarks))
	lines.extend(_format_pytest_section(summary))
	lines.extend([
		"## 실행",
		"",
		"```bash",
		"./scripts/verify-regression-eval-smoke.sh",
		"./scripts/eval/run-<bench>-smoke.sh",
		"```",
		"",
		"Live MLX smoke: `ADA_EVAL_RUN_LIVE=1 pytest ada/tests/regression/eval/ -m eval_smoke`",
		"",
	])

	meta = {
		"suite": "eval_smoke",
		"timestamp": _now_iso(),
		"status": summary.status,
		"stack": stack_status(),
		"benchmarks": benchmarks,
		"pytest": summary.__dict__,
	}
	md_path, _ = _write_report_files("eval-smoke", "\n".join(lines), meta)
	write_summary_report()
	return md_path


def write_benchmark_report(payload: dict[str, Any]) -> Path:
	validate_result_schema(payload)
	benchmark = str(payload["benchmark"])
	mode = str(payload["mode"])
	label = BENCHMARK_LABELS.get(benchmark, benchmark)
	ok, baseline_msg = compare_baseline(benchmark, float(payload["pass_rate"]))

	lines = [
		f"# Ada 테스트 리포트 — {label} ({mode})",
		"",
		f"**생성 시각:** {payload.get('timestamp') or _now_iso()}  ",
		f"**결과:** **{_status_icon(ok)}**  ",
		f"**Pass rate:** {float(payload['pass_rate']):.1%} ({payload['tasks_passed']}/{payload['tasks_total']})  ",
		f"**Baseline:** {baseline_msg}",
		"",
		"## 상세",
		"",
		"| 항목 | 값 |",
		"|------|-----|",
		f"| Endpoint | `{payload.get('endpoint')}` |",
		f"| Model | `{payload.get('model')}` |",
		f"| 소요 시간 | {float(payload['duration_sec']):.1f}s |",
		"",
	]
	task_ids = payload.get("task_ids") or []
	if task_ids:
		lines.extend(["## Task IDs", ""])
		for task_id in task_ids[:20]:
			lines.append(f"- `{task_id}`")
		if len(task_ids) > 20:
			lines.append(f"- … 외 {len(task_ids) - 20}개")
		lines.append("")

	extra = payload.get("extra")
	if isinstance(extra, dict) and extra:
		lines.extend(["## Extra", "", "```json", json.dumps(extra, indent=2, ensure_ascii=False), "```", ""])

	slug = f"benchmark-{benchmark}-{mode}"
	meta = {
		"suite": slug,
		"timestamp": _now_iso(),
		"status": _status_icon(ok),
		"benchmark": payload,
		"baseline_check": baseline_msg,
	}
	md_path, _ = _write_report_files(slug, "\n".join(lines), meta)
	write_summary_report()
	return md_path


def write_summary_report() -> Path:
	benchmarks = collect_benchmark_results("smoke") + collect_benchmark_results("full")
	seen: set[tuple[str, str]] = set()
	unique: list[dict[str, Any]] = []
	for item in benchmarks:
		key = (str(item.get("benchmark")), str(item.get("mode")))
		if key in seen:
			continue
		seen.add(key)
		unique.append(item)

	all_ok = all(compare_baseline(str(b["benchmark"]), float(b["pass_rate"]))[0] for b in unique) if unique else True
	status = "PASS" if all_ok else "FAIL"

	lines = [
		"# Ada Eval Summary",
		"",
		f"**생성 시각:** {_now_iso()}  ",
		f"**종합 결과:** **{status}**",
		"",
		"## 벤치마크 결과",
		"",
	]
	lines.extend(_format_benchmark_rows(unique))
	lines.extend(_format_stack_section())
	lines.extend([
		"## 리포트 위치",
		"",
		f"- `{reports_dir()}/contract-latest.md`",
		f"- `{reports_dir()}/eval-smoke-latest.md`",
		f"- `{reports_dir()}/benchmark-<name>-<mode>-latest.md`",
		f"- `{reports_dir()}/summary-latest.md` (this file)",
		"",
	])

	meta = {
		"suite": "summary",
		"timestamp": _now_iso(),
		"status": status,
		"benchmarks": unique,
		"stack": stack_status(),
	}
	md_path, _ = _write_report_files("summary", "\n".join(lines), meta)
	return md_path


def main() -> int:
	import argparse

	parser = argparse.ArgumentParser(description="Generate Ada eval/regression reports")
	parser.add_argument(
		"suite",
		choices=("contract", "eval-smoke", "summary", "benchmark"),
		help="Report type to generate",
	)
	parser.add_argument("--junit", type=Path, help="Pytest JUnit XML path")
	parser.add_argument("--result", type=Path, help="Benchmark result JSON (for benchmark suite)")
	args = parser.parse_args()

	if args.suite == "contract":
		path = write_contract_report(junit_path=args.junit)
	elif args.suite == "eval-smoke":
		path = write_eval_smoke_report(junit_path=args.junit)
	elif args.suite == "summary":
		path = write_summary_report()
	else:
		if not args.result or not args.result.is_file():
			raise SystemExit("--result required for benchmark suite")
		payload = json.loads(args.result.read_text(encoding="utf-8"))
		path = write_benchmark_report(payload)

	print(path)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
