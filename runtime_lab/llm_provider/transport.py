"""Transports for DeepSeek test provider adapter."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .errors import ProviderTimeout, ProviderTransportError


@dataclass(frozen=True)
class ProviderResponse:
    status_code: int
    payload: Any


class FakeDeepSeekTransport:
    """Deterministic fake transport for offline tests."""

    def __init__(self, response: ProviderResponse | Exception):
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout_seconds: float,
    ) -> ProviderResponse:
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "json": dict(json_body),
                "timeout_seconds": timeout_seconds,
            }
        )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class UrllibDeepSeekTransport:
    """Small urllib transport used only by explicitly gated live smoke tests."""

    def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout_seconds: float,
    ) -> ProviderResponse:
        data = json.dumps(json_body).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
                return ProviderResponse(status_code=response.status, payload=json.loads(body))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                payload: Any = json.loads(body)
            except json.JSONDecodeError:
                payload = body
            return ProviderResponse(status_code=exc.code, payload=payload)
        except socket.timeout as exc:
            raise ProviderTimeout(str(exc)) from exc
        except TimeoutError as exc:
            raise ProviderTimeout(str(exc)) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, socket.timeout):
                raise ProviderTimeout(str(exc)) from exc
            raise ProviderTransportError(str(exc)) from exc
