"""Calls to FBR. Every call is logged, and the token never leaves the request header."""

import json
import time
from dataclasses import dataclass

import requests
from django.conf import settings

from .models import FbrApiLog, FbrCredential

CONNECT_TIMEOUT = 10
READ_TIMEOUT = 45


class NoToken(Exception):
    pass


@dataclass
class Result:
    http_status: int | None = None
    body: str = ""
    data: object = None
    # True when the request can't have reached FBR, so trying again is safe.
    not_sent: bool = False
    network_error: str = ""


def sandbox_token(company) -> str:
    credential = FbrCredential.objects.filter(company=company, environment="sandbox").first()
    if credential is None:
        raise NoToken("Add the sandbox token in FBR setup first.")
    return credential.token


def call(company, method, path, *, payload=None, params=None, invoice=None) -> Result:
    token = sandbox_token(company)
    body = json.dumps(payload) if payload is not None else None
    url = settings.FBR_BASE_URL + path
    started = time.monotonic()
    result = Result()
    try:
        response = requests.request(
            method, url, data=body, params=params,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
    except requests.exceptions.ConnectTimeout:
        result.not_sent = True
        result.network_error = "Connection timed out"
    except requests.exceptions.Timeout:
        result.network_error = "No reply in time"
    except requests.exceptions.ConnectionError as exc:
        # A failure while connecting never delivered the request. Anything else might have.
        text = str(exc).lower()
        result.not_sent = any(w in text for w in ("name resolution", "getaddrinfo", "connection refused", "failed to establish", "max retries"))
        result.network_error = "Couldn't reach FBR"
    except requests.exceptions.RequestException as exc:
        result.network_error = type(exc).__name__
    else:
        result.http_status = response.status_code
        result.body = response.text
        try:
            result.data = response.json()
        except ValueError:
            result.data = None

    FbrApiLog.objects.create(
        company=company,
        invoice=invoice,
        invoice_number=invoice.number if invoice else "",
        method=method,
        path=path + (f"?{requests.compat.urlencode(params)}" if params else ""),
        request_body=body or "",
        response_body=result.body,
        http_status=result.http_status,
        network_error=result.network_error,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    return result
