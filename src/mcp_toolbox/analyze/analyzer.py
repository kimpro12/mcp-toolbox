from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mcp_toolbox.parse import ParsedSpec
from mcp_toolbox.utils import sanitize_identifier, to_pascal_case, to_snake_case

from .models import AuthConfig, AuthType, ModelDefinition, ParamDef, ParamLocation, ServerIR, ToolDefinition
from .naming import build_tool_description, build_tool_name, ensure_unique_name, is_valid_tool_name
from .schema_mapper import openapi_type_to_python, schema_to_params
from .type_mapper import map_schema_to_typeref

HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head")
HTTP_METHOD_SORT_ORDER = {"get": 0, "post": 1, "put": 2, "patch": 3, "delete": 4, "options": 5, "head": 6}


@dataclass
class AnalyzerConfig:
    """Configuration knobs for OpenAPI → ServerIR analysis."""

    filter_tags: list[str] | None = None
    include_tags: list[str] | None = None
    exclude_tags: list[str] | None = None
    prefer_tags: list[str] | None = None
    max_tools: int = 12
    server_name: str | None = None
    body_style: str = "auto"
    enum_style: str = "literal"


@dataclass
class ToolSelectionDecision:
    """Selection decision used to explain include/exclude behavior."""

    name: str
    method: str
    path: str
    included: bool
    rank: int
    reason: str


def analyze_spec(parsed: ParsedSpec, config: AnalyzerConfig) -> ServerIR:
    """Convert ParsedSpec into ServerIR for template rendering."""

    server_name = _resolve_server_name(config.server_name, parsed.title)
    auth = _detect_auth(parsed.security_schemes, parsed.global_security, parsed.paths, server_name)

    used_tool_names: set[str] = set()
    analyzed_tools: list[tuple[int, ToolDefinition]] = []

    operation_index = 0
    for path in sorted(parsed.paths.keys()):
        path_item = parsed.paths[path]
        if not isinstance(path_item, dict):
            continue

        path_parameters = path_item.get("parameters", []) if isinstance(path_item.get("parameters", []), list) else []

        operations = [
            (method, operation)
            for method, operation in path_item.items()
            if method.lower() in HTTP_METHODS and isinstance(operation, dict)
        ]
        operations.sort(key=lambda item: _http_method_sort_key(item[0]))

        for method, operation in operations:
            tags = (
                [str(tag) for tag in operation.get("tags", [])] if isinstance(operation.get("tags", []), list) else []
            )

            include_tags = config.include_tags or config.filter_tags
            if include_tags and not set(tags).intersection(include_tags):
                continue
            if config.exclude_tags and set(tags).intersection(config.exclude_tags):
                continue

            operation_id = operation.get("operationId") if isinstance(operation.get("operationId"), str) else None
            candidate_name = build_tool_name(method.upper(), path, operation_id)
            if not is_valid_tool_name(candidate_name):
                candidate_name = sanitize_identifier(to_snake_case(candidate_name))[:64] or "tool"

            tool_name = ensure_unique_name(candidate_name, used_tool_names)
            tool_description = build_tool_description(
                method.upper(),
                path,
                operation.get("summary") if isinstance(operation.get("summary"), str) else None,
                operation.get("description") if isinstance(operation.get("description"), str) else None,
            )

            merged_parameters = _merge_parameters(path_parameters, operation.get("parameters", []))
            params = [_parameter_to_param_def(param, enum_style=config.enum_style) for param in merged_parameters]
            request_body_type, body_params, request_body_content_type = _extract_request_body_params(
                operation,
                enum_style=config.enum_style,
                body_style=config.body_style,
            )
            params.extend(body_params)
            params = _dedupe_python_names(params)

            response_type, response_content_type, structured_output = _extract_response_info(
                operation,
                schemas=parsed.schemas,
                enum_style=config.enum_style,
            )
            pagination_pattern = _detect_pagination_pattern(params, operation)

            analyzed_tools.append(
                (
                    operation_index,
                    ToolDefinition(
                        name=tool_name,
                        description=tool_description,
                        http_method=method.upper(),
                        path=path,
                        params=params,
                        request_body_type=request_body_type,
                        response_type=response_type,
                        request_body_content_type=request_body_content_type,
                        response_content_type=response_content_type,
                        structured_output=structured_output,
                        pagination_pattern=pagination_pattern,
                        tags=tags,
                        operation_id=operation_id,
                    ),
                )
            )
            operation_index += 1

    tools = _apply_tool_limits(analyzed_tools, config)
    models = _collect_models(parsed.schemas, enum_style=config.enum_style)

    dependencies = ["mcp[cli]>=1.26.0", "httpx>=0.27.1", "pydantic>=2.5"]

    return ServerIR(
        server_name=server_name,
        server_title=parsed.title or server_name.replace("_", " ").title(),
        server_description=parsed.description or f"MCP server for {parsed.title or server_name}",
        base_url=parsed.base_url,
        tools=tools,
        auth=auth,
        models=models,
        dependencies=dependencies,
    )


def explain_tool_selection(parsed: ParsedSpec, config: AnalyzerConfig) -> list[ToolSelectionDecision]:
    """Explain which tools were included/excluded and why."""

    full_config = AnalyzerConfig(
        filter_tags=config.filter_tags,
        include_tags=config.include_tags,
        exclude_tags=config.exclude_tags,
        prefer_tags=config.prefer_tags,
        max_tools=10_000,
        server_name=config.server_name,
        body_style=config.body_style,
        enum_style=config.enum_style,
    )
    full_ir = analyze_spec(parsed, full_config)

    ranked_tools = _rank_tools_for_selection(
        full_ir.tools, config.prefer_tags or config.include_tags or config.filter_tags
    )
    selected_names = {tool.name for tool in ranked_tools[: config.max_tools]}

    decisions: list[ToolSelectionDecision] = []
    for rank_index, tool in enumerate(ranked_tools, start=1):
        included = tool.name in selected_names
        if included:
            reason = f"Included in top-{config.max_tools} by heuristic rank."
            if tool.http_method.upper() == "GET":
                reason = (
                    "Included: GET endpoint prioritized and ranked within limit."
                    if config.max_tools < len(ranked_tools)
                    else "Included: within tool limit."
                )
        else:
            reason = f"Excluded by max-tools limit ({config.max_tools}); lower priority rank."

        decisions.append(
            ToolSelectionDecision(
                name=tool.name,
                method=tool.http_method,
                path=tool.path,
                included=included,
                rank=rank_index,
                reason=reason,
            )
        )

    return decisions


def _resolve_server_name(override: str | None, title: str) -> str:
    """Resolve server package name from explicit override or API title."""

    source = override or title or "generated_api"
    resolved = sanitize_identifier(to_snake_case(source))
    return resolved or "generated_api"


def _detect_auth(
    security_schemes: dict[str, Any],
    global_security: list[dict[str, Any]],
    paths: dict[str, Any],
    server_name: str,
) -> AuthConfig:
    """Detect dominant authentication configuration from OpenAPI components."""

    if not security_schemes:
        return AuthConfig(auth_type=AuthType.NONE)

    env_prefix = to_snake_case(server_name).upper() or "API"

    operation_scheme_names = _collect_operation_security_scheme_names(paths)
    global_scheme_names = _extract_requirement_scheme_names(global_security)

    candidate_scheme_names = operation_scheme_names + global_scheme_names
    if not candidate_scheme_names:
        candidate_scheme_names = [str(name) for name in sorted(security_schemes.keys(), key=str)]

    best_rank = 10_000
    best_auth: AuthConfig | None = None

    for order_index, scheme_name in enumerate(candidate_scheme_names):
        scheme = security_schemes.get(scheme_name, {})
        if not isinstance(scheme, dict):
            continue

        auth_config = _auth_config_from_scheme(scheme_name, scheme, env_prefix)
        if auth_config is None:
            continue

        rank = _auth_priority_rank(auth_config.auth_type)
        weighted_rank = rank * 100 + order_index

        if weighted_rank < best_rank:
            best_rank = weighted_rank
            best_auth = auth_config

    return best_auth or AuthConfig(auth_type=AuthType.NONE)


def _collect_operation_security_scheme_names(paths: dict[str, Any]) -> list[str]:
    """Collect security scheme names declared at operation level."""

    names: list[str] = []
    for path in sorted(paths.keys(), key=str):
        path_item = paths[path]
        if not isinstance(path_item, dict):
            continue

        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation_security = operation.get("security", [])
            names.extend(_extract_requirement_scheme_names(operation_security))

    return names


def _extract_requirement_scheme_names(requirements: Any) -> list[str]:
    """Extract scheme names from OpenAPI security requirement arrays."""

    if not isinstance(requirements, list):
        return []

    names: list[str] = []
    for requirement in requirements:
        if isinstance(requirement, dict):
            names.extend([str(name) for name in requirement.keys()])

    return names


def _auth_config_from_scheme(scheme_name: str, scheme: dict[str, Any], env_prefix: str) -> AuthConfig | None:
    """Build AuthConfig from one OpenAPI security scheme definition."""

    scheme_type = str(scheme.get("type", "")).lower()

    if scheme_type == "apikey":
        location = str(scheme.get("in", "header")).lower()
        key_name = str(scheme.get("name", "X-API-Key"))
        env_var_name = f"{env_prefix}_API_KEY"
        if location == "query":
            return AuthConfig(auth_type=AuthType.API_KEY_QUERY, key_name=key_name, env_var_name=env_var_name)
        if location == "cookie":
            return AuthConfig(auth_type=AuthType.API_KEY_COOKIE, key_name=key_name, env_var_name=env_var_name)
        return AuthConfig(auth_type=AuthType.API_KEY_HEADER, key_name=key_name, env_var_name=env_var_name)

    if scheme_type == "http":
        http_scheme = str(scheme.get("scheme", "")).lower()
        if http_scheme == "bearer":
            return AuthConfig(auth_type=AuthType.BEARER, env_var_name=f"{env_prefix}_BEARER_TOKEN")
        if http_scheme == "basic":
            return AuthConfig(auth_type=AuthType.BASIC, env_var_name=f"{env_prefix}_USERNAME")

    if scheme_type == "oauth2":
        token_url, scopes = _extract_oauth2_client_credentials(scheme)
        return AuthConfig(
            auth_type=AuthType.OAUTH2,
            env_var_name=f"{env_prefix}_ACCESS_TOKEN",
            token_url=token_url,
            client_id_env_var=f"{env_prefix}_CLIENT_ID",
            client_secret_env_var=f"{env_prefix}_CLIENT_SECRET",
            scopes=scopes,
            key_name=scheme_name,
        )

    return None


def _extract_oauth2_client_credentials(scheme: dict[str, Any]) -> tuple[str, list[str]]:
    """Extract OAuth2 client credentials token URL and scopes."""

    flows = scheme.get("flows", {}) if isinstance(scheme.get("flows", {}), dict) else {}
    client_credentials = (
        flows.get("clientCredentials", {}) if isinstance(flows.get("clientCredentials", {}), dict) else {}
    )

    token_url = str(client_credentials.get("tokenUrl", ""))
    raw_scopes = client_credentials.get("scopes", {})
    scopes = [str(scope) for scope in raw_scopes.keys()] if isinstance(raw_scopes, dict) else []

    return token_url, scopes


def _auth_priority_rank(auth_type: AuthType) -> int:
    """Lower rank means higher auth selection priority."""

    ranking = {
        AuthType.BEARER: 0,
        AuthType.OAUTH2: 1,
        AuthType.API_KEY_HEADER: 2,
        AuthType.API_KEY_QUERY: 3,
        AuthType.API_KEY_COOKIE: 4,
        AuthType.BASIC: 5,
        AuthType.NONE: 6,
    }
    return ranking.get(auth_type, 99)


def _merge_parameters(path_params: list[Any], operation_params: Any) -> list[dict[str, Any]]:
    """Merge path-level and operation-level parameters with operation precedence."""

    merged: dict[tuple[str, str], dict[str, Any]] = {}

    for raw_param in path_params:
        if not isinstance(raw_param, dict):
            continue
        key = (str(raw_param.get("name", "")), str(raw_param.get("in", "query")))
        merged[key] = raw_param

    if isinstance(operation_params, list):
        for raw_param in operation_params:
            if not isinstance(raw_param, dict):
                continue
            key = (str(raw_param.get("name", "")), str(raw_param.get("in", "query")))
            merged[key] = raw_param

    return list(merged.values())


def _parameter_to_param_def(parameter: dict[str, Any], enum_style: str = "literal") -> ParamDef:
    """Convert an OpenAPI parameter object into ParamDef."""

    name = str(parameter.get("name", "param"))
    location_raw = str(parameter.get("in", "query")).lower()
    schema = parameter.get("schema") if isinstance(parameter.get("schema"), dict) else {}

    location_map = {
        "path": ParamLocation.PATH,
        "query": ParamLocation.QUERY,
        "header": ParamLocation.HEADER,
        "cookie": ParamLocation.COOKIE,
    }
    location = location_map.get(location_raw, ParamLocation.QUERY)

    required = bool(parameter.get("required", False)) or location == ParamLocation.PATH

    python_type = openapi_type_to_python(schema, enum_style=enum_style)
    if not required and "| None" not in python_type:
        python_type = f"{python_type} | None"

    enum_raw = schema.get("enum")
    enum_values = [str(value) for value in enum_raw] if isinstance(enum_raw, list) else None

    return ParamDef(
        name=name,
        python_name=sanitize_identifier(to_snake_case(name)),
        python_type=python_type,
        location=location,
        required=required,
        description=str(parameter.get("description", "")),
        default=schema.get("default"),
        enum_values=enum_values,
        constraints=_extract_constraints(schema),
    )


def _extract_constraints(schema: dict[str, Any]) -> dict[str, Any]:
    """Extract Field-compatible constraints from schema definitions."""

    constraint_keys = {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "pattern",
        "minItems",
        "maxItems",
        "uniqueItems",
    }

    constraints: dict[str, Any] = {}
    for key in constraint_keys:
        if key in schema:
            constraints[key] = schema[key]

    return constraints


def _detect_pagination_pattern(params: list[ParamDef], operation: dict[str, Any]) -> str | None:
    """Detect common pagination patterns from query params and response shapes."""

    query_names = {param.name.lower() for param in params if param.location == ParamLocation.QUERY}

    if {"limit", "offset"}.issubset(query_names):
        return "offset_limit"
    if {"page", "per_page"}.issubset(query_names):
        return "page_per_page"
    if "cursor" in query_names or "next_cursor" in query_names:
        return "cursor"

    responses = operation.get("responses", {}) if isinstance(operation.get("responses", {}), dict) else {}
    for response_obj in responses.values():
        if not isinstance(response_obj, dict):
            continue

        headers = response_obj.get("headers", {}) if isinstance(response_obj.get("headers", {}), dict) else {}
        header_names = {str(name).lower() for name in headers.keys()}
        if "link" in header_names:
            return "link_header"
        if "x-next-page" in header_names:
            return "page_header"
        if "x-next-cursor" in header_names:
            return "cursor_header"

        content = response_obj.get("content", {}) if isinstance(response_obj.get("content", {}), dict) else {}
        schema, _ = _pick_response_schema(content)
        if not schema:
            continue

        properties = schema.get("properties", {}) if isinstance(schema.get("properties", {}), dict) else {}
        response_property_names = {str(name).lower() for name in properties.keys()}
        if {"items", "next_cursor"}.issubset(response_property_names):
            return "cursor_body"
        if {"items", "next_page"}.issubset(response_property_names):
            return "page_body"
        if "has_more" in response_property_names and "items" in response_property_names:
            return "cursor_body"

    return None


def _extract_request_body_params(
    operation: dict[str, Any],
    enum_style: str = "literal",
    body_style: str = "auto",
) -> tuple[str | None, list[ParamDef], str | None]:
    """Extract request body parameters, type, and media type.

    Returns:
        Tuple of ``(python_type, params, content_type)``.
    """

    request_body = operation.get("requestBody")
    if not isinstance(request_body, dict):
        return None, [], None

    content = request_body.get("content", {}) if isinstance(request_body.get("content", {}), dict) else {}
    schema, content_type = _pick_request_body_schema(content, body_style=body_style)
    if not schema:
        return None, [], None

    required = bool(request_body.get("required", False))
    body_type = openapi_type_to_python(schema, enum_style=enum_style)

    params: list[ParamDef] = []
    if isinstance(schema.get("properties"), dict):
        required_fields = schema.get("required", []) if isinstance(schema.get("required", []), list) else []
        params = schema_to_params(schema, required_fields=required_fields, enum_style=enum_style)
        for param in params:
            param.location = ParamLocation.BODY
            if not required:
                param.required = False
            if not param.required and "| None" not in param.python_type:
                param.python_type = f"{param.python_type} | None"
    else:
        param_type = body_type if required or "| None" in body_type else f"{body_type} | None"
        params = [
            ParamDef(
                name="body",
                python_name="body",
                python_type=param_type,
                location=ParamLocation.BODY,
                required=required,
                description="Request body",
                default=None,
            )
        ]

    return body_type, params, content_type


def _pick_request_body_schema(
    content: dict[str, Any],
    body_style: str = "auto",
) -> tuple[dict[str, Any] | None, str | None]:
    """Pick request body schema with priority for JSON/form encodings."""

    style_priority_map = {
        "auto": (
            "application/json",
            "multipart/form-data",
            "application/x-www-form-urlencoded",
        ),
        "json": ("application/json",),
        "form": ("application/x-www-form-urlencoded",),
        "multipart": ("multipart/form-data",),
    }

    preferred_content_types = style_priority_map.get(body_style, style_priority_map["auto"])

    for content_type in preferred_content_types:
        media_obj = content.get(content_type)
        if isinstance(media_obj, dict) and isinstance(media_obj.get("schema"), dict):
            return media_obj["schema"], content_type

    for content_type, media_obj in content.items():
        if isinstance(media_obj, dict) and isinstance(media_obj.get("schema"), dict):
            return media_obj["schema"], str(content_type)

    return None, None


def _pick_response_schema(content: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Pick response schema and content type with JSON-first priority."""

    preferred_content_types = (
        "application/json",
        "text/plain",
        "application/octet-stream",
    )

    for content_type in preferred_content_types:
        media_obj = content.get(content_type)
        if isinstance(media_obj, dict) and isinstance(media_obj.get("schema"), dict):
            return media_obj["schema"], content_type

    for content_type, media_obj in content.items():
        if isinstance(media_obj, dict) and isinstance(media_obj.get("schema"), dict):
            return media_obj["schema"], str(content_type)

    return None, None


def _extract_response_info(
    operation: dict[str, Any],
    schemas: dict[str, Any],
    enum_style: str = "literal",
) -> tuple[str, str | None, bool]:
    """Extract response annotation, content type, and structured-output hint."""

    responses = operation.get("responses", {}) if isinstance(operation.get("responses", {}), dict) else {}
    if not responses:
        return "Any", None, False

    response_candidates: list[tuple[str, dict[str, Any]]] = [
        (str(code), value) for code, value in responses.items() if isinstance(value, dict)
    ]

    preferred = next((item for item in response_candidates if item[0] in {"200", "201", "202"}), None)
    if preferred is None:
        preferred = next((item for item in response_candidates if item[0].startswith("2")), None)
    selected = preferred or (response_candidates[0] if response_candidates else None)
    if not selected:
        return "Any", None, False

    _, response_obj = selected
    content = response_obj.get("content", {}) if isinstance(response_obj.get("content", {}), dict) else {}
    schema, content_type = _pick_response_schema(content)

    if not schema:
        return "Any", None, False

    annotation = _map_response_schema_to_annotation(schema, schemas, enum_style=enum_style)

    is_json = bool(content_type and "json" in content_type.lower())
    structured = is_json and annotation not in {"str", "bytes", "Any"}

    return annotation, content_type, structured


def _map_response_schema_to_annotation(
    schema: dict[str, Any],
    schemas: dict[str, Any],
    enum_style: str = "literal",
) -> str:
    """Map response schema to model-aware annotation when possible."""

    model_name = _match_schema_to_model_name(schema, schemas)
    if model_name:
        return model_name

    schema_type = schema.get("type")
    if schema_type == "array":
        items = schema.get("items") if isinstance(schema.get("items"), dict) else None
        if items is not None:
            item_model_name = _match_schema_to_model_name(items, schemas)
            if item_model_name:
                return f"list[{item_model_name}]"

    return map_schema_to_typeref(schema, enum_style=enum_style).annotation


def _match_schema_to_model_name(schema: dict[str, Any], schemas: dict[str, Any]) -> str | None:
    """Return model class name when schema matches a known component schema."""

    ref = schema.get("$ref")
    if isinstance(ref, str) and "/" in ref:
        return to_pascal_case(ref.rsplit("/", 1)[-1])

    for schema_name, candidate in schemas.items():
        if isinstance(candidate, dict) and candidate == schema:
            return to_pascal_case(str(schema_name))

    return None


def _collect_models(schemas: dict[str, Any], enum_style: str = "literal") -> list[ModelDefinition]:
    """Collect schema models into IR model definitions."""

    models: list[ModelDefinition] = []

    for schema_name in sorted(schemas.keys(), key=lambda item: str(item)):
        schema = schemas[schema_name]
        if not isinstance(schema, dict):
            continue

        normalized_schema = _normalize_model_schema(schema)
        required_fields = (
            normalized_schema.get("required", []) if isinstance(normalized_schema.get("required", []), list) else []
        )
        parent_key = _extract_parent_schema_key_from_all_of(schema, schemas, current_schema_key=schema_name)
        parent_name = to_pascal_case(parent_key) if parent_key else None

        fields = schema_to_params(normalized_schema, required_fields=required_fields, enum_style=enum_style)
        if parent_key and isinstance(schemas.get(parent_key), dict):
            parent_schema = _normalize_model_schema(schemas[parent_key])
            parent_properties = (
                parent_schema.get("properties", {}) if isinstance(parent_schema.get("properties", {}), dict) else {}
            )
            parent_property_names = set(parent_properties.keys())
            fields = [field for field in fields if field.name not in parent_property_names]

        for field in fields:
            if not field.required and "| None" not in field.python_type:
                field.python_type = f"{field.python_type} | None"

        schema_type = normalized_schema.get("type")
        root_type: str | None = None

        raw_one_of = schema.get("oneOf") if isinstance(schema.get("oneOf"), list) else []
        if raw_one_of:
            variant_annotations = _extract_composed_variant_annotations(raw_one_of, schemas, enum_style=enum_style)
            if variant_annotations:
                root_type = " | ".join(variant_annotations)

        if root_type is None:
            if isinstance(schema_type, str) and schema_type != "object":
                root_type = openapi_type_to_python(normalized_schema, enum_style=enum_style)
            elif schema_type == "object" and not fields:
                root_type = "dict[str, Any]"

        additional_properties_raw: Any = normalized_schema.get("additionalProperties")
        additional_properties: bool | None
        if isinstance(additional_properties_raw, bool):
            additional_properties = additional_properties_raw
        elif isinstance(additional_properties_raw, dict):
            additional_properties = True
        else:
            additional_properties = None

        discriminator = schema.get("discriminator") if isinstance(schema.get("discriminator"), dict) else {}
        discriminator_field = (
            str(discriminator.get("propertyName")) if isinstance(discriminator.get("propertyName"), str) else None
        )

        models.append(
            ModelDefinition(
                name=to_pascal_case(str(schema_name)) or "Model",
                fields=fields,
                description=str(schema.get("description", "")),
                parent=parent_name,
                root_type=root_type,
                additional_properties=additional_properties,
                discriminator_field=discriminator_field,
            )
        )

    return _order_models_by_parent(models)


def _normalize_model_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Flatten useful parts of allOf schemas for MVP model generation."""

    all_of = schema.get("allOf")
    if not isinstance(all_of, list) or not all_of:
        return schema

    merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}

    for part in all_of:
        if not isinstance(part, dict):
            continue

        properties = part.get("properties")
        if isinstance(properties, dict):
            merged["properties"].update(properties)

        required_fields = part.get("required")
        if isinstance(required_fields, list):
            for field_name in required_fields:
                if field_name not in merged["required"]:
                    merged["required"].append(field_name)

        if "additionalProperties" in part:
            merged["additionalProperties"] = part["additionalProperties"]

    own_properties = schema.get("properties")
    if isinstance(own_properties, dict):
        merged["properties"].update(own_properties)

    own_required = schema.get("required")
    if isinstance(own_required, list):
        for field_name in own_required:
            if field_name not in merged["required"]:
                merged["required"].append(field_name)

    if "additionalProperties" in schema:
        merged["additionalProperties"] = schema["additionalProperties"]

    if merged["properties"] or merged["required"] or "additionalProperties" in merged:
        return merged

    return schema


def _extract_composed_variant_annotations(
    variants: list[Any],
    all_schemas: dict[str, Any],
    enum_style: str = "literal",
) -> list[str]:
    """Extract deterministic variant annotations from oneOf/anyOf schemas."""

    annotations: list[str] = []

    for variant in variants:
        if not isinstance(variant, dict):
            continue

        model_name = _match_schema_to_model_name(variant, all_schemas)
        annotation = model_name or openapi_type_to_python(variant, enum_style=enum_style)

        if annotation not in annotations:
            annotations.append(annotation)

    return annotations


def _extract_parent_schema_key_from_all_of(
    schema: dict[str, Any],
    all_schemas: dict[str, Any],
    current_schema_key: str,
) -> str | None:
    """Extract parent schema key from allOf, supporting resolved refs."""

    all_of = schema.get("allOf")
    if not isinstance(all_of, list):
        return None

    for part in all_of:
        if not isinstance(part, dict):
            continue

        ref = part.get("$ref")
        if isinstance(ref, str) and "/" in ref:
            return ref.rsplit("/", 1)[-1]

        title = part.get("title")
        if isinstance(title, str):
            candidate_from_title = _find_schema_key_by_class_name(all_schemas, to_pascal_case(title))
            if candidate_from_title:
                return candidate_from_title

        matched_key = _match_schema_key_by_content(
            all_schemas,
            candidate_schema=part,
            current_schema_key=current_schema_key,
        )
        if matched_key:
            return matched_key

    return None


def _find_schema_key_by_class_name(all_schemas: dict[str, Any], class_name: str) -> str | None:
    """Find original schema key from normalized class name."""

    for key in all_schemas:
        if to_pascal_case(str(key)) == class_name:
            return str(key)
    return None


def _match_schema_key_by_content(
    all_schemas: dict[str, Any],
    candidate_schema: dict[str, Any],
    current_schema_key: str,
) -> str | None:
    """Best-effort parent match by schema content when refs are resolved."""

    for key, schema_obj in all_schemas.items():
        if str(key) == current_schema_key:
            continue
        if not isinstance(schema_obj, dict):
            continue
        if schema_obj == candidate_schema:
            return str(key)

    return None


def _http_method_sort_key(method: str) -> tuple[int, str]:
    """Return deterministic sort key for HTTP methods."""

    lowered = method.lower()
    return (HTTP_METHOD_SORT_ORDER.get(lowered, len(HTTP_METHOD_SORT_ORDER)), lowered)


def _order_models_by_parent(models: list[ModelDefinition]) -> list[ModelDefinition]:
    """Order models so parent classes are emitted before child classes."""

    ordered: list[ModelDefinition] = []
    pending = list(models)
    declared_names: set[str] = set()

    while pending:
        progressed = False
        remaining: list[ModelDefinition] = []

        pending_names = {model.name for model in pending}
        for model in pending:
            parent = model.parent
            parent_declared = parent is None or parent in declared_names or parent not in pending_names
            if parent_declared:
                ordered.append(model)
                declared_names.add(model.name)
                progressed = True
            else:
                remaining.append(model)

        if not progressed:
            ordered.extend(remaining)
            break

        pending = remaining

    return ordered


def _apply_tool_limits(
    analyzed_tools: list[tuple[int, ToolDefinition]], config: AnalyzerConfig
) -> list[ToolDefinition]:
    """Apply max_tools filtering while prioritizing GET operations."""

    tools_in_source_order = [tool for _, tool in analyzed_tools]
    ranked_tools = _rank_tools_for_selection(
        tools_in_source_order,
        config.prefer_tags or config.include_tags or config.filter_tags,
    )

    if len(ranked_tools) <= config.max_tools:
        for tool in ranked_tools:
            tool.selection_reason = "Included: within tool limit."
        return ranked_tools

    selected = ranked_tools[: config.max_tools]
    for tool in selected:
        if tool.http_method.upper() == "GET":
            tool.selection_reason = "Included: GET endpoint prioritized by selection heuristic."
        else:
            tool.selection_reason = "Included: ranked within max-tools limit."

    return selected


def _rank_tools_for_selection(tools: list[ToolDefinition], filter_tags: list[str] | None) -> list[ToolDefinition]:
    """Rank tools deterministically for max-tools selection."""

    tag_priority = {tag: idx for idx, tag in enumerate(filter_tags)} if filter_tags else {}

    indexed_tools = list(enumerate(tools))

    def _rank(item: tuple[int, ToolDefinition]) -> tuple[int, int, int, str]:
        index, tool = item
        get_priority = 0 if tool.http_method.upper() == "GET" else 1
        if tag_priority:
            matching = [tag_priority[tag] for tag in tool.tags if tag in tag_priority]
            tag_rank = min(matching) if matching else len(tag_priority)
        else:
            tag_rank = 0
        return (get_priority, tag_rank, index, tool.name)

    ranked = sorted(indexed_tools, key=_rank)
    return [tool for _, tool in ranked]


def _dedupe_python_names(params: list[ParamDef]) -> list[ParamDef]:
    """Ensure all tool parameter Python names are unique."""

    used: set[str] = set()
    for param in params:
        base_name = param.python_name or "param"
        if base_name not in used:
            used.add(base_name)
            continue

        index = 2
        while True:
            candidate = f"{base_name}_{index}"
            if candidate not in used:
                param.python_name = candidate
                used.add(candidate)
                break
            index += 1

    return params
