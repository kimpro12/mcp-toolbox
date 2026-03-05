from __future__ import annotations

import re
from pathlib import Path

from mcp_toolbox.analyze import AnalyzerConfig, AuthType, analyze_spec
from mcp_toolbox.parse import ParsedSpec, parse_spec


def test_analyzer_generates_expected_tools(parsed_petstore: ParsedSpec) -> None:
    """Analyzer should convert Petstore operations into tool definitions."""

    ir = analyze_spec(parsed_petstore, AnalyzerConfig(max_tools=20))

    assert len(ir.tools) == 6
    tool_names = {tool.name for tool in ir.tools}
    assert {
        "list_pets",
        "create_pet",
        "get_pet_by_id",
        "update_pet",
        "delete_pet",
        "list_orders",
    }.issubset(tool_names)


def test_analyzer_tool_names_are_snake_case(parsed_petstore: ParsedSpec) -> None:
    """Generated tool names should be valid snake_case identifiers."""

    ir = analyze_spec(parsed_petstore, AnalyzerConfig(max_tools=20))

    for tool in ir.tools:
        assert re.match(r"^[a-z_][a-z0-9_]*$", tool.name)


def test_analyzer_parameter_types(parsed_petstore: ParsedSpec) -> None:
    """Analyzer maps parameter schemas to expected Python types."""

    ir = analyze_spec(parsed_petstore, AnalyzerConfig(max_tools=20))
    list_pets = next(tool for tool in ir.tools if tool.name == "list_pets")

    by_name = {param.python_name: param for param in list_pets.params}
    assert by_name["limit"].python_type in {"int | None", "int"}
    assert by_name["offset"].python_type in {"int | None", "int"}


def test_analyzer_detects_auth(parsed_petstore: ParsedSpec) -> None:
    """Analyzer infers auth type and environment variable naming."""

    ir = analyze_spec(parsed_petstore, AnalyzerConfig(max_tools=20))

    assert ir.auth.auth_type == AuthType.API_KEY_HEADER
    assert ir.auth.key_name == "X-API-Key"
    assert ir.auth.env_var_name.endswith("API_KEY")


def test_analyzer_filter_tags(parsed_petstore: ParsedSpec) -> None:
    """Tag filters should include only matching operations."""

    ir = analyze_spec(parsed_petstore, AnalyzerConfig(filter_tags=["store"], max_tools=20))
    assert len(ir.tools) == 1
    assert ir.tools[0].name == "list_orders"


def test_analyzer_extracts_request_body_content_type(parsed_petstore: ParsedSpec) -> None:
    """Analyzer should preserve request body media type for generation."""

    ir = analyze_spec(parsed_petstore, AnalyzerConfig(max_tools=20))
    create_pet = next(tool for tool in ir.tools if tool.name == "create_pet")

    assert create_pet.request_body_content_type == "application/json"


def test_analyzer_extracts_structured_response_metadata(parsed_petstore: ParsedSpec) -> None:
    """Analyzer should flag JSON responses as structured outputs."""

    ir = analyze_spec(parsed_petstore, AnalyzerConfig(max_tools=20))
    list_pets = next(tool for tool in ir.tools if tool.name == "list_pets")

    assert list_pets.response_content_type == "application/json"
    assert list_pets.structured_output is True
    assert list_pets.response_type == "list[Pet]"


def test_analyzer_detects_pagination_patterns(parsed_petstore: ParsedSpec) -> None:
    """Analyzer should detect common pagination conventions from query params."""

    ir = analyze_spec(parsed_petstore, AnalyzerConfig(max_tools=20))
    list_pets = next(tool for tool in ir.tools if tool.name == "list_pets")

    assert list_pets.pagination_pattern == "offset_limit"


def test_analyzer_detects_pagination_from_response_headers(tmp_path: Path) -> None:
    """Analyzer should detect link-header pagination hints from responses."""

    spec = tmp_path / "pagination-header.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: Pagination Header API
  version: "1.0"
paths:
  /items:
    get:
      operationId: listItems
      responses:
        "200":
          description: ok
          headers:
            Link:
              description: pagination links
              schema:
                type: string
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      type: string
""".strip(),
        encoding="utf-8",
    )

    ir = analyze_spec(parse_spec(spec), AnalyzerConfig(max_tools=10))
    tool = next(tool for tool in ir.tools if tool.name == "list_items")

    assert tool.pagination_pattern == "link_header"


def test_analyzer_collects_models_with_optional_fields(parsed_petstore: ParsedSpec) -> None:
    """Collected models should include optional fields as Optional types."""

    ir = analyze_spec(parsed_petstore, AnalyzerConfig(max_tools=20))
    pet_model = next(model for model in ir.models if model.name == "Pet")

    fields_by_name = {field.python_name: field for field in pet_model.fields}
    assert fields_by_name["id"].required is True
    assert fields_by_name["name"].required is True
    assert fields_by_name["tag"].required is False
    assert "| None" in fields_by_name["tag"].python_type


def test_analyzer_detects_parent_model_from_all_of(tmp_path: Path) -> None:
    """Analyzer should preserve parent relationship for allOf-derived models."""

    spec = tmp_path / "inheritance.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: Inheritance API
  version: "1.0"
paths:
  /noop:
    get:
      operationId: noop
      responses:
        "200":
          description: ok
components:
  schemas:
    Base:
      type: object
      required: [id]
      properties:
        id:
          type: string
    Child:
      allOf:
        - $ref: "#/components/schemas/Base"
        - type: object
          required: [name]
          properties:
            name:
              type: string
""".strip(),
        encoding="utf-8",
    )

    ir = analyze_spec(parse_spec(spec), AnalyzerConfig(max_tools=10))
    child = next(model for model in ir.models if model.name == "Child")

    assert child.parent == "Base"
    field_names = {field.name for field in child.fields}
    assert "name" in field_names
    assert "id" not in field_names


def test_analyzer_auth_prefers_bearer_over_api_key(tmp_path: Path) -> None:
    """When multiple schemes are available, bearer should win by priority."""

    spec = tmp_path / "auth-priority.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: Auth Priority API
  version: "1.0"
security:
  - ApiKeyAuth: []
  - BearerAuth: []
paths:
  /ping:
    get:
      operationId: ping
      responses:
        "200":
          description: ok
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
    BearerAuth:
      type: http
      scheme: bearer
""".strip(),
        encoding="utf-8",
    )

    ir = analyze_spec(parse_spec(spec), AnalyzerConfig(max_tools=10))

    assert ir.auth.auth_type == AuthType.BEARER
    assert ir.auth.env_var_name.endswith("BEARER_TOKEN")


def test_analyzer_auth_uses_operation_level_security(tmp_path: Path) -> None:
    """Operation-level security should be considered when global security is absent."""

    spec = tmp_path / "operation-security.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: Op Security API
  version: "1.0"
paths:
  /secure:
    get:
      operationId: getSecure
      security:
        - ApiKeyQuery: []
      responses:
        "200":
          description: ok
components:
  securitySchemes:
    ApiKeyQuery:
      type: apiKey
      in: query
      name: api_key
""".strip(),
        encoding="utf-8",
    )

    ir = analyze_spec(parse_spec(spec), AnalyzerConfig(max_tools=10))

    assert ir.auth.auth_type == AuthType.API_KEY_QUERY
    assert ir.auth.key_name == "api_key"


def test_analyzer_extracts_oauth_client_credentials_metadata(tmp_path: Path) -> None:
    """OAuth2 auth config should include client-credentials metadata."""

    spec = tmp_path / "oauth-meta.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: OAuth API
  version: "1.0"
security:
  - OAuth2: []
paths:
  /me:
    get:
      operationId: getMe
      responses:
        "200":
          description: ok
components:
  securitySchemes:
    OAuth2:
      type: oauth2
      flows:
        clientCredentials:
          tokenUrl: https://example.com/oauth/token
          scopes:
            read: Read scope
            write: Write scope
""".strip(),
        encoding="utf-8",
    )

    ir = analyze_spec(parse_spec(spec), AnalyzerConfig(max_tools=10))

    assert ir.auth.auth_type == AuthType.OAUTH2
    assert ir.auth.token_url == "https://example.com/oauth/token"
    assert ir.auth.client_id_env_var.endswith("CLIENT_ID")
    assert ir.auth.client_secret_env_var.endswith("CLIENT_SECRET")
    assert ir.auth.scopes == ["read", "write"]


def test_analyzer_cookie_params_preserve_cookie_location(tmp_path: Path) -> None:
    """Cookie parameters should map to ParamLocation.COOKIE."""

    spec = tmp_path / "cookie-param.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: Cookie Param API
  version: "1.0"
paths:
  /session:
    get:
      operationId: getSession
      parameters:
        - name: session_id
          in: cookie
          required: true
          schema:
            type: string
      responses:
        "200":
          description: ok
""".strip(),
        encoding="utf-8",
    )

    ir = analyze_spec(parse_spec(spec), AnalyzerConfig(max_tools=10))
    tool = next(tool for tool in ir.tools if tool.name == "get_session")

    cookie_param = next(param for param in tool.params if param.name == "session_id")
    assert cookie_param.location.value == "cookie"


def test_analyzer_detects_cookie_api_key_auth(tmp_path: Path) -> None:
    """apiKey in cookie should map to API_KEY_COOKIE auth type."""

    spec = tmp_path / "cookie-auth.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: Cookie Auth API
  version: "1.0"
security:
  - CookieKey: []
paths:
  /me:
    get:
      operationId: getMe
      responses:
        "200":
          description: ok
components:
  securitySchemes:
    CookieKey:
      type: apiKey
      in: cookie
      name: session
""".strip(),
        encoding="utf-8",
    )

    ir = analyze_spec(parse_spec(spec), AnalyzerConfig(max_tools=10))

    assert ir.auth.auth_type == AuthType.API_KEY_COOKIE
    assert ir.auth.key_name == "session"


def test_analyzer_models_support_discriminator_unions(tmp_path: Path) -> None:
    """oneOf+discriminator schemas should be represented as root union models."""

    spec = tmp_path / "discriminator.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: Discriminator API
  version: "1.0"
paths:
  /pet:
    get:
      operationId: getPet
      responses:
        "200":
          description: ok
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/PetResult"
components:
  schemas:
    Cat:
      type: object
      properties:
        kind:
          type: string
          enum: [cat]
        meows:
          type: boolean
    Dog:
      type: object
      properties:
        kind:
          type: string
          enum: [dog]
        barks:
          type: boolean
    PetResult:
      oneOf:
        - $ref: "#/components/schemas/Cat"
        - $ref: "#/components/schemas/Dog"
      discriminator:
        propertyName: kind
""".strip(),
        encoding="utf-8",
    )

    ir = analyze_spec(parse_spec(spec), AnalyzerConfig(max_tools=10))
    model = next(model for model in ir.models if model.name == "PetResult")
    tool = next(tool for tool in ir.tools if tool.name == "get_pet")

    assert model.root_type == "Cat | Dog"
    assert model.discriminator_field == "kind"
    assert tool.response_type == "PetResult"
