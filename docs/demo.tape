Output docs/demo.gif

Set Theme "Catppuccin Mocha"
Set Width 1200
Set Height 700
Set FontSize 18
Set TypingSpeed 35ms

Type "cd /home/ubuntu/mcp-toolbox"
Enter
Sleep 1s

Type "echo"
Enter
Type "echo '🚀 Step 1/4: Generate MCP server'"
Enter
Sleep 2s

Type "PYTHONPATH=src .venv/bin/python -m mcp_toolbox.cli generate --spec tests/fixtures/petstore.yaml -o /tmp/mcp-demo-out"
Enter
Sleep 3s

Type "echo"
Enter
Type "echo '📁 Step 2/4: Inspect package structure'"
Enter
Sleep 2s

Type "ls -la /tmp/mcp-demo-out/src"
Enter
Sleep 3s

Type "echo"
Enter
Type "echo '🧩 Step 3/4: Preview server entrypoint'"
Enter
Sleep 2s

Type "sed -n '1,50p' /tmp/mcp-demo-out/src/petstore_api_mcp_server/server.py"
Enter
Sleep 3s

Type "echo"
Enter
Type "echo '✅ Step 4/4: Run generator tests'"
Enter
Sleep 2s

Type ".venv/bin/python -m pytest -q tests/test_generator.py"
Enter
Sleep 5s
