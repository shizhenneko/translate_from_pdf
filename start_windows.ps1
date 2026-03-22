param(
    [int]$Port = 10001,
    [string]$BindHost = "127.0.0.1",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PYTHONUNBUFFERED = "1"
$env:HF_HUB_DISABLE_PROGRESS_BARS = "0"

$RootDir = Split-Path -Parent $PSCommandPath
$VenvDir = Join-Path $RootDir ".venv-windows"

Set-Location $RootDir

function Test-PythonVersion {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    try {
        $versionText = & $Command @Arguments -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $versionText) {
            return $null
        }

        return [version]($versionText | Select-Object -Last 1).Trim()
    }
    catch {
        return $null
    }
}

function Resolve-Python {
    $candidates = @(
        @{ Command = "py"; Arguments = @("-3.12") },
        @{ Command = "py"; Arguments = @("-3.11") },
        @{ Command = "py"; Arguments = @("-3.10") },
        @{ Command = "python"; Arguments = @() },
        @{ Command = "py"; Arguments = @() }
    )

    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Command -ErrorAction SilentlyContinue)) {
            continue
        }

        $version = Test-PythonVersion -Command $candidate.Command -Arguments $candidate.Arguments
        if (-not $version) {
            continue
        }

        if ($version.Major -ne 3 -or $version.Minor -lt 10) {
            continue
        }

        return @{
            Command = $candidate.Command
            Arguments = $candidate.Arguments
            Version = $version
        }
    }

    throw "Python 3.10+ is required. Install Python 3.10, 3.11, or 3.12 and ensure `py` or `python` is available."
}

function Invoke-Python {
    param(
        [hashtable]$Python,
        [string[]]$Arguments
    )

    & $Python.Command @($Python.Arguments + $Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $($Python.Command) $($Python.Arguments + $Arguments -join ' ')"
    }
}

function Resolve-MarkerCommand {
    param(
        [string]$ScriptsDir
    )

    $candidates = @(
        (Join-Path $ScriptsDir "marker_single.exe"),
        (Join-Path $ScriptsDir "marker.exe"),
        (Join-Path $ScriptsDir "marker_single"),
        (Join-Path $ScriptsDir "marker")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return "marker_single"
}

if ($null -eq $ExtraArgs) {
    $ExtraArgs = @()
}

if ($ExtraArgs.Count -gt 0 -and $ExtraArgs[0] -eq "--") {
    if ($ExtraArgs.Count -eq 1) {
        $ExtraArgs = @()
    }
    else {
        $ExtraArgs = $ExtraArgs[1..($ExtraArgs.Count - 1)]
    }
}

$Python = Resolve-Python
$PythonArgsDisplay = ($Python.Arguments -join " ").Trim()
if ($PythonArgsDisplay) {
    Write-Host ("Using Python {0} via {1} {2}" -f $Python.Version, $Python.Command, $PythonArgsDisplay)
}
else {
    Write-Host ("Using Python {0} via {1}" -f $Python.Version, $Python.Command)
}

if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating Windows virtual environment in .venv-windows"
    Invoke-Python -Python $Python -Arguments @("-m", "venv", $VenvDir)
}

$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$ScriptsDir = Join-Path $VenvDir "Scripts"
if (-not (Test-Path $PythonExe)) {
    throw "Virtual environment was not created correctly: $PythonExe"
}

Write-Host "[1/5] Upgrading pip in .venv-windows"
& $PythonExe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip in .venv-windows"
}

Write-Host "[2/5] Installing project dependencies"
& $PythonExe -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install project dependencies in .venv-windows"
}

Write-Host "[3/5] Ensuring marker-pdf is installed"
& $PythonExe -m pip install marker-pdf
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install marker-pdf in .venv-windows"
}

$env:PDF_TRANSLATE_MARKER_COMMAND = Resolve-MarkerCommand -ScriptsDir $ScriptsDir
Write-Host "Using Marker command: $env:PDF_TRANSLATE_MARKER_COMMAND"
Write-Host "[4/5] Starting local web service"
Write-Host "Marker first run may download multiple models. Progress will be shown live in this window."
Write-Host "If the web UI says stage=marker, watch this terminal for model download bars and initialization logs."

Write-Host "[5/5] Web UI is launching"
& $PythonExe -m pdf_translate serve --host $BindHost --port $Port @ExtraArgs
exit $LASTEXITCODE
