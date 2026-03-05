from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ParamLocation(Enum):
    """Location of a parameter in HTTP request composition."""

    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"
    BODY = "body"


class AuthType(Enum):
    """Supported authentication schemes for generated MCP servers."""

    NONE = "none"
    API_KEY_HEADER = "api_key_header"
    API_KEY_QUERY = "api_key_query"
    API_KEY_COOKIE = "api_key_cookie"
    BEARER = "bearer"
    BASIC = "basic"
    OAUTH2 = "oauth2"


@dataclass
class ParamDef:
    """Describes a generated tool/model parameter."""

    name: str
    python_name: str
    python_type: str
    location: ParamLocation
    required: bool
    description: str
    default: Any | None = None
    enum_values: list[str] | None = None
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolDefinition:
    """Intermediate representation for one generated MCP tool."""

    name: str
    description: str
    http_method: str
    path: str
    params: list[ParamDef]
    request_body_type: str | None
    response_type: str
    request_body_content_type: str | None = None
    response_content_type: str | None = None
    structured_output: bool = False
    pagination_pattern: str | None = None
    selection_reason: str = ""
    tags: list[str] = field(default_factory=list)
    operation_id: str | None = None


@dataclass
class AuthConfig:
    """Detected authentication configuration for generated server."""

    auth_type: AuthType
    key_name: str = ""
    env_var_name: str = ""
    token_url: str = ""
    client_id_env_var: str = ""
    client_secret_env_var: str = ""
    scopes: list[str] = field(default_factory=list)


@dataclass
class ModelDefinition:
    """Intermediate representation for schema models."""

    name: str
    fields: list[ParamDef]
    description: str = ""
    parent: str | None = None
    root_type: str | None = None
    additional_properties: bool | None = None
    discriminator_field: str | None = None


@dataclass
class ServerIR:
    """Complete intermediate representation used by template generation."""

    server_name: str
    server_title: str
    server_description: str
    base_url: str
    tools: list[ToolDefinition]
    auth: AuthConfig
    models: list[ModelDefinition]
    dependencies: list[str]
