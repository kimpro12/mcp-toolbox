from __future__ import annotations

from pathlib import Path

from mcp_toolbox.analyze import AnalyzerConfig, ServerIR, analyze_spec
from mcp_toolbox.generate import MCPGenerator
from mcp_toolbox.parse import parse_spec


def test_generator_creates_expected_files(analyzed_petstore: ServerIR, tmp_path: Path) -> None:
    """Generator should render core project files from IR."""

    generator = MCPGenerator()
    output_dir = tmp_path / "petstore_output"
    files = generator.generate(analyzed_petstore, output_dir)

    package_dir = output_dir / "src" / f"{analyzed_petstore.server_name}_mcp_server"

    expected = {
        output_dir / "pyproject.toml",
        output_dir / "README.md",
        output_dir / ".env.example",
        package_dir / "__init__.py",
        package_dir / "server.py",
        package_dir / "auth.py",
        package_dir / "tools" / "__init__.py",
        package_dir / "tools" / "list_pets.py",
        output_dir / "tests" / "conftest.py",
    }

    assert expected.issubset(set(files))
    for filepath in expected:
        assert filepath.exists()


def test_generator_output_python_compiles(analyzed_petstore: ServerIR, tmp_path: Path) -> None:
    """Generated Python modules should compile successfully."""

    generator = MCPGenerator()
    output_dir = tmp_path / "compiled_output"
    generator.generate(analyzed_petstore, output_dir)

    package_dir = output_dir / "src" / f"{analyzed_petstore.server_name}_mcp_server"
    for py_file in package_dir.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        compile(source, str(py_file), "exec")


def test_generator_skips_auth_file_when_no_auth(tmp_path: Path) -> None:
    """Generator omits auth.py when the API has no security scheme."""

    spec = tmp_path / "no-auth.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: No Auth API
  version: "1.0"
paths:
  /status:
    get:
      operationId: getStatus
      responses:
        "200":
          description: ok
""".strip(),
        encoding="utf-8",
    )

    ir = analyze_spec(parse_spec(spec), AnalyzerConfig(max_tools=10))
    generator = MCPGenerator()
    output_dir = tmp_path / "no_auth_output"
    generator.generate(ir, output_dir)

    package_dir = output_dir / "src" / f"{ir.server_name}_mcp_server"
    assert not (package_dir / "auth.py").exists()


def test_generator_includes_header_params_in_request(tmp_path: Path) -> None:
    """Header parameters should be forwarded in request kwargs."""

    spec = tmp_path / "header.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: Header API
  version: "1.0"
paths:
  /secure:
    get:
      operationId: getSecure
      parameters:
        - name: X-Custom
          in: header
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
    output_dir = tmp_path / "header_output"
    MCPGenerator().generate(ir, output_dir)

    package_dir = output_dir / "src" / f"{ir.server_name}_mcp_server"
    tool_source = (package_dir / "tools" / "get_secure.py").read_text(encoding="utf-8")

    assert 'headers["X-Custom"] = str(x_custom)' in tool_source
    assert 'request_kwargs["headers"] = headers' in tool_source


def test_generator_includes_cookie_params_in_request(tmp_path: Path) -> None:
    """Cookie parameters should be forwarded via request_kwargs['cookies']."""

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
    output_dir = tmp_path / "cookie_param_output"
    MCPGenerator().generate(ir, output_dir)

    package_dir = output_dir / "src" / f"{ir.server_name}_mcp_server"
    tool_source = (package_dir / "tools" / "get_session.py").read_text(encoding="utf-8")

    assert 'cookies["session_id"] = str(session_id)' in tool_source
    assert 'request_kwargs["cookies"] = cookies' in tool_source


def test_generator_oauth2_wires_access_token_auth(tmp_path: Path) -> None:
    """OAuth2 specs should wire a bearer token auth handler from env vars."""

    spec = tmp_path / "oauth.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: OAuth API
  version: "1.0"
security:
  - OAuth2: []
components:
  securitySchemes:
    OAuth2:
      type: oauth2
      flows:
        clientCredentials:
          tokenUrl: https://example.com/token
          scopes:
            read: Read scope
paths:
  /me:
    get:
      operationId: getMe
      responses:
        "200":
          description: ok
""".strip(),
        encoding="utf-8",
    )

    ir = analyze_spec(parse_spec(spec), AnalyzerConfig(max_tools=10))
    output_dir = tmp_path / "oauth_output"
    MCPGenerator().generate(ir, output_dir)

    prefix = ir.server_name.upper()
    package_dir = output_dir / "src" / f"{ir.server_name}_mcp_server"
    server_source = (package_dir / "server.py").read_text(encoding="utf-8")
    auth_source = (package_dir / "auth.py").read_text(encoding="utf-8")
    env_source = (output_dir / ".env.example").read_text(encoding="utf-8")

    assert f'token = os.environ.get("{prefix}_ACCESS_TOKEN", "")' in server_source
    assert "auth_handler = BearerTokenAuth(token) if token else None" in server_source
    assert "class BearerTokenAuth(httpx.Auth):" in auth_source
    assert "class OAuth2ClientCredentialsConfig:" in auth_source
    assert f"{prefix}_ACCESS_TOKEN=your-access-token" in env_source
    assert f"{prefix}_CLIENT_ID=your-client-id" in env_source
    assert f"{prefix}_CLIENT_SECRET=your-client-secret" in env_source
    assert f"{prefix}_TOKEN_URL=https://example.com/token" in env_source


def test_generator_cookie_api_key_auth_uses_cookie_handler(tmp_path: Path) -> None:
    """apiKey cookie auth should use APIKeyCookieAuth scaffold."""

    spec = tmp_path / "cookie-auth.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: Cookie Auth API
  version: "1.0"
security:
  - CookieKey: []
components:
  securitySchemes:
    CookieKey:
      type: apiKey
      in: cookie
      name: session
paths:
  /me:
    get:
      operationId: getMe
      responses:
        "200":
          description: ok
""".strip(),
        encoding="utf-8",
    )

    ir = analyze_spec(parse_spec(spec), AnalyzerConfig(max_tools=10))
    output_dir = tmp_path / "cookie_auth_output"
    MCPGenerator().generate(ir, output_dir)

    package_dir = output_dir / "src" / f"{ir.server_name}_mcp_server"
    server_source = (package_dir / "server.py").read_text(encoding="utf-8")
    auth_source = (package_dir / "auth.py").read_text(encoding="utf-8")

    assert "from .auth import APIKeyCookieAuth" in server_source
    assert 'auth_handler = APIKeyCookieAuth("session", api_key) if api_key else None' in server_source
    assert "class APIKeyCookieAuth(httpx.Auth):" in auth_source


def test_generator_basic_readme_matches_runtime_env_vars(tmp_path: Path) -> None:
    """Basic auth docs should match runtime username/password variables."""

    spec = tmp_path / "basic.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: Basic API
  version: "1.0"
security:
  - BasicAuth: []
components:
  securitySchemes:
    BasicAuth:
      type: http
      scheme: basic
paths:
  /data:
    get:
      operationId: getData
      responses:
        "200":
          description: ok
""".strip(),
        encoding="utf-8",
    )

    ir = analyze_spec(parse_spec(spec), AnalyzerConfig(max_tools=10))
    output_dir = tmp_path / "basic_output"
    MCPGenerator().generate(ir, output_dir)

    prefix = ir.server_name.upper()
    package_dir = output_dir / "src" / f"{ir.server_name}_mcp_server"
    server_source = (package_dir / "server.py").read_text(encoding="utf-8")
    readme_source = (output_dir / "README.md").read_text(encoding="utf-8")

    assert f"{prefix}_USERNAME" in server_source
    assert f"{prefix}_PASSWORD" in server_source
    assert f"{prefix}_USERNAME" in readme_source
    assert f"{prefix}_PASSWORD" in readme_source
    assert f"{prefix}_BASIC_AUTH" not in readme_source


def test_generator_emits_retry_backoff_client_settings(analyzed_petstore: ServerIR, tmp_path: Path) -> None:
    """Generated client/server should include retry and timeout configuration hooks."""

    output_dir = tmp_path / "retry_output"
    MCPGenerator().generate(analyzed_petstore, output_dir)

    package_dir = output_dir / "src" / f"{analyzed_petstore.server_name}_mcp_server"
    client_source = (package_dir / "client.py").read_text(encoding="utf-8")
    tool_source = (package_dir / "tools" / "list_pets.py").read_text(encoding="utf-8")
    env_source = (output_dir / ".env.example").read_text(encoding="utf-8")

    assert "class ClientSettings:" in client_source
    assert "async def request_with_retry(" in client_source
    assert "max_retries=ctx.max_retries" in tool_source
    assert "backoff_seconds=ctx.backoff_seconds" in tool_source
    assert "allow_unsafe_retries=ctx.retry_unsafe_methods" in tool_source
    assert "PETSTORE_API_RETRY_MAX_ATTEMPTS=2" in env_source
    assert "PETSTORE_API_RETRY_BACKOFF_SECONDS=0.5" in env_source
    assert "PETSTORE_API_RETRY_UNSAFE_METHODS=false" in env_source


def test_generator_emits_pagination_hints_for_detected_tools(analyzed_petstore: ServerIR, tmp_path: Path) -> None:
    """Generated server should emit pagination hints for paginated operations."""

    output_dir = tmp_path / "pagination_output"
    MCPGenerator().generate(analyzed_petstore, output_dir)

    package_dir = output_dir / "src" / f"{analyzed_petstore.server_name}_mcp_server"
    server_source = (package_dir / "server.py").read_text(encoding="utf-8")
    readme_source = (output_dir / "README.md").read_text(encoding="utf-8")

    assert "PAGINATION_HINTS" in server_source
    assert '"list_pets": "offset_limit"' in server_source
    assert "def get_pagination_hints()" in server_source
    assert "## Pagination Hints" in readme_source


def test_generator_applies_default_transport_setting(analyzed_petstore: ServerIR, tmp_path: Path) -> None:
    """Generated server should default to requested transport."""

    output_dir = tmp_path / "transport_output"
    MCPGenerator().generate(analyzed_petstore, output_dir, default_transport="sse")

    package_dir = output_dir / "src" / f"{analyzed_petstore.server_name}_mcp_server"
    server_source = (package_dir / "server.py").read_text(encoding="utf-8")

    assert 'transport = "sse"' in server_source


def test_generator_models_are_pydantic_classes(analyzed_petstore: ServerIR, tmp_path: Path) -> None:
    """Generated models.py should contain Pydantic models for component schemas."""

    output_dir = tmp_path / "models_output"
    MCPGenerator().generate(analyzed_petstore, output_dir)

    package_dir = output_dir / "src" / f"{analyzed_petstore.server_name}_mcp_server"
    models_source = (package_dir / "models.py").read_text(encoding="utf-8")

    assert "from pydantic import" in models_source
    assert "BaseModel" in models_source
    assert "ConfigDict" in models_source
    assert "Field" in models_source
    assert "class Pet(BaseModel):" in models_source
    assert "class NewPet(BaseModel):" in models_source
    assert "model_config = ConfigDict(" in models_source


def test_generator_uses_fastmcp_instructions_field(analyzed_petstore: ServerIR, tmp_path: Path) -> None:
    """Generated server should initialize FastMCP with instructions field."""

    output_dir = tmp_path / "instructions_output"
    MCPGenerator().generate(analyzed_petstore, output_dir)

    package_dir = output_dir / "src" / f"{analyzed_petstore.server_name}_mcp_server"
    server_source = (package_dir / "server.py").read_text(encoding="utf-8")

    assert 'instructions="' in server_source


def test_generator_uses_structured_output_for_json_tools(analyzed_petstore: ServerIR, tmp_path: Path) -> None:
    """JSON response tools should emit structured output and TypeAdapter usage."""

    output_dir = tmp_path / "structured_output"
    MCPGenerator().generate(analyzed_petstore, output_dir)

    package_dir = output_dir / "src" / f"{analyzed_petstore.server_name}_mcp_server"
    server_source = (package_dir / "server.py").read_text(encoding="utf-8")
    tool_source = (package_dir / "tools" / "list_pets.py").read_text(encoding="utf-8")

    assert "@mcp.tool(structured_output=True)" in server_source
    assert "from pydantic import TypeAdapter" in tool_source
    assert "TypeAdapter(" in tool_source


def test_generator_form_urlencoded_request_uses_data(tmp_path: Path) -> None:
    """Form-url-encoded request bodies should map to request_kwargs['data']."""

    spec = tmp_path / "form.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: Form API
  version: "1.0"
paths:
  /submit:
    post:
      operationId: submitForm
      requestBody:
        required: true
        content:
          application/x-www-form-urlencoded:
            schema:
              type: object
              required: [name]
              properties:
                name:
                  type: string
                age:
                  type: integer
      responses:
        "200":
          description: ok
""".strip(),
        encoding="utf-8",
    )

    ir = analyze_spec(parse_spec(spec), AnalyzerConfig(max_tools=10))
    output_dir = tmp_path / "form_output"
    MCPGenerator().generate(ir, output_dir)

    package_dir = output_dir / "src" / f"{ir.server_name}_mcp_server"
    tool_file = package_dir / "tools" / "submit_form.py"
    tool_source = tool_file.read_text(encoding="utf-8")

    assert 'request_kwargs["data"] = data_body' in tool_source
    assert 'data_body["name"] = name' in tool_source
    compile(tool_source, str(tool_file), "exec")


def test_generator_multipart_request_uses_files_for_binary(tmp_path: Path) -> None:
    """Multipart request bodies should map binary fields to files payload."""

    spec = tmp_path / "multipart.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: Upload API
  version: "1.0"
paths:
  /upload:
    post:
      operationId: uploadFile
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required: [file]
              properties:
                file:
                  type: string
                  format: binary
                note:
                  type: string
      responses:
        "200":
          description: ok
""".strip(),
        encoding="utf-8",
    )

    ir = analyze_spec(parse_spec(spec), AnalyzerConfig(max_tools=10))
    output_dir = tmp_path / "multipart_output"
    MCPGenerator().generate(ir, output_dir)

    package_dir = output_dir / "src" / f"{ir.server_name}_mcp_server"
    tool_file = package_dir / "tools" / "upload_file.py"
    tool_source = tool_file.read_text(encoding="utf-8")

    assert 'files_body["file"] = ("file.bin", file)' in tool_source
    assert 'request_kwargs["files"] = files_body' in tool_source
    assert 'request_kwargs["data"] = data_body' in tool_source
    compile(tool_source, str(tool_file), "exec")


def test_generator_allof_child_inherits_parent(tmp_path: Path) -> None:
    """Generated models should render allOf child classes as parent subclasses."""

    spec = tmp_path / "allof.yaml"
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
    output_dir = tmp_path / "allof_output"
    MCPGenerator().generate(ir, output_dir)

    package_dir = output_dir / "src" / f"{ir.server_name}_mcp_server"
    models_file = package_dir / "models.py"
    models_source = models_file.read_text(encoding="utf-8")

    assert models_source.index("class Base(") < models_source.index("class Child(")
    assert "class Child(Base):" in models_source
    assert "name: str" in models_source
    assert "id: str" in models_source
    compile(models_source, str(models_file), "exec")


def test_generator_supports_template_overrides(analyzed_petstore: ServerIR, tmp_path: Path) -> None:
    """Custom template directory should override packaged templates."""

    template_dir = tmp_path / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "server.py.jinja2").write_text(
        '''
"""Custom server template for {{ server_title }}."""
from __future__ import annotations

CUSTOM_TEMPLATE_MARKER = "{{ server_name }}"


def main() -> None:
    return None
'''.strip(),
        encoding="utf-8",
    )

    output_dir = tmp_path / "template_override_output"
    MCPGenerator(template_dir=template_dir).generate(analyzed_petstore, output_dir)

    package_dir = output_dir / "src" / f"{analyzed_petstore.server_name}_mcp_server"
    server_source = (package_dir / "server.py").read_text(encoding="utf-8")

    assert "CUSTOM_TEMPLATE_MARKER" in server_source
    assert "Custom server template" in server_source
