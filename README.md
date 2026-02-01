# robo_template

## Dynamic Pytest Log Level Control

You can control the pytest log level dynamically using an environment variable when running tests from the command line.

### Windows PowerShell
```powershell
$env:LOG_LEVEL="WARNING"
pytest --log-cli-level=$env:LOG_LEVEL
```

### Windows Command Prompt
```cmd
set LOG_LEVEL=WARNING
pytest --log-cli-level=%LOG_LEVEL%
```

### Linux/macOS
```bash
export LOG_LEVEL=WARNING
pytest --log-cli-level=$LOG_LEVEL
```

Replace `WARNING` with any valid log level (e.g., `INFO`, `ERROR`, `DEBUG`).