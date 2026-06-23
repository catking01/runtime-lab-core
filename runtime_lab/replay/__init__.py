"""Read-only replay validation engine v1 for R119.

R119 reconstructs and validates the bounded R114-R118 evidence chain from a
ledger and receipt graph. It intentionally does not redispatch executors,
mutate workspaces, mutate artifacts, mutate ledgers, invoke tools, invoke LLMs,
or use network access.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime_lab.authority.canonical import canonical_hash
from runtime_lab.ledger import validate_ledger_chain

REPLAY_INPUT_MALFORMED = "REPLAY_INPUT_MALFORMED"
REPLAY_EXPECTED_STATE_MALFORMED = "REPLAY_EXPECTED_STATE_MALFORMED"
REPLAY_FORBIDDEN_FIELD = "REPLAY_FORBIDDEN_FIELD"
REPLAY_LEDGER_INVALID = "REPLAY_LEDGER_INVALID"
REPLAY_LEDGER_HEAD_MISMATCH = "REPLAY_LEDGER_HEAD_MISMATCH"
REPLAY_EVENT_COUNT_MISMATCH = "REPLAY_EVENT_COUNT_MISMATCH"
REPLAY_REQUIRED_EVENT_MISSING = "REPLAY_REQUIRED_EVENT_MISSING"
REPLAY_TASK_BINDING_MISMATCH = "REPLAY_TASK_BINDING_MISMATCH"
REPLAY_DESCRIPTOR_HASH_MISMATCH = "REPLAY_DESCRIPTOR_HASH_MISMATCH"
REPLAY_AUTHORITY_RECEIPT_MISMATCH = "REPLAY_AUTHORITY_RECEIPT_MISMATCH"
REPLAY_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH = "REPLAY_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH"
REPLAY_ARTIFACT_RECEIPT_MISMATCH = "REPLAY_ARTIFACT_RECEIPT_MISMATCH"
REPLAY_EXECUTOR_RECEIPT_MISMATCH = "REPLAY_EXECUTOR_RECEIPT_MISMATCH"
REPLAY_VALIDATION_RECEIPT_MISMATCH = "REPLAY_VALIDATION_RECEIPT_MISMATCH"
REPLAY_ARTIFACT_CONTENT_HASH_MISMATCH = "REPLAY_ARTIFACT_CONTENT_HASH_MISMATCH"
REPLAY_EXECUTOR_OUTPUT_HASH_MISMATCH = "REPLAY_EXECUTOR_OUTPUT_HASH_MISMATCH"

FORBIDDEN_REQUEST_FIELDS = {
    "shell_command",
    "subprocess",
    "command",
    "tool_call",
    "tool_invocation",
    "llm_call",
    "llm_invocation",
    "network_endpoint",
    "http_request",
    "socket",
    "executor_dispatch",
    "workspace_mutation",
    "artifact_mutation",
    "ledger_mutation",
    "r120_seal",
}

LEDGER_REJECTION_MAP = {
    "LEDGER_EXPECTED_EVENT_COUNT_MISMATCH": REPLAY_EVENT_COUNT_MISMATCH,
    "LEDGER_EXPECTED_LEDGER_CHAIN_HASH_MISMATCH": REPLAY_LEDGER_HEAD_MISMATCH,
    "LEDGER_EXPECTED_TERMINAL_EVENT_HASH_MISMATCH": REPLAY_LEDGER_HEAD_MISMATCH,
}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _is_hash(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("sha256:") and len(value.removeprefix("sha256:")) == 64


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return list(value)


def _dedupe(codes: list[str]) -> list[str]:
    return list(dict.fromkeys(codes))


def _non_mutation_flags() -> dict[str, bool]:
    return {
        "executor_redispatch_performed": False,
        "workspace_mutation_performed": False,
        "artifact_mutation_performed": False,
        "ledger_mutation_performed": False,
        "tool_invocation_performed": False,
        "llm_invocation_performed": False,
        "network_access_performed": False,
        "r120_seal_performed": False,
    }


def _result(
    *,
    accepted: bool,
    status: str,
    rejection_codes: list[str],
    ledger_chain_hash: str | None = None,
    receipt_graph: dict[str, Any] | None = None,
    receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "accepted": accepted,
        "status": status,
        "rejection_codes": _dedupe(rejection_codes),
        "ledger_chain_hash": ledger_chain_hash,
        "receipt_graph": receipt_graph,
        "receipt": receipt,
    }
    result.update(_non_mutation_flags())
    return result


def _reject(code: str) -> dict[str, Any]:
    return _result(accepted=False, status="rejected", rejection_codes=[code])


def _receipt_hash_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(receipt)
    payload.pop("receipt_hash", None)
    return payload


def canonical_replay_hash(payload: Mapping[str, Any]) -> str:
    """Return the deterministic hash for a replay receipt or report payload."""

    return canonical_hash(_receipt_hash_payload(payload))


def _ledger_events(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    if not all(_is_mapping(event) for event in value):
        return None
    return [dict(event) for event in value]


def _expected_state(value: Any) -> dict[str, Any] | None:
    if not _is_mapping(value):
        return None
    expected = dict(value)
    if "expected_event_count" in expected and not isinstance(expected["expected_event_count"], int):
        return None
    for field in (
        "expected_ledger_chain_hash",
        "expected_terminal_event_hash",
        "descriptor_hash",
        "authority_receipt_hash",
        "workspace_transaction_receipt_hash",
        "artifact_receipt_hash",
        "executor_receipt_hash",
        "validation_receipt_hash",
        "artifact_content_hash",
        "executor_output_hash",
    ):
        if field in expected and not _is_hash(expected[field]):
            return None
    if "required_event_types" in expected and _string_list(expected["required_event_types"]) is None:
        return None
    if "task_id" in expected and (not isinstance(expected["task_id"], str) or not expected["task_id"]):
        return None
    return expected


def _receipt_graph(value: Any) -> dict[str, Mapping[str, Any]] | None:
    if not _is_mapping(value):
        return None
    graph = dict(value)
    for key in ("authority", "workspace_transaction", "artifact", "executor", "validation"):
        if key in graph and not _is_mapping(graph[key]):
            return None
    return {key: dict(graph[key]) for key in graph if _is_mapping(graph[key])}


def _first_mismatch(actual: Any, expected: Any, code: str) -> str | None:
    if expected is not None and actual != expected:
        return code
    return None


def _event_binding_errors(ledger: list[Mapping[str, Any]], expected: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    checks = (
        ("task_id", REPLAY_TASK_BINDING_MISMATCH),
        ("descriptor_hash", REPLAY_DESCRIPTOR_HASH_MISMATCH),
        ("authority_receipt_hash", REPLAY_AUTHORITY_RECEIPT_MISMATCH),
        ("workspace_transaction_receipt_hash", REPLAY_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH),
        ("artifact_receipt_hash", REPLAY_ARTIFACT_RECEIPT_MISMATCH),
        ("executor_receipt_hash", REPLAY_EXECUTOR_RECEIPT_MISMATCH),
        ("validation_receipt_hash", REPLAY_VALIDATION_RECEIPT_MISMATCH),
    )
    for event in ledger:
        for field, code in checks:
            if field in event and _first_mismatch(event.get(field), expected.get(field), code):
                codes.append(code)
    return codes


def _missing_required_events(ledger: list[Mapping[str, Any]], required_event_types: list[str]) -> list[str]:
    present = {event.get("event_type") for event in ledger}
    return [event_type for event_type in required_event_types if event_type not in present]


def _graph_hash_errors(graph: Mapping[str, Mapping[str, Any]], expected: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    authority = graph.get("authority", {})
    workspace = graph.get("workspace_transaction", {})
    artifact = graph.get("artifact", {})
    executor = graph.get("executor", {})
    validation = graph.get("validation", {})

    if authority.get("receipt_hash") != expected.get("authority_receipt_hash"):
        codes.append(REPLAY_AUTHORITY_RECEIPT_MISMATCH)
    if authority.get("task_id") not in (None, expected.get("task_id")):
        codes.append(REPLAY_TASK_BINDING_MISMATCH)
    if authority.get("descriptor_hash") not in (None, expected.get("descriptor_hash")):
        codes.append(REPLAY_DESCRIPTOR_HASH_MISMATCH)

    if workspace.get("transaction_hash") != expected.get("workspace_transaction_receipt_hash"):
        codes.append(REPLAY_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH)
    if workspace.get("authority_receipt_hash") not in (None, expected.get("authority_receipt_hash")):
        codes.append(REPLAY_AUTHORITY_RECEIPT_MISMATCH)
    if workspace.get("task_id") not in (None, expected.get("task_id")):
        codes.append(REPLAY_TASK_BINDING_MISMATCH)
    if workspace.get("descriptor_hash") not in (None, expected.get("descriptor_hash")):
        codes.append(REPLAY_DESCRIPTOR_HASH_MISMATCH)

    if artifact.get("receipt_hash") != expected.get("artifact_receipt_hash"):
        codes.append(REPLAY_ARTIFACT_RECEIPT_MISMATCH)
    if artifact.get("authority_receipt_hash") not in (None, expected.get("authority_receipt_hash")):
        codes.append(REPLAY_AUTHORITY_RECEIPT_MISMATCH)
    if artifact.get("workspace_transaction_receipt_hash") not in (None, expected.get("workspace_transaction_receipt_hash")):
        codes.append(REPLAY_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH)
    if artifact.get("content_hash") != expected.get("artifact_content_hash"):
        codes.append(REPLAY_ARTIFACT_CONTENT_HASH_MISMATCH)
    if artifact.get("task_id") not in (None, expected.get("task_id")):
        codes.append(REPLAY_TASK_BINDING_MISMATCH)
    if artifact.get("descriptor_hash") not in (None, expected.get("descriptor_hash")):
        codes.append(REPLAY_DESCRIPTOR_HASH_MISMATCH)

    if executor.get("receipt_hash") != expected.get("executor_receipt_hash"):
        codes.append(REPLAY_EXECUTOR_RECEIPT_MISMATCH)
    if executor.get("authority_receipt_hash") not in (None, expected.get("authority_receipt_hash")):
        codes.append(REPLAY_AUTHORITY_RECEIPT_MISMATCH)
    if executor.get("workspace_transaction_receipt_hash") not in (None, expected.get("workspace_transaction_receipt_hash")):
        codes.append(REPLAY_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH)
    if executor.get("artifact_receipt_hash") not in (None, expected.get("artifact_receipt_hash")):
        codes.append(REPLAY_ARTIFACT_RECEIPT_MISMATCH)
    if executor.get("content_hash") != expected.get("executor_output_hash"):
        codes.append(REPLAY_EXECUTOR_OUTPUT_HASH_MISMATCH)
    if executor.get("task_id") not in (None, expected.get("task_id")):
        codes.append(REPLAY_TASK_BINDING_MISMATCH)
    if executor.get("descriptor_hash") not in (None, expected.get("descriptor_hash")):
        codes.append(REPLAY_DESCRIPTOR_HASH_MISMATCH)

    if validation.get("receipt_hash") not in (None, expected.get("validation_receipt_hash")):
        codes.append(REPLAY_VALIDATION_RECEIPT_MISMATCH)
    if validation.get("executor_receipt_hash") not in (None, expected.get("executor_receipt_hash")):
        codes.append(REPLAY_EXECUTOR_RECEIPT_MISMATCH)
    return codes


def _graph_summary(expected: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_id": expected.get("task_id"),
        "descriptor_hash": expected.get("descriptor_hash"),
        "authority_receipt_hash": expected.get("authority_receipt_hash"),
        "workspace_transaction_receipt_hash": expected.get("workspace_transaction_receipt_hash"),
        "artifact_receipt_hash": expected.get("artifact_receipt_hash"),
        "executor_receipt_hash": expected.get("executor_receipt_hash"),
        "validation_receipt_hash": expected.get("validation_receipt_hash"),
        "artifact_content_hash": expected.get("artifact_content_hash"),
        "executor_output_hash": expected.get("executor_output_hash"),
    }


def _accepted_receipt(
    *,
    expected: Mapping[str, Any],
    ledger: list[Mapping[str, Any]],
    ledger_chain_hash: str,
    terminal_event_hash: str,
) -> dict[str, Any]:
    receipt = {
        "schema_version": "replay_receipt.v1",
        "replay_engine": "read_only_replay_v1",
        "task_id": expected.get("task_id"),
        "descriptor_hash": expected.get("descriptor_hash"),
        "ledger_event_count": len(ledger),
        "ledger_chain_hash": ledger_chain_hash,
        "terminal_event_hash": terminal_event_hash,
        "authority_receipt_hash": expected.get("authority_receipt_hash"),
        "workspace_transaction_receipt_hash": expected.get("workspace_transaction_receipt_hash"),
        "artifact_receipt_hash": expected.get("artifact_receipt_hash"),
        "executor_receipt_hash": expected.get("executor_receipt_hash"),
        "validation_receipt_hash": expected.get("validation_receipt_hash"),
        "artifact_content_hash": expected.get("artifact_content_hash"),
        "executor_output_hash": expected.get("executor_output_hash"),
        "executor_redispatch_performed": False,
        "workspace_mutation_performed": False,
        "artifact_mutation_performed": False,
        "ledger_mutation_performed": False,
        "tool_invocation_performed": False,
        "llm_invocation_performed": False,
        "network_access_performed": False,
        "r120_seal_performed": False,
        "receipt_hash": "",
    }
    receipt["receipt_hash"] = canonical_replay_hash(receipt)
    return receipt


def _ledger_rejection_codes(report: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    for code in report.get("rejection_codes", []):
        if code in LEDGER_REJECTION_MAP:
            codes.append(LEDGER_REJECTION_MAP[code])
        else:
            codes.append(REPLAY_LEDGER_INVALID)
    return codes


def replay_ledger_chain(request: Any) -> dict[str, Any]:
    """Validate a bounded R118 ledger and reconstruct receipt graph evidence."""

    if not _is_mapping(request):
        return _reject(REPLAY_INPUT_MALFORMED)
    request_map = dict(request)
    if FORBIDDEN_REQUEST_FIELDS & set(request_map):
        return _reject(REPLAY_FORBIDDEN_FIELD)

    ledger = _ledger_events(request_map.get("ledger"))
    expected = _expected_state(request_map.get("expected_state"))
    graph = _receipt_graph(request_map.get("receipt_graph"))
    if ledger is None:
        return _reject(REPLAY_INPUT_MALFORMED)
    if expected is None:
        return _reject(REPLAY_EXPECTED_STATE_MALFORMED)
    if graph is None:
        return _reject(REPLAY_INPUT_MALFORMED)

    chain_report = validate_ledger_chain(
        ledger,
        expected_event_count=expected.get("expected_event_count"),
        expected_ledger_chain_hash=expected.get("expected_ledger_chain_hash"),
        expected_terminal_event_hash=expected.get("expected_terminal_event_hash"),
    )
    if not chain_report.get("accepted", False):
        return _result(accepted=False, status="rejected", rejection_codes=_ledger_rejection_codes(chain_report))

    required_event_types = _string_list(expected.get("required_event_types", [])) or []
    if _missing_required_events(ledger, required_event_types):
        return _reject(REPLAY_REQUIRED_EVENT_MISSING)

    binding_errors = _event_binding_errors(ledger, expected)
    if binding_errors:
        return _result(accepted=False, status="rejected", rejection_codes=binding_errors)

    graph_errors = _graph_hash_errors(graph, expected)
    if graph_errors:
        return _result(accepted=False, status="rejected", rejection_codes=graph_errors)

    ledger_chain_hash = chain_report["ledger_chain_hash"]
    terminal_event_hash = ledger[-1]["event_hash"] if ledger else "GENESIS"
    receipt_graph = _graph_summary(expected)
    receipt = _accepted_receipt(
        expected=expected,
        ledger=ledger,
        ledger_chain_hash=ledger_chain_hash,
        terminal_event_hash=terminal_event_hash,
    )
    return _result(
        accepted=True,
        status="replayed",
        rejection_codes=[],
        ledger_chain_hash=ledger_chain_hash,
        receipt_graph=receipt_graph,
        receipt=receipt,
    )


def validate_replay_against_expected_state(request: Any, expected_state: Any) -> dict[str, Any]:
    """Validate replay using an explicit expected state override."""

    if not _is_mapping(request):
        return _reject(REPLAY_INPUT_MALFORMED)
    request_map = dict(request)
    request_map["expected_state"] = expected_state
    return replay_ledger_chain(request_map)
