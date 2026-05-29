"""Tests for Ecobulles API request shaping."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientError

from custom_components.ecobulles.api import EcobullesClient


@pytest.mark.asyncio
async def test_usage_request_keeps_current_minute_in_stopdate() -> None:
    """Do not force the API request to the previous closed hour."""
    client = EcobullesClient(session=object())
    post = AsyncMock(
        return_value={
            "data": {
                "infoconso": {
                    "total_gas": 1,
                    "total_eau": 2,
                    "graph": [{"date": "2026-05-21 00:37:00"}],
                }
            }
        }
    )

    with (
        patch(
            "custom_components.ecobulles.api.hass_now",
            return_value=datetime(2026, 5, 21, 0, 37, 42),
        ),
        patch.object(client, "_post", post),
    ):
        await client.get_total_water_and_co2_usage("eco-ref")

    post.assert_awaited_once_with(
        "getConsoBoiteItemAppFilter.php",
        {
            "eco_ref": "eco-ref",
            "eau": "1",
            "startdate": "2000-01-01 00:00:00",
            "stopdate": "2026-05-21 00:37:42",
        },
    )


def test_hash_password() -> None:
    """Password hashing matches the legacy Ecobulles API expectation."""
    assert (
        EcobullesClient.hash_password("secret")
        == "e5e9fa1ba31ecd1ae84f75caaa474f3a663f05f4"
    )


@pytest.mark.asyncio
async def test_authenticate_success() -> None:
    """Authentication returns normalized account metadata."""
    client = EcobullesClient(session=object())
    with patch.object(
        client,
        "get_login_payload",
        AsyncMock(
            return_value={
                "status": 1,
                "data": {
                    "userid": "user-id",
                    "eco_ref": "eco-ref",
                    "conso": {"boite": {"name": " Test box "}},
                },
            }
        ),
    ):
        assert await client.authenticate("user@example.com", "secret") == (
            True,
            "user-id",
            "eco-ref",
            "Test box",
        )


@pytest.mark.asyncio
async def test_authenticate_failure() -> None:
    """Authentication failure is normalized."""
    client = EcobullesClient(session=object())
    with patch.object(client, "get_login_payload", AsyncMock(return_value={"status": 0})):
        assert await client.authenticate("user@example.com", "bad") == (
            False,
            None,
            None,
            None,
        )


@pytest.mark.asyncio
async def test_authenticate_missing_payload() -> None:
    """Missing authentication payload is treated as failed authentication."""
    client = EcobullesClient(session=object())
    with patch.object(client, "get_login_payload", AsyncMock(return_value=None)):
        assert await client.authenticate("user@example.com", "bad") == (
            False,
            None,
            None,
            None,
        )


@pytest.mark.asyncio
async def test_usage_request_handles_missing_payload() -> None:
    """Missing usage payload returns no data."""
    client = EcobullesClient(session=object())
    with patch.object(client, "_post", AsyncMock(return_value=None)):
        assert await client.get_total_water_and_co2_usage("eco-ref") is None


@pytest.mark.asyncio
async def test_usage_request_handles_empty_graph() -> None:
    """Usage payloads without graph data still expose cumulative totals."""
    client = EcobullesClient(session=object())
    with patch.object(
        client,
        "_post",
        AsyncMock(
            return_value={
                "data": {
                    "infoconso": {
                        "total_gas": "1500",
                        "total_eau": "42",
                        "graph": [],
                    }
                }
            }
        ),
    ):
        assert await client.get_total_water_and_co2_usage("eco-ref") == {
            "total_gas": 1500,
            "total_eau": 42,
            "last_updated": None,
        }


@pytest.mark.asyncio
async def test_post_requires_session() -> None:
    """The API client needs an injected Home Assistant session."""
    client = EcobullesClient()
    with pytest.raises(RuntimeError, match="requires a Home Assistant session"):
        await client._post("endpoint.php", {})


@pytest.mark.asyncio
async def test_post_wraps_client_errors() -> None:
    """Aiohttp client errors are normalized."""
    session = SimpleNamespace()
    client = EcobullesClient(session=session)
    with patch.object(
        session,
        "post",
        side_effect=ClientError("network down"),
        create=True,
    ):
        with pytest.raises(RuntimeError, match="Ecobulles request failed"):
            await client._post("endpoint.php", {})
