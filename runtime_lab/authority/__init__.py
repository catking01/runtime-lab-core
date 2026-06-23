"""R114 authority packet helpers.

This package provides deterministic, hash-bound authority packet verification
for descriptor intake only. It does not implement cryptographic signatures,
executor dispatch, tool execution, or LLM invocation.
"""

from .packet import build_authority_packet, compute_descriptor_payload_hash, verify_authority_packet

__all__ = [
    "build_authority_packet",
    "compute_descriptor_payload_hash",
    "verify_authority_packet",
]
