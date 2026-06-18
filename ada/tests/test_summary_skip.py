from __future__ import annotations

import pytest

from ada.email.summary_skip import evaluate_summary_skip, validate_summary_skip_rules


def test_evaluate_sender_domain_matches():
	rule_id = evaluate_summary_skip(
		from_address="user@mail.example.com",
		subject="hello",
		headers={},
		rules=[{"id": "r1", "name": "domain", "enabled": True, "match": "sender_domain", "pattern": "mail.example.com"}],
	)
	assert rule_id == "r1"


def test_evaluate_header_present_matches():
	rule_id = evaluate_summary_skip(
		from_address="user@example.com",
		subject="hello",
		headers={"List-Id": "<abc>"},
		rules=[{"id": "r1", "name": "list", "enabled": True, "match": "header_present", "header": "List-Id"}],
	)
	assert rule_id == "r1"


def test_evaluate_logic_all_requires_every_condition():
	rules = [
		{
			"id": "r1",
			"name": "both",
			"enabled": True,
			"logic": "all",
			"conditions": [
				{"match": "sender_domain", "pattern": "example.com"},
				{"match": "subject_contains", "pattern": "sale"},
			],
		}
	]
	assert (
		evaluate_summary_skip(
			from_address="a@example.com",
			subject="big sale",
			headers={},
			rules=rules,
		)
		== "r1"
	)
	assert (
		evaluate_summary_skip(
			from_address="a@example.com",
			subject="hello",
			headers={},
			rules=rules,
		)
		is None
	)


def test_evaluate_logic_any_matches_one_condition():
	rules = [
		{
			"id": "r1",
			"name": "either",
			"enabled": True,
			"logic": "any",
			"conditions": [
				{"match": "sender_domain", "pattern": "other.com"},
				{"match": "subject_contains", "pattern": "urgent"},
			],
		}
	]
	assert (
		evaluate_summary_skip(
			from_address="a@example.com",
			subject="urgent request",
			headers={},
			rules=rules,
		)
		== "r1"
	)


def test_validate_normalizes_legacy_rule():
	out = validate_summary_skip_rules(
		[{"id": "r1", "name": "legacy", "enabled": True, "match": "from_noreply"}]
	)
	assert out == [
		{
			"id": "r1",
			"name": "legacy",
			"enabled": True,
			"logic": "any",
			"conditions": [{"match": "from_noreply"}],
		}
	]


def test_validate_rejects_empty_conditions():
	with pytest.raises(ValueError):
		validate_summary_skip_rules(
			[{"id": "r1", "name": "bad", "enabled": True, "logic": "all", "conditions": []}]
		)


def test_validate_rejects_invalid_logic():
	with pytest.raises(ValueError):
		validate_summary_skip_rules(
			[
				{
					"id": "r1",
					"name": "bad",
					"enabled": True,
					"logic": "xor",
					"conditions": [{"match": "from_noreply"}],
				}
			]
		)


def test_validate_rejects_duplicate_id():
	with pytest.raises(ValueError):
		validate_summary_skip_rules(
			[
				{"id": "r1", "name": "a", "enabled": True, "match": "from_noreply"},
				{"id": "r1", "name": "b", "enabled": True, "match": "from_noreply"},
			]
		)
