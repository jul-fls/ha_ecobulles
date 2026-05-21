"""Tests for Ecobulles API request shaping."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

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
