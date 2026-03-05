from __future__ import annotations

import pytest

from mcp_toolbox.utils import (
    http_method_to_verb,
    path_to_resource_name,
    sanitize_identifier,
    to_pascal_case,
    to_snake_case,
    truncate_description,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("camelCase", "camel_case"),
        ("PascalCase", "pascal_case"),
        ("kebab-case", "kebab_case"),
        ("many words here", "many_words_here"),
        ("getHTTPResponse", "get_http_response"),
        ("  spaced value  ", "spaced_value"),
        ("already_snake", "already_snake"),
        ("naïveValue", "naïve_value"),
        ("", ""),
    ],
)
def test_to_snake_case(value: str, expected: str) -> None:
    """to_snake_case handles common naming patterns and edge cases."""

    assert to_snake_case(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("pet_store", "PetStore"),
        ("pet store api", "PetStoreApi"),
        ("alreadyPascal", "AlreadyPascal"),
        ("", ""),
    ],
)
def test_to_pascal_case(value: str, expected: str) -> None:
    """to_pascal_case converts various input styles."""

    assert to_pascal_case(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("hello-world", "hello_world"),
        ("123abc", "_123abc"),
        ("class", "class_"),
        ("***", "_"),
    ],
)
def test_sanitize_identifier(value: str, expected: str) -> None:
    """sanitize_identifier creates safe Python names."""

    assert sanitize_identifier(value) == expected


def test_truncate_description_word_boundary() -> None:
    """truncate_description truncates on a word boundary when possible."""

    text = "This is a long sentence that should be truncated cleanly at a word boundary."
    assert truncate_description(text, max_length=45) == "This is a long sentence that should be..."


def test_truncate_description_short_text() -> None:
    """truncate_description leaves short text untouched."""

    assert truncate_description("short", max_length=20) == "short"


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("GET", "list"),
        ("POST", "create"),
        ("PUT", "update"),
        ("PATCH", "update"),
        ("DELETE", "delete"),
    ],
)
def test_http_method_to_verb(method: str, expected: str) -> None:
    """http_method_to_verb maps standard CRUD methods."""

    assert http_method_to_verb(method) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/api/v1/users/{id}/orders", "orders"),
        ("/pets", "pets"),
        ("/{id}", "resource"),
        ("/", "resource"),
    ],
)
def test_path_to_resource_name(path: str, expected: str) -> None:
    """path_to_resource_name extracts the most specific resource segment."""

    assert path_to_resource_name(path) == expected
