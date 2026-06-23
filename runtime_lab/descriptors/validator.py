from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from . import canonical, schema
from .errors import DescriptorValidationError

NON_DETERMINISTIC_CLOCK = "B1_DESCRIPTOR_NON_DETERMINISTIC_CLOCK"
MISSING_AUTHORITY = "B1_DESCRIPTOR_MISSING_AUTHORITY_BINDING"
MISSING_GOVERNANCE = "B1_DESCRIPTOR_MISSING_GOVERNANCE_REQUIREMENT"
MISSING_REPLAY = "B1_DESCRIPTOR_MISSING_REPLAY_BINDING"
EMPTY_NON_CLAIMS = "B1_DESCRIPTOR_EMPTY_NON_CLAIMS"
AMBIGUOUS_WORKSPACE = "B1_DESCRIPTOR_AMBIGUOUS_WORKSPACE_BOUNDARY"
UNDECLARED_ARTIFACT = "B1_DESCRIPTOR_UNDECLARED_ARTIFACT_OUTPUT"
DERIVED_FIELD = "B1_DESCRIPTOR_PROPOSER_SUPPLIED_DERIVED_FIELD"
AUTHORITY_CAPABILITY = "B1_DESCRIPTOR_AUTHORITY_CAPABILITY_MISMATCH"
STAGE_B1_REQUIRED_GRANTS = ["null_descriptor_scope"]
STAGE_B1_ALLOWED_ACTIONS = ["write_text_artifact"]
FORBIDDEN_CLAIM = "B1_DESCRIPTOR_FORBIDDEN_CLAIM"
FORBIDDEN_CLAIM_TOKENS = (
    "runtime_capability_proven",
    "runtime capability proven",
    "organization_runtime_proven",
    "organization runtime proven",
    "artificial_civilization_seed_proven",
    "artificial civilization seed proven",
    "r105_r110_unified_runtime_spine_pass",
    "r105-r110 full convergence",
    "r105-r110 fully implemented",
    "r105-r110 implemented",
    "r105-r110 converged",
    "main-canonical",
    "main canonical",
    "merged to main",
    "executor implemented",
    "governance enforced",
    "replay proven",
)
SAFE_NEGATION_PATTERNS = (
    re.compile(r"\bnot proven\b"),
    re.compile(r"\bnot claimed\b"),
    re.compile(r"\bnot verified\b"),
    re.compile(r"\bno runtime capability proven\b"),
)


def _raise(code: str) -> None:
    raise DescriptorValidationError(code)


def _workspace_invalid(workspace_boundary: Mapping[str, Any]) -> bool:
    allowed_roots = workspace_boundary.get("allowed_roots")
    mode = workspace_boundary.get("mode")
    if mode != "single_root":
        return True
    if not isinstance(allowed_roots, list) or len(allowed_roots) != 1:
        return True
    root = allowed_roots[0]
    return not isinstance(root, str) or root.startswith("/") or ".." in root


def _contains_forbidden_claim(value: str) -> bool:
    normalized = value.strip().lower()
    for token in FORBIDDEN_CLAIM_TOKENS:
        if token not in normalized:
            continue
        escaped = re.escape(token)
        safe_patterns = (
            re.compile(rf"(?:^|[^a-z0-9_])no\s+{escaped}(?:[^a-z0-9_]|$)"),
            re.compile(rf"(?:^|[^a-z0-9_]){escaped}\s+not\s+(?:proven|claimed|verified)(?:[^a-z0-9_]|$)"),
        )
        if any(pattern.search(normalized) for pattern in safe_patterns):
            continue
        return True
    return False


def validate_descriptor(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        _raise("B1_DESCRIPTOR_INVALID_FIELD_TYPE")
    payload = dict(payload)

    if "authority_binding" not in payload:
        _raise(MISSING_AUTHORITY)
    if "governance_requirements" not in payload:
        _raise(MISSING_GOVERNANCE)
    if "replay_binding" not in payload:
        _raise(MISSING_REPLAY)
    if "non_claims" not in payload or not payload.get("non_claims"):
        _raise(EMPTY_NON_CLAIMS)
    if any(field in payload for field in ("canonical_hash", "descriptor_hash", "descriptor_id")):
        _raise(DERIVED_FIELD)

    schema_errors = schema.validate_schema_shape(payload)
    if schema_errors:
        _raise(schema_errors[0])

    if payload.get("determinism_level") != "STRICT":
        _raise("B1_DESCRIPTOR_INVALID_FIELD_TYPE")

    if not isinstance(payload.get("governance_requirements", {}).get("required_predicates"), list) or not payload["governance_requirements"]["required_predicates"]:
        _raise(MISSING_GOVERNANCE)

    if not isinstance(payload.get("validation_requirements", {}).get("required_validators"), list) or not payload["validation_requirements"]["required_validators"]:
        _raise("B1_DESCRIPTOR_MISSING_REQUIRED_FIELD")
    if payload["validation_requirements"].get("fail_closed") is not True:
        _raise("B1_DESCRIPTOR_MISSING_REQUIRED_FIELD")

    if not isinstance(payload.get("replay_binding"), Mapping) or not payload["replay_binding"].get("mode"):
        _raise(MISSING_REPLAY)

    if _workspace_invalid(payload.get("workspace_boundary", {})):
        _raise(AMBIGUOUS_WORKSPACE)

    if payload.get("action_type") == STAGE_B1_ALLOWED_ACTIONS[0] and not payload.get("artifact_expectation"):
        _raise(UNDECLARED_ARTIFACT)

    authority_binding = payload.get("authority_binding", {})
    capability_boundary = payload.get("capability_boundary", {})
    required_grants = authority_binding.get("required_grants")
    allowed_actions = capability_boundary.get("allowed_actions")
    if required_grants != STAGE_B1_REQUIRED_GRANTS or allowed_actions != STAGE_B1_ALLOWED_ACTIONS:
        _raise(AUTHORITY_CAPABILITY)
    if payload.get("action_type") != STAGE_B1_ALLOWED_ACTIONS[0]:
        _raise(AUTHORITY_CAPABILITY)
    if STAGE_B1_REQUIRED_GRANTS[0] in authority_binding.get("denied_grants", []):
        _raise(AUTHORITY_CAPABILITY)
    if STAGE_B1_ALLOWED_ACTIONS[0] in capability_boundary.get("denied_actions", []):
        _raise(AUTHORITY_CAPABILITY)

    for field in ("preconditions", "postconditions", "compatibility_refs", "notes", "non_claims"):
        for value in payload.get(field, []):
            if _contains_forbidden_claim(value):
                _raise(FORBIDDEN_CLAIM)

    derived_hash = canonical.canonical_hash(payload)
    descriptor_id = canonical.descriptor_id(payload)
    return payload | {
        "canonical_hash": derived_hash,
        "descriptor_hash": derived_hash,
        "descriptor_id": descriptor_id,
    }
