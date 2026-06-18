from __future__ import annotations

from typing import Any

from ada.email.policy import is_noreply_address

ALLOWED_MATCH_TYPES: tuple[str, ...] = (
	"sender_contains",
	"sender_domain",
	"subject_contains",
	"header_present",
	"from_noreply",
)

ALLOWED_LOGIC: tuple[str, ...] = ("all", "any")


def _validate_condition(raw: Any, rule_idx: int, cond_idx: int) -> dict[str, Any]:
	if not isinstance(raw, dict):
		raise ValueError(f"summary_skip_rules[{rule_idx}].conditions[{cond_idx}] must be an object")
	match = str(raw.get("match") or "").strip()
	pattern = str(raw.get("pattern") or "").strip() or None
	header = str(raw.get("header") or "").strip() or None
	if match not in ALLOWED_MATCH_TYPES:
		raise ValueError(f"summary_skip_rules[{rule_idx}].conditions[{cond_idx}].match is invalid: {match}")
	if match in {"sender_contains", "sender_domain", "subject_contains"} and not pattern:
		raise ValueError(
			f"summary_skip_rules[{rule_idx}].conditions[{cond_idx}].pattern is required for {match}"
		)
	if match == "header_present" and not header:
		raise ValueError(
			f"summary_skip_rules[{rule_idx}].conditions[{cond_idx}].header is required for header_present"
		)
	if match == "from_noreply" and (pattern or header):
		raise ValueError(
			f"summary_skip_rules[{rule_idx}].conditions[{cond_idx}] "
			"does not accept pattern/header for from_noreply"
		)
	item: dict[str, Any] = {"match": match}
	if pattern:
		item["pattern"] = pattern
	if header:
		item["header"] = header
	return item


def _normalize_rule(raw: dict[str, Any], idx: int) -> dict[str, Any]:
	rule_id = str(raw.get("id") or "").strip()
	name = str(raw.get("name") or "").strip()
	enabled = bool(raw.get("enabled", True))
	if not rule_id:
		raise ValueError(f"summary_skip_rules[{idx}].id is required")
	if not name:
		raise ValueError(f"summary_skip_rules[{idx}].name is required")

	raw_conditions = raw.get("conditions")
	if isinstance(raw_conditions, list) and raw_conditions:
		conditions = [_validate_condition(c, idx, cidx) for cidx, c in enumerate(raw_conditions)]
	elif str(raw.get("match") or "").strip():
		legacy: dict[str, Any] = {"match": str(raw.get("match") or "").strip()}
		pattern = str(raw.get("pattern") or "").strip() or None
		header = str(raw.get("header") or "").strip() or None
		if pattern:
			legacy["pattern"] = pattern
		if header:
			legacy["header"] = header
		conditions = [_validate_condition(legacy, idx, 0)]
	else:
		raise ValueError(f"summary_skip_rules[{idx}].conditions must have at least one item")

	logic = str(raw.get("logic") or "any").strip()
	if logic not in ALLOWED_LOGIC:
		raise ValueError(f"summary_skip_rules[{idx}].logic must be 'all' or 'any'")

	return {
		"id": rule_id,
		"name": name,
		"enabled": enabled,
		"logic": logic,
		"conditions": conditions,
	}


def validate_summary_skip_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
	out: list[dict[str, Any]] = []
	seen_ids: set[str] = set()
	for idx, raw in enumerate(rules):
		if not isinstance(raw, dict):
			raise ValueError(f"summary_skip_rules[{idx}] must be an object")
		item = _normalize_rule(raw, idx)
		rule_id = str(item["id"])
		if rule_id in seen_ids:
			raise ValueError(f"summary_skip_rules[{idx}].id must be unique")
		seen_ids.add(rule_id)
		out.append(item)
	return out


def _rule_conditions(raw: dict[str, Any]) -> list[dict[str, Any]]:
	conditions = raw.get("conditions")
	if isinstance(conditions, list) and conditions:
		return [c for c in conditions if isinstance(c, dict)]
	if str(raw.get("match") or "").strip():
		legacy: dict[str, Any] = {"match": str(raw.get("match") or "").strip()}
		if raw.get("pattern"):
			legacy["pattern"] = str(raw.get("pattern"))
		if raw.get("header"):
			legacy["header"] = str(raw.get("header"))
		return [legacy]
	return []


def _evaluate_condition(
	*,
	cond: dict[str, Any],
	from_address: str,
	subject: str,
	headers: dict[str, str],
) -> bool:
	addr = from_address.lower()
	sub = subject.lower()
	match = str(cond.get("match") or "")
	pattern = str(cond.get("pattern") or "").strip().lower()
	header = str(cond.get("header") or "").strip().lower()
	if match == "sender_contains" and pattern and pattern in addr:
		return True
	if match == "sender_domain" and pattern:
		domain = addr.rsplit("@", 1)[-1] if "@" in addr else ""
		return domain == pattern
	if match == "subject_contains" and pattern and pattern in sub:
		return True
	if match == "header_present" and header and header in headers:
		return True
	if match == "from_noreply" and is_noreply_address(from_address):
		return True
	return False


def evaluate_summary_skip(
	*,
	from_address: str,
	subject: str,
	headers: dict[str, str] | None,
	rules: list[dict[str, Any]] | None,
) -> str | None:
	if not rules:
		return None
	head = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
	for raw in rules:
		if not isinstance(raw, dict):
			continue
		if not bool(raw.get("enabled", True)):
			continue
		rule_id = str(raw.get("id") or "").strip()
		if not rule_id:
			continue
		conditions = _rule_conditions(raw)
		if not conditions:
			continue
		logic = str(raw.get("logic") or "any").strip()
		results = [
			_evaluate_condition(cond=cond, from_address=from_address, subject=subject, headers=head)
			for cond in conditions
		]
		matched = all(results) if logic == "all" else any(results)
		if matched:
			return rule_id
	return None
