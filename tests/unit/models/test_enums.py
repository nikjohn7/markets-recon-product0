"""Unit tests for enum definitions."""

from __future__ import annotations

from enum import Enum
from typing import Type

import pytest

from src.models import enums


@pytest.mark.parametrize(
    ("enum_cls", "expected_values"),
    [
        (
            enums.CallDirection,
            ["OVERWEIGHT", "NEUTRAL", "UNDERWEIGHT", "UNCERTAIN"],
        ),
        (enums.Conviction, ["HIGH", "MEDIUM", "LOW"]),
        (enums.Sentiment, ["NET_POSITIVE", "NEUTRAL", "NET_NEGATIVE"]),
        (
            enums.DocumentType,
            [
                "ANNUAL_OUTLOOK",
                "MID_YEAR_OUTLOOK",
                "QUARTERLY_OUTLOOK",
                "THEMATIC_NOTE",
                "ASSET_CLASS_UPDATE",
                "OTHER",
            ],
        ),
        (
            enums.BlockType,
            [
                "HEADING",
                "PARAGRAPH",
                "BULLET",
                "TABLE_CELL",
                "CHART_TEXT",
                "FOOTNOTE",
                "DISCLAIMER",
            ],
        ),
        (enums.ConfidenceBand, ["HIGH", "MEDIUM", "LOW"]),
        (
            enums.DocumentStatus,
            ["pending", "processing", "review_required", "published", "failed"],
        ),
        (
            enums.TagType,
            [
                "ASSET_CLASS",
                "REGION",
                "THEME",
                "RISK",
                "INSTRUMENT",
                "STYLE",
                "MACRO_REGIME",
            ],
        ),
        (enums.IndicatorDirection, ["RISING", "FALLING", "STABLE", "VOLATILE"]),
    ],
)
def test_enum_values(enum_cls: Type[Enum], expected_values: list[str]) -> None:
    assert [member.value for member in enum_cls] == expected_values
    for member in enum_cls:
        assert isinstance(member, str)
        assert isinstance(member.value, str)


@pytest.mark.parametrize(
    "enum_cls",
    [
        enums.CallDirection,
        enums.Conviction,
        enums.Sentiment,
        enums.DocumentType,
        enums.BlockType,
        enums.ConfidenceBand,
        enums.DocumentStatus,
        enums.TagType,
        enums.IndicatorDirection,
    ],
)
def test_invalid_enum_value_rejected(enum_cls: Type[Enum]) -> None:
    with pytest.raises(ValueError):
        enum_cls("NOT_A_VALUE")
