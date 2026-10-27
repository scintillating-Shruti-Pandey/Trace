param(
    [ValidateSet('up', 'test', 'logs', 'stop', 'status')]
    [string]$Action = 'up'
)
$ErrorActionPreference = 'Stop'
$traceRoot = Split-Path -Parent $PSScriptRoot
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCommand) {
    $traceDocker = $dockerCommand.Source
} else {
    $traceDocker = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
    if (-not (Test-Path -LiteralPath $traceDocker)) {
        $traceDocker = Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe'
    }
}
if (-not (Test-Path -LiteralPath $traceDocker)) {
    throw 'Docker CLI is missing. Install and start Docker Desktop before continuing.'
}
# A newly installed Docker Desktop may not yet be in this terminal's PATH.
$env:PATH = (Split-Path -Parent $traceDocker) + ';' + $env:PATH
Push-Location $traceRoot
try {
    switch ($Action) {
        'up' { & $traceDocker compose up --build -d }
        'test' {
            & $traceDocker compose run --rm --no-deps -e TRACE_INTEGRATION=1 -e SEARCH_ENABLED=false `
                -v "${traceRoot}:/workspace" -w /workspace api `
                python -m pytest -q -p no:cacheprovider
        }
        'logs' { & $traceDocker compose logs --tail 100 api migrate }
        'stop' { & $traceDocker compose stop }
        'status' { & $traceDocker compose ps }
    }
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}
