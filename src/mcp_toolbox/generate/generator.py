from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import jinja2

from mcp_toolbox.analyze import AuthType, ModelDefinition, ParamDef, ServerIR
from mcp_toolbox.utils import to_pascal_case, to_snake_case, truncate_description


class MCPGenerator:
    """Render Jinja2 templates from ServerIR into a complete MCP server project."""

    def __init__(self, template_dir: Path | None = None) -> None:
        """Initialize template environment and custom filters.

        Args:
            template_dir: Optional directory containing override templates. Any
                matching template name in this directory takes precedence over
                packaged defaults.
        """

        loaders: list[jinja2.BaseLoader] = []
        if template_dir is not None:
            loaders.append(jinja2.FileSystemLoader(str(template_dir)))
        loaders.append(jinja2.PackageLoader("mcp_toolbox", "generate/templates"))

        self.env = jinja2.Environment(
            loader=jinja2.ChoiceLoader(loaders),
            trim_blocks=False,
            lstrip_blocks=False,
            keep_trailing_newline=True,
            autoescape=False,
        )
        self.env.filters["snake_case"] = to_snake_case
        self.env.filters["pascal_case"] = to_pascal_case
        self.env.filters["truncate"] = truncate_description
        self.env.filters["pyrepr"] = _pyrepr

    def generate(self, ir: ServerIR, output_dir: Path, default_transport: str = "stdio") -> list[Path]:
        """Generate a standalone MCP server project from intermediate representation.

        Args:
            ir: Intermediate representation created by analysis stage.
            output_dir: Root directory where generated files will be written.
            default_transport: Generated server default transport.

        Returns:
            List of file paths created during generation.
        """

        output_dir.mkdir(parents=True, exist_ok=True)

        package_name = f"{ir.server_name.replace('-', '_')}_mcp_server"
        package_dir = output_dir / "src" / package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        server_annotation_strings = _collect_tool_annotation_strings(ir)
        model_annotation_strings = _collect_model_annotation_strings(ir)

        import_context = _collect_import_context(server_annotation_strings)
        model_import_context = _collect_import_context(model_annotation_strings)
        rendered_models, model_requires_field, model_needs_annotated = _build_model_render_context(ir.models)

        response_model_imports = _collect_response_model_imports(ir)

        context = {
            "server_name": ir.server_name,
            "server_title": ir.server_title,
            "server_description": ir.server_description,
            "base_url": ir.base_url,
            "tools": ir.tools,
            "tool_modules": [tool.name for tool in ir.tools],
            "auth": ir.auth,
            "models": ir.models,
            "rendered_models": rendered_models,
            "dependencies": ir.dependencies,
            "package_name": package_name,
            "default_transport": default_transport,
            "needs_type_adapter": any(tool.structured_output for tool in ir.tools),
            "response_model_imports": response_model_imports,
            **import_context,
            "model_typing_imports": model_import_context["typing_imports"],
            "model_datetime_imports": model_import_context["datetime_imports"],
            "model_uuid_imports": model_import_context["uuid_imports"],
            "model_ipaddress_imports": model_import_context["ipaddress_imports"],
            "model_pydantic_type_imports": model_import_context["pydantic_imports"],
            "model_requires_base_model": any(not model.root_type for model in ir.models),
            "model_requires_root_model": any(bool(model.root_type) for model in ir.models),
            "model_requires_config_dict": any(not model.root_type for model in ir.models),
            "model_requires_field": model_requires_field,
            "model_needs_annotated": model_needs_annotated,
        }

        created_files: list[Path] = []

        render_plan: list[tuple[str, Path]] = [
            ("pyproject.toml.jinja2", output_dir / "pyproject.toml"),
            ("readme.md.jinja2", output_dir / "README.md"),
            ("env_example.jinja2", output_dir / ".env.example"),
            ("init.py.jinja2", package_dir / "__init__.py"),
            ("server.py.jinja2", package_dir / "server.py"),
            ("client.py.jinja2", package_dir / "client.py"),
            ("models.py.jinja2", package_dir / "models.py"),
            ("errors.py.jinja2", package_dir / "errors.py"),
            ("tool.py.jinja2", package_dir / "tool.py"),
            ("conftest.py.jinja2", output_dir / "tests" / "conftest.py"),
        ]

        if ir.auth.auth_type != AuthType.NONE:
            render_plan.append(("auth.py.jinja2", package_dir / "auth.py"))

        for template_name, destination in render_plan:
            rendered = self._render_template(template_name, context)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(rendered, encoding="utf-8")
            created_files.append(destination)

        tools_dir = package_dir / "tools"
        tools_dir.mkdir(parents=True, exist_ok=True)

        tools_init = self._render_template("tools_init.py.jinja2", context)
        tools_init_path = tools_dir / "__init__.py"
        tools_init_path.write_text(tools_init, encoding="utf-8")
        created_files.append(tools_init_path)

        model_names = {model.name for model in ir.models}
        for tool in ir.tools:
            tool_context = {
                **context,
                "tool": tool,
                "tool_response_model_imports": _collect_model_names_for_annotation(tool.response_type, model_names),
            }
            module_path = tools_dir / f"{tool.name}.py"
            rendered_module = self._render_template("tool_module.py.jinja2", tool_context)
            module_path.write_text(rendered_module, encoding="utf-8")
            created_files.append(module_path)

        return created_files

    def _render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a Jinja2 template to text."""

        template = self.env.get_template(template_name)
        return template.render(**context)


def _pyrepr(value: Any) -> str:
    """Render Python source literal representation used in templates."""

    if value is None:
        return "None"
    return repr(value)


def _collect_tool_annotation_strings(ir: ServerIR) -> list[str]:
    """Collect all annotation strings referenced by generated tool signatures."""

    annotations: list[str] = []
    for tool in ir.tools:
        annotations.extend(param.python_type for param in tool.params)
        annotations.append(tool.response_type)

    return annotations


def _collect_model_annotation_strings(ir: ServerIR) -> list[str]:
    """Collect type annotation strings used by generated Pydantic models."""

    annotations: list[str] = []
    for model in ir.models:
        if model.root_type:
            annotations.append(model.root_type)
        annotations.extend(field.python_type for field in model.fields)

    return annotations


def _collect_response_model_imports(ir: ServerIR) -> list[str]:
    """Collect model class names referenced by response annotations."""

    model_names = {model.name for model in ir.models}
    used: set[str] = set()

    for tool in ir.tools:
        used.update(_collect_model_names_for_annotation(tool.response_type, model_names))

    return sorted(used)


def _collect_model_names_for_annotation(annotation: str, model_names: set[str]) -> list[str]:
    """Collect referenced model names from one type annotation string."""

    used: list[str] = []
    for model_name in sorted(model_names):
        if _has_symbol(annotation, model_name):
            used.append(model_name)
    return used


def _build_model_render_context(models: list[ModelDefinition]) -> tuple[list[dict[str, Any]], bool, bool]:
    """Build simplified model rendering payload for templates."""

    rendered_models: list[dict[str, Any]] = []
    requires_field = False
    needs_annotated = False

    for model in models:
        field_lines: list[str] = []
        for field in model.fields:
            line, field_required, field_needs_annotated = _render_model_field_line(field)
            if field_required:
                requires_field = True
            if field_needs_annotated:
                needs_annotated = True
            field_lines.append(line)

        rendered_models.append(
            {
                "name": model.name,
                "description": model.description,
                "parent": model.parent,
                "root_type": model.root_type,
                "additional_properties": model.additional_properties,
                "discriminator_field": model.discriminator_field,
                "field_lines": field_lines,
            }
        )

    return rendered_models, requires_field, needs_annotated


def _render_model_field_line(field: ParamDef) -> tuple[str, bool, bool]:
    """Render one Pydantic model field declaration line.

    Returns:
        (rendered_line, requires_field_import, needs_annotated_import)
    """

    has_alias = field.name != field.python_name
    has_constraints = bool(field.constraints)
    has_description = bool(field.description)

    if has_constraints:
        metadata_args: list[str] = []
        if has_alias:
            metadata_args.append(f"alias={_pyrepr(field.name)}")
        if has_description:
            metadata_args.append(f"description={_pyrepr(field.description)}")
        metadata_args.extend(_constraint_field_args(field.constraints))

        metadata_expr = f"Field({', '.join(metadata_args)})" if metadata_args else "Field()"
        annotated = f"Annotated[{field.python_type}, {metadata_expr}]"

        if field.required and field.default is None:
            return f"{field.python_name}: {annotated}", True, True

        if field.default is not None:
            default_expr = _pyrepr(field.default)
        else:
            default_expr = "None"

        return f"{field.python_name}: {annotated} = {default_expr}", True, True

    has_meta = has_alias or has_description or field.default is not None

    if field.required and not has_meta:
        return f"{field.python_name}: {field.python_type}", False, False

    if not field.required and not has_meta:
        return f"{field.python_name}: {field.python_type} = None", False, False

    if field.required and field.default is None:
        default_expr = "..."
    elif field.default is None:
        default_expr = "None"
    else:
        default_expr = _pyrepr(field.default)

    field_kwargs: list[str] = [default_expr]
    if has_alias:
        field_kwargs.append(f"alias={_pyrepr(field.name)}")
    if has_description:
        field_kwargs.append(f"description={_pyrepr(field.description)}")

    joined = ", ".join(field_kwargs)
    return f"{field.python_name}: {field.python_type} = Field({joined})", True, False


def _constraint_field_args(constraints: dict[str, Any]) -> list[str]:
    """Convert OpenAPI constraint keys to Pydantic Field arguments."""

    mapping = {
        "minimum": "ge",
        "maximum": "le",
        "exclusiveMinimum": "gt",
        "exclusiveMaximum": "lt",
        "multipleOf": "multiple_of",
        "minLength": "min_length",
        "maxLength": "max_length",
        "pattern": "pattern",
        "minItems": "min_length",
        "maxItems": "max_length",
    }

    args: list[str] = []
    for key in sorted(constraints.keys()):
        if key == "uniqueItems":
            if constraints[key]:
                args.append("json_schema_extra={'uniqueItems': True}")
            continue

        field_arg = mapping.get(key)
        if field_arg is None:
            continue
        args.append(f"{field_arg}={_pyrepr(constraints[key])}")

    return args


def _collect_import_context(annotation_strings: list[str]) -> dict[str, list[str]]:
    """Build template import context from detected annotation symbols."""

    typing_imports: set[str] = set()
    datetime_imports: set[str] = set()
    uuid_imports: set[str] = set()
    ipaddress_imports: set[str] = set()
    pydantic_imports: set[str] = set()

    for annotation in annotation_strings:
        if _has_symbol(annotation, "Any"):
            typing_imports.add("Any")
        if "Literal[" in annotation:
            typing_imports.add("Literal")

        if _has_symbol(annotation, "datetime"):
            datetime_imports.add("datetime")
        if _has_symbol(annotation, "date"):
            datetime_imports.add("date")
        if _has_symbol(annotation, "time"):
            datetime_imports.add("time")

        if _has_symbol(annotation, "UUID"):
            uuid_imports.add("UUID")

        if _has_symbol(annotation, "IPv4Address"):
            ipaddress_imports.add("IPv4Address")
        if _has_symbol(annotation, "IPv6Address"):
            ipaddress_imports.add("IPv6Address")

        if _has_symbol(annotation, "EmailStr"):
            pydantic_imports.add("EmailStr")
        if _has_symbol(annotation, "AnyUrl"):
            pydantic_imports.add("AnyUrl")
        if _has_symbol(annotation, "SecretStr"):
            pydantic_imports.add("SecretStr")

    return {
        "typing_imports": sorted(typing_imports),
        "datetime_imports": sorted(datetime_imports),
        "uuid_imports": sorted(uuid_imports),
        "ipaddress_imports": sorted(ipaddress_imports),
        "pydantic_imports": sorted(pydantic_imports),
    }


def _has_symbol(annotation: str, symbol: str) -> bool:
    """Return True when a type annotation contains a standalone symbol."""

    return bool(re.search(rf"\b{re.escape(symbol)}\b", annotation))
