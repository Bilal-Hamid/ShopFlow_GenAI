"""Rate limiter unit behaviour against real Redis."""

import pytest
from starlette.requests import Request

from app.api.errors import ProblemException
from app.api.rate_limit import RateLimiter


def _request(ip: str = "1.2.3.4") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/x",
        "headers": [],
        "client": (ip, 12345),
    }
    return Request(scope)


async def test_allows_up_to_limit_then_blocks():
    limiter = RateLimiter(limit=2, scope="test", identifier=lambda r: r.client.host)
    req = _request()

    await limiter(req)  # 1
    await limiter(req)  # 2
    with pytest.raises(ProblemException) as exc:
        await limiter(req)  # 3 -> over limit

    assert exc.value.status_code == 429
    assert exc.value.headers is not None
    assert "Retry-After" in exc.value.headers


async def test_separate_identifiers_have_separate_budgets():
    limiter = RateLimiter(limit=1, scope="test2", identifier=lambda r: r.client.host)
    await limiter(_request("10.0.0.1"))
    # Different IP -> its own counter, still allowed.
    await limiter(_request("10.0.0.2"))
