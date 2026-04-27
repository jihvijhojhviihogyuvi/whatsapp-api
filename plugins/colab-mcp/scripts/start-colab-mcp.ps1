param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"

# Force uv to use writable locations in this workspace.
if (-not $env:UV_CACHE_DIR -or [string]::IsNullOrWhiteSpace($env:UV_CACHE_DIR)) {
  $env:UV_CACHE_DIR = "C:\Users\james\OneDrive\Documents\Playground\.uv-cache"
}

# Prefer the Python already available on PATH in this environment.
if (-not $env:UV_PYTHON -or [string]::IsNullOrWhiteSpace($env:UV_PYTHON)) {
  $env:UV_PYTHON = "python"
}

# Optional compatibility flag for corporate/non-standard package indexes.
$installTarget = "git+https://github.com/googlecolab/colab-mcp"
$extraArgs = @()
if ($env:COLAB_MCP_USE_PYPI_INDEX -eq "1") {
  $extraArgs += @("--index", "https://pypi.org/simple")
}

& uvx @extraArgs $installTarget @RemainingArgs
exit $LASTEXITCODE
