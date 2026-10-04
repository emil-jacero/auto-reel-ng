"""``GET /api/v1/fonts``: the registry, listed. Needs no project and no database."""

from __future__ import annotations

from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.openapi import schema_dump_settings
from auto_reel_ng.render.title import BUNDLED_FONTS, DEFAULT_FONT_FAMILY


def test_the_list_is_the_registry_in_order_with_one_default() -> None:
    # The schema-dump settings point at no project and an unreachable database: the route
    # must answer from the registry alone.
    with TestClient(create_app(schema_dump_settings())) as client:
        response = client.get("/api/v1/fonts")
    assert response.status_code == 200
    fonts = response.json()
    assert [font["family"] for font in fonts] == [font.family for font in BUNDLED_FONTS]
    assert [font["display_name"] for font in fonts] == [font.display_name for font in BUNDLED_FONTS]
    assert [font["weights"] for font in fonts] == [list(font.weights) for font in BUNDLED_FONTS]
    assert all(isinstance(w, int) for font in fonts for w in font["weights"])
    assert [font["family"] for font in fonts if font["default"]] == [DEFAULT_FONT_FAMILY]
    assert len(fonts) >= 8
