"""Policy checks for admission-controller determinism and non-execution constraints."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

MISSING_GOVERNANCE_DECISION = "ADMISSION_MISSING_GOVERNANCE_DECISION"
INVALID_GOVERNANCE_DECISION = "ADMISSION_GOVERNANCE_DECISION_NOT_APPROVED"
MISSING_GOVERNANCE_DECISION_REFERENCE = "ADMISSION_MISSING_GOVERNANCE_DECISION_REFERENCE"

MISSING_AUTHORITY_BINDING = "ADMISSION_MISSING_AUTHORITY_BINDING"
INVALID_AUTHORITY_BINDING = "ADMISSION_AUTHORITY_REQUIRED_GRANTS_INVALID"

WORKSPACE_MUTATION_NOT_ALLOWED = "ADMISSION_WORKSPACE_MUTATION_NOT_ALLOWED"
TOOL_INVOCATION_NOT_ALLOWED = "ADMISSION_TOOL_INVOCATION_NOT_ALLOWED"
LLM_INVOCATION_NOT_ALLOWED = "ADMISSION_LLM_INVOCATION_NOT_ALLOWED"



def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _governance_checks(payload: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    governance = payload.get("governance_requirements")
    if not _is_mapping(governance):
        return [MISSING_GOVERNANCE_DECISION]

    decision = governance.get("decision")
    if not decision:
        codes.append(MISSING_GOVERNANCE_DECISION)
    elif decision != "approved":
        codes.append(INVALID_GOVERNANCE_DECISION)

    decision_ref = governance.get("decision_ref")
    if not decision_ref:
        codes.append(MISSING_GOVERNANCE_DECISION_REFERENCE)

    return codes


def _authority_checks(payload: Mapping[str, Any]) -> list[str]:
    authority = payload.get("authority_binding")
    if not _is_mapping(authority):
        return [MISSING_AUTHORITY_BINDING]

    required_grants = authority.get("required_grants")
    if not isinstance(required_grants, list) or not required_grants:
        return [INVALID_AUTHORITY_BINDING]

    if any(not isinstance(grant, str) or not grant for grant in required_grants):
        return [INVALID_AUTHORITY_BINDING]

    return []


def _tool_llm_workspace_checks(payload: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []

    if "tool_invocation" in payload:
        codes.append(TOOL_INVOCATION_NOT_ALLOWED)

    if "llm_invocation" in payload:
        codes.append(LLM_INVOCATION_NOT_ALLOWED)

    if "workspace_mutation" in payload:
        codes.append(WORKSPACE_MUTATION_NOT_ALLOWED)

    return codes


def validate_admission_policy(payload: Mapping[str, Any]) -> list[str]:
    """Return all admission policy rejection codes for descriptor payload."""

    return (
        _governance_checks(payload)
        + _authority_checks(payload)
        + _tool_llm_workspace_checks(payload)
    )
