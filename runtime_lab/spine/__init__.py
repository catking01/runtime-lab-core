"""Unified local spine seal for R120.

R120 seals the local R114-R119 evidence chain for the bounded
`write_text_artifact` path. It validates receipts and replay evidence only; it
does not dispatch executors, invoke tools, invoke LLMs, run shell commands, or
use network access.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from runtime_lab.authority.canonical import canonical_hash
from runtime_lab.replay import canonical_replay_hash, replay_ledger_chain

SPINE_INPUT_MALFORMED = "SPINE_INPUT_MALFORMED"
SPINE_EXPECTED_STATE_MALFORMED = "SPINE_EXPECTED_STATE_MALFORMED"
SPINE_UNSUPPORTED_ACTION = "SPINE_UNSUPPORTED_ACTION"
SPINE_FORBIDDEN_FIELD = "SPINE_FORBIDDEN_FIELD"
SPINE_ARBITRARY_EXECUTOR_DISPATCH_REJECTED = "SPINE_ARBITRARY_EXECUTOR_DISPATCH_REJECTED"
SPINE_CLAIM_BOUNDARY_REJECTED = "SPINE_CLAIM_BOUNDARY_REJECTED"
SPINE_DESCRIPTOR_HASH_MISMATCH = "SPINE_DESCRIPTOR_HASH_MISMATCH"
SPINE_ADMISSION_RECEIPT_MISSING = "SPINE_ADMISSION_RECEIPT_MISSING"
SPINE_ADMISSION_RECEIPT_MISMATCH = "SPINE_ADMISSION_RECEIPT_MISMATCH"
SPINE_AUTHORITY_RECEIPT_MISSING = "SPINE_AUTHORITY_RECEIPT_MISSING"
SPINE_AUTHORITY_RECEIPT_MISMATCH = "SPINE_AUTHORITY_RECEIPT_MISMATCH"
SPINE_WORKSPACE_TRANSACTION_RECEIPT_MISSING = "SPINE_WORKSPACE_TRANSACTION_RECEIPT_MISSING"
SPINE_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH = "SPINE_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH"
SPINE_ARTIFACT_RECEIPT_MISSING = "SPINE_ARTIFACT_RECEIPT_MISSING"
SPINE_ARTIFACT_RECEIPT_MISMATCH = "SPINE_ARTIFACT_RECEIPT_MISMATCH"
SPINE_EXECUTOR_RECEIPT_MISSING = "SPINE_EXECUTOR_RECEIPT_MISSING"
SPINE_EXECUTOR_RECEIPT_MISMATCH = "SPINE_EXECUTOR_RECEIPT_MISMATCH"
SPINE_REPLAY_RECEIPT_MISSING = "SPINE_REPLAY_RECEIPT_MISSING"
SPINE_REPLAY_RECEIPT_MISMATCH = "SPINE_REPLAY_RECEIPT_MISMATCH"
SPINE_VALIDATION_RECEIPT_MISSING = "SPINE_VALIDATION_RECEIPT_MISSING"
SPINE_VALIDATION_RECEIPT_MISMATCH = "SPINE_VALIDATION_RECEIPT_MISMATCH"
SPINE_LEDGER_INVALID = "SPINE_LEDGER_INVALID"
SPINE_LEDGER_HEAD_MISMATCH = "SPINE_LEDGER_HEAD_MISMATCH"
SPINE_LEDGER_EVENT_COUNT_MISMATCH = "SPINE_LEDGER_EVENT_COUNT_MISMATCH"
SPINE_REQUIRED_EVENT_MISSING = "SPINE_REQUIRED_EVENT_MISSING"
SPINE_ARTIFACT_CONTENT_HASH_MISMATCH = "SPINE_ARTIFACT_CONTENT_HASH_MISMATCH"
SPINE_EXECUTOR_OUTPUT_HASH_MISMATCH = "SPINE_EXECUTOR_OUTPUT_HASH_MISMATCH"
SPINE_OUTPUT_PATH_ABSOLUTE_REJECTED = "SPINE_OUTPUT_PATH_ABSOLUTE_REJECTED"
SPINE_OUTPUT_PATH_TRAVERSAL_REJECTED = "SPINE_OUTPUT_PATH_TRAVERSAL_REJECTED"
SPINE_OUTPUT_PATH_OUTSIDE_ALLOWED_ROOT = "SPINE_OUTPUT_PATH_OUTSIDE_ALLOWED_ROOT"
SPINE_DENIED_PATH_REJECTED = "SPINE_DENIED_PATH_REJECTED"

ALLOWED_ACTION = "write_text_artifact"
ALLOWED_LOCAL_CAPABILITY_CLAIMS = {
    "R120_UNIFIED_LOCAL_SPINE_SEAL_WORKTREE_LOCAL_VALIDATION_PASS",
    "BOUNDED_LOCAL_RUNTIME_CAPABILITY_FOR_WRITE_TEXT_ARTIFACT_ONLY_LOCAL_VALIDATION_PASS",
}
FORBIDDEN_CLAIM_TOKENS = {
    "REMOTE_SEALED_PASS",
    "GENERAL_TASK_EXECUTION_PROVEN",
    "ARBITRARY_EXECUTOR_DISPATCH_PROVEN",
    "TOOL_EXECUTION_PROVEN",
    "LLM_INVOCATION_PROVEN",
    "NETWORK_EXECUTION_PROVEN",
    "PRODUCTION_READY",
    "TEAM_RUNTIME_PROVEN",
    "ORGANIZATION_RUNTIME_PROVEN",
    "ACS_PROVEN",
    "R121_EXECUTOR_EXPANSION",
    "R130_TEAM_RUNTIME",
}
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
}
REPLAY_TO_SPINE_REJECTION = {
    "REPLAY_LEDGER_INVALID": SPINE_LEDGER_INVALID,
    "REPLAY_LEDGER_HEAD_MISMATCH": SPINE_LEDGER_HEAD_MISMATCH,
    "REPLAY_EVENT_COUNT_MISMATCH": SPINE_LEDGER_EVENT_COUNT_MISMATCH,
    "REPLAY_REQUIRED_EVENT_MISSING": SPINE_REQUIRED_EVENT_MISSING,
    "REPLAY_DESCRIPTOR_HASH_MISMATCH": SPINE_DESCRIPTOR_HASH_MISMATCH,
    "REPLAY_AUTHORITY_RECEIPT_MISMATCH": SPINE_AUTHORITY_RECEIPT_MISMATCH,
    "REPLAY_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH": SPINE_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH,
    "REPLAY_ARTIFACT_RECEIPT_MISMATCH": SPINE_ARTIFACT_RECEIPT_MISMATCH,
    "REPLAY_EXECUTOR_RECEIPT_MISMATCH": SPINE_EXECUTOR_RECEIPT_MISMATCH,
    "REPLAY_VALIDATION_RECEIPT_MISMATCH": SPINE_VALIDATION_RECEIPT_MISMATCH,
    "REPLAY_ARTIFACT_CONTENT_HASH_MISMATCH": SPINE_ARTIFACT_CONTENT_HASH_MISMATCH,
    "REPLAY_EXECUTOR_OUTPUT_HASH_MISMATCH": SPINE_EXECUTOR_OUTPUT_HASH_MISMATCH,
}


@dataclass(frozen=True)
class SpineSealExpectedState:
    task_id: str
    descriptor_hash: str
    admission_receipt_hash: str
    authority_receipt_hash: str
    workspace_transaction_receipt_hash: str
    artifact_receipt_hash: str
    executor_receipt_hash: str
    ledger_head_hash: str
    ledger_event_count: int
    replay_receipt_hash: str
    validation_receipt_hash: str
    artifact_content_hash: str
    executor_output_hash: str
    required_event_types: tuple[str, ...]


@dataclass(frozen=True)
class UnifiedSpineSealRequest:
    action: str
    task_id: str
    descriptor_hash: str
    output_path: str
    allowed_roots: tuple[str, ...]
    denied_paths: tuple[str, ...]
    ledger: tuple[Mapping[str, Any], ...]
    receipt_graph: Mapping[str, Mapping[str, Any]]
    replay_receipt: Mapping[str, Any]
    expected_state: SpineSealExpectedState
    capability_claims: tuple[str, ...] = ()


@dataclass(frozen=True)
class UnifiedSpineSealReceipt:
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class UnifiedSpineValidationReport:
    payload: Mapping[str, Any]


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _is_hash(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("sha256:") and len(value.removeprefix("sha256:")) == 64


def _dedupe(codes: list[str]) -> list[str]:
    return list(dict.fromkeys(codes))


def _non_execution_flags() -> dict[str, bool]:
    return {
        "executor_dispatch_performed": False,
        "tool_invocation_performed": False,
        "llm_invocation_performed": False,
        "network_access_performed": False,
        "shell_invocation_performed": False,
        "workspace_mutation_performed": False,
        "artifact_mutation_performed": False,
        "ledger_mutation_performed": False,
        "arbitrary_executor_dispatch_supported": False,
    }


def _result(*, accepted: bool, status: str, rejection_codes: list[str], receipt: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "accepted": accepted,
        "status": status,
        "rejection_codes": _dedupe(rejection_codes),
        "receipt": receipt,
    }
    result.update(_non_execution_flags())
    return result


def _reject(code: str) -> dict[str, Any]:
    return _result(accepted=False, status="rejected", rejection_codes=[code])


def _seal_hash_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(receipt)
    payload.pop("final_spine_seal_hash", None)
    return payload


def canonical_spine_seal_hash(payload: Mapping[str, Any]) -> str:
    """Return the deterministic R120 seal hash for a receipt-like payload."""

    return canonical_hash(_seal_hash_payload(payload))


def _request_from_mapping(value: Mapping[str, Any]) -> UnifiedSpineSealRequest | None:
    expected = value.get("expected_state")
    if isinstance(expected, SpineSealExpectedState):
        expected_state = expected
    elif _is_mapping(expected):
        try:
            expected_state = SpineSealExpectedState(**dict(expected))
        except TypeError:
            return None
    else:
        return None
    try:
        return UnifiedSpineSealRequest(
            action=value["action"],
            task_id=value["task_id"],
            descriptor_hash=value["descriptor_hash"],
            output_path=value["output_path"],
            allowed_roots=tuple(value["allowed_roots"]),
            denied_paths=tuple(value["denied_paths"]),
            ledger=tuple(value["ledger"]),
            receipt_graph=value["receipt_graph"],
            replay_receipt=value["replay_receipt"],
            expected_state=expected_state,
            capability_claims=tuple(value.get("capability_claims", ())),
        )
    except (KeyError, TypeError):
        return None


def _coerce_request(request: Any) -> tuple[UnifiedSpineSealRequest | None, str | None]:
    if isinstance(request, UnifiedSpineSealRequest):
        return request, None
    if not _is_mapping(request):
        return None, SPINE_INPUT_MALFORMED
    request_map = dict(request)
    if "executor_dispatch" in request_map:
        return None, SPINE_ARBITRARY_EXECUTOR_DISPATCH_REJECTED
    if FORBIDDEN_REQUEST_FIELDS & set(request_map):
        return None, SPINE_FORBIDDEN_FIELD
    coerced = _request_from_mapping(request_map)
    if coerced is None:
        return None, SPINE_INPUT_MALFORMED
    return coerced, None


def _state_is_well_formed(state: SpineSealExpectedState) -> bool:
    required_hashes = (
        state.descriptor_hash,
        state.admission_receipt_hash,
        state.authority_receipt_hash,
        state.workspace_transaction_receipt_hash,
        state.artifact_receipt_hash,
        state.executor_receipt_hash,
        state.ledger_head_hash,
        state.replay_receipt_hash,
        state.validation_receipt_hash,
        state.artifact_content_hash,
        state.executor_output_hash,
    )
    return (
        isinstance(state.task_id, str)
        and bool(state.task_id)
        and isinstance(state.ledger_event_count, int)
        and state.ledger_event_count >= 0
        and all(_is_hash(item) for item in required_hashes)
        and all(isinstance(item, str) and item for item in state.required_event_types)
    )


def _path_within_root(path: str, root: str) -> bool:
    normalized_path = str(PurePosixPath(path))
    normalized_root = str(PurePosixPath(root))
    return normalized_path == normalized_root or normalized_path.startswith(f"{normalized_root}/")


def _path_error(request: UnifiedSpineSealRequest) -> str | None:
    path = PurePosixPath(request.output_path)
    if path.is_absolute():
        return SPINE_OUTPUT_PATH_ABSOLUTE_REJECTED
    if any(part == ".." for part in path.parts):
        return SPINE_OUTPUT_PATH_TRAVERSAL_REJECTED
    normalized = str(path)
    denied = {str(PurePosixPath(item)) for item in request.denied_paths}
    if normalized in denied:
        return SPINE_DENIED_PATH_REJECTED
    if not any(_path_within_root(normalized, root) for root in request.allowed_roots):
        return SPINE_OUTPUT_PATH_OUTSIDE_ALLOWED_ROOT
    return None


def _claim_error(claims: Sequence[str]) -> str | None:
    if not all(isinstance(claim, str) for claim in claims):
        return SPINE_CLAIM_BOUNDARY_REJECTED
    for claim in claims:
        if claim not in ALLOWED_LOCAL_CAPABILITY_CLAIMS:
            return SPINE_CLAIM_BOUNDARY_REJECTED
        if any(token in claim for token in FORBIDDEN_CLAIM_TOKENS):
            return SPINE_CLAIM_BOUNDARY_REJECTED
    return None


def _graph_node(graph: Mapping[str, Any], key: str, missing_code: str) -> tuple[Mapping[str, Any] | None, str | None]:
    node = graph.get(key)
    if not _is_mapping(node):
        return None, missing_code
    return node, None


def _graph_error(request: UnifiedSpineSealRequest) -> str | None:
    graph = request.receipt_graph
    if not _is_mapping(graph):
        return SPINE_INPUT_MALFORMED
    state = request.expected_state
    admission, error = _graph_node(graph, "admission", SPINE_ADMISSION_RECEIPT_MISSING)
    if error:
        return error
    authority, error = _graph_node(graph, "authority", SPINE_AUTHORITY_RECEIPT_MISSING)
    if error:
        return error
    workspace, error = _graph_node(graph, "workspace_transaction", SPINE_WORKSPACE_TRANSACTION_RECEIPT_MISSING)
    if error:
        return error
    artifact, error = _graph_node(graph, "artifact", SPINE_ARTIFACT_RECEIPT_MISSING)
    if error:
        return error
    executor, error = _graph_node(graph, "executor", SPINE_EXECUTOR_RECEIPT_MISSING)
    if error:
        return error
    validation, error = _graph_node(graph, "validation", SPINE_VALIDATION_RECEIPT_MISSING)
    if error:
        return error

    if admission.get("receipt_hash") != state.admission_receipt_hash:
        return SPINE_ADMISSION_RECEIPT_MISMATCH
    if admission.get("task_id") not in (None, state.task_id) or admission.get("descriptor_hash") not in (None, state.descriptor_hash):
        return SPINE_DESCRIPTOR_HASH_MISMATCH
    if authority.get("receipt_hash") != state.authority_receipt_hash:
        return SPINE_AUTHORITY_RECEIPT_MISMATCH
    if workspace.get("transaction_hash") != state.workspace_transaction_receipt_hash:
        return SPINE_WORKSPACE_TRANSACTION_RECEIPT_MISMATCH
    if artifact.get("receipt_hash") != state.artifact_receipt_hash:
        return SPINE_ARTIFACT_RECEIPT_MISMATCH
    if executor.get("receipt_hash") != state.executor_receipt_hash:
        return SPINE_EXECUTOR_RECEIPT_MISMATCH
    if validation.get("receipt_hash") != state.validation_receipt_hash:
        return SPINE_VALIDATION_RECEIPT_MISMATCH
    if artifact.get("content_hash") != state.artifact_content_hash:
        return SPINE_ARTIFACT_CONTENT_HASH_MISMATCH
    if executor.get("content_hash") != state.executor_output_hash:
        return SPINE_EXECUTOR_OUTPUT_HASH_MISMATCH
    return None


def _replay_request(request: UnifiedSpineSealRequest) -> dict[str, Any]:
    state = request.expected_state
    return {
        "ledger": [dict(event) for event in request.ledger],
        "expected_state": {
            "expected_event_count": state.ledger_event_count,
            "expected_ledger_chain_hash": state.ledger_head_hash,
            "required_event_types": list(state.required_event_types),
            "task_id": state.task_id,
            "descriptor_hash": state.descriptor_hash,
            "authority_receipt_hash": state.authority_receipt_hash,
            "workspace_transaction_receipt_hash": state.workspace_transaction_receipt_hash,
            "artifact_receipt_hash": state.artifact_receipt_hash,
            "executor_receipt_hash": state.executor_receipt_hash,
            "validation_receipt_hash": state.validation_receipt_hash,
            "artifact_content_hash": state.artifact_content_hash,
            "executor_output_hash": state.executor_output_hash,
        },
        "receipt_graph": dict(request.receipt_graph),
    }


def _replay_error(request: UnifiedSpineSealRequest) -> tuple[dict[str, Any] | None, str | None]:
    replay_result = replay_ledger_chain(_replay_request(request))
    if not replay_result.get("accepted", False):
        codes = replay_result.get("rejection_codes", [])
        if "REPLAY_EVENT_COUNT_MISMATCH" in codes:
            return None, SPINE_LEDGER_EVENT_COUNT_MISMATCH
        for code in codes:
            return None, REPLAY_TO_SPINE_REJECTION.get(code, SPINE_LEDGER_INVALID)
        return None, SPINE_LEDGER_INVALID
    return replay_result, None


def _replay_receipt_error(request: UnifiedSpineSealRequest, replay_result: Mapping[str, Any]) -> str | None:
    receipt = request.replay_receipt
    if not _is_mapping(receipt) or not receipt:
        return SPINE_REPLAY_RECEIPT_MISSING
    provided_hash = receipt.get("receipt_hash")
    if not _is_hash(provided_hash) or canonical_replay_hash(receipt) != provided_hash:
        return SPINE_REPLAY_RECEIPT_MISMATCH
    expected_hash = request.expected_state.replay_receipt_hash
    if provided_hash != expected_hash:
        return SPINE_REPLAY_RECEIPT_MISMATCH
    generated = replay_result.get("receipt")
    if not _is_mapping(generated) or generated.get("receipt_hash") != provided_hash:
        return SPINE_REPLAY_RECEIPT_MISMATCH
    return None


def _accepted_receipt(request: UnifiedSpineSealRequest, replay_result: Mapping[str, Any]) -> dict[str, Any]:
    state = request.expected_state
    receipt = {
        "schema_version": "unified_local_spine_seal_receipt.v1",
        "seal": "R120_UNIFIED_LOCAL_SPINE_SEAL",
        "status": "R120_UNIFIED_LOCAL_SPINE_SEAL_WORKTREE_LOCAL_VALIDATION_PASS",
        "capability": "BOUNDED_LOCAL_RUNTIME_CAPABILITY_FOR_WRITE_TEXT_ARTIFACT_ONLY_LOCAL_VALIDATION_PASS",
        "action": ALLOWED_ACTION,
        "task_id": state.task_id,
        "descriptor_hash": state.descriptor_hash,
        "admission_receipt_hash": state.admission_receipt_hash,
        "authority_receipt_hash": state.authority_receipt_hash,
        "workspace_transaction_receipt_hash": state.workspace_transaction_receipt_hash,
        "artifact_receipt_hash": state.artifact_receipt_hash,
        "executor_receipt_hash": state.executor_receipt_hash,
        "ledger_head_hash": state.ledger_head_hash,
        "ledger_event_count": state.ledger_event_count,
        "replay_receipt_hash": state.replay_receipt_hash,
        "validation_receipt_hash": state.validation_receipt_hash,
        "artifact_content_hash": state.artifact_content_hash,
        "executor_output_hash": state.executor_output_hash,
        "required_event_types": list(state.required_event_types),
        "output_path": request.output_path,
        "remote_sealed_pass_claimed": False,
        "general_runtime_capability_claimed": False,
        "arbitrary_executor_dispatch_claimed": False,
        "tool_execution_claimed": False,
        "llm_invocation_claimed": False,
        "network_execution_claimed": False,
        "production_ready_claimed": False,
        "team_runtime_claimed": False,
        "organization_runtime_claimed": False,
        "acs_claimed": False,
        "executor_dispatch_performed": False,
        "tool_invocation_performed": False,
        "llm_invocation_performed": False,
        "network_access_performed": False,
        "shell_invocation_performed": False,
        "workspace_mutation_performed": False,
        "artifact_mutation_performed": False,
        "ledger_mutation_performed": False,
        "replay_receipt_observed": replay_result["receipt"]["receipt_hash"],
        "final_spine_seal_hash": "",
    }
    receipt["final_spine_seal_hash"] = canonical_spine_seal_hash(receipt)
    return receipt


def seal_unified_local_spine(request: Any) -> dict[str, Any]:
    """Validate and seal the bounded local R114-R119 evidence chain."""

    coerced, error = _coerce_request(request)
    if error:
        return _reject(error)
    if coerced is None:
        return _reject(SPINE_INPUT_MALFORMED)
    if coerced.action != ALLOWED_ACTION:
        return _reject(SPINE_UNSUPPORTED_ACTION)
    if coerced.task_id != coerced.expected_state.task_id or coerced.descriptor_hash != coerced.expected_state.descriptor_hash:
        return _reject(SPINE_DESCRIPTOR_HASH_MISMATCH)
    if not _state_is_well_formed(coerced.expected_state):
        return _reject(SPINE_EXPECTED_STATE_MALFORMED)

    for check in (_path_error(coerced), _claim_error(coerced.capability_claims), _graph_error(coerced)):
        if check:
            return _reject(check)

    replay_result, replay_error = _replay_error(coerced)
    if replay_error:
        return _reject(replay_error)
    assert replay_result is not None

    replay_receipt_error = _replay_receipt_error(coerced, replay_result)
    if replay_receipt_error:
        return _reject(replay_receipt_error)

    receipt = _accepted_receipt(coerced, replay_result)
    return _result(accepted=True, status="sealed", rejection_codes=[], receipt=receipt)


def validate_unified_local_spine(request: Any) -> dict[str, Any]:
    """Alias for R120 seal validation without any side effects."""

    return seal_unified_local_spine(request)
