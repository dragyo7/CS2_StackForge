[CmdletBinding()]
param(
    [switch]$Stop,
    [int]$BackendPort = 8001,
    [int]$FrontendPort = 5174,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$ProjectRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$ViteScript = Join-Path $FrontendDir "node_modules\vite\bin\vite.js"
$LogsDir = Join-Path $ProjectRoot "logs"
$PidFile = Join-Path $ProjectRoot ".stackforge-pids.json"

$BackendOutLog = Join-Path $LogsDir "backend.out.log"
$BackendErrLog = Join-Path $LogsDir "backend.err.log"
$FrontendOutLog = Join-Path $LogsDir "frontend.out.log"
$FrontendErrLog = Join-Path $LogsDir "frontend.err.log"

$BackendUrl = "http://127.0.0.1:$BackendPort"
$FrontendUrl = "http://127.0.0.1:$FrontendPort"

function Write-Info([string]$Msg) {
    Write-Host "[StackForge] $Msg" -ForegroundColor Cyan
}

function Write-Ok([string]$Msg) {
    Write-Host "[StackForge] [OK] $Msg" -ForegroundColor Green
}

function Write-Warn([string]$Msg) {
    Write-Host "[StackForge] [WARN] $Msg" -ForegroundColor Yellow
}

function Write-Fail([string]$Msg) {
    Write-Host "[StackForge] [ERROR] $Msg" -ForegroundColor Red
}

function Get-PortListenerInfo([int]$Port) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $conn) {
            return $null
        }
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $($conn.OwningProcess)" -ErrorAction SilentlyContinue
        return [pscustomobject]@{
            Pid         = [int]$conn.OwningProcess
            ProcessName = if ($proc) { $proc.Name } else { "unknown" }
            CommandLine = if ($proc) { [string]$proc.CommandLine } else { "" }
        }
    } catch {
        return $null
    }
}

function Test-StackForgeBackend([int]$Port) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($resp.StatusCode -ne 200) {
            return $null
        }
        $json = $resp.Content | ConvertFrom-Json -ErrorAction Stop
        if ($json.status -eq "ok" -and $json.map_policy -eq "random_no_picker" -and $null -ne $json.providers) {
            return $json
        }
        return $null
    } catch {
        return $null
    }
}

function Test-StackForgeFrontend([int]$Port) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($resp.StatusCode -eq 200 -and $resp.Content -match "StackForge") {
            return $true
        }
        return $false
    } catch {
        return $false
    }
}

function Test-IsTrackedProcess([int]$CandidatePid, $StateSection) {
    if ($null -eq $StateSection -or $StateSection.managed -ne $true -or $CandidatePid -le 0) {
        return $false
    }
    $trackedPids = @()
    if ($StateSection.pid) { $trackedPids += [int]$StateSection.pid }
    if ($StateSection.launcherPid) { $trackedPids += [int]$StateSection.launcherPid }
    if ($trackedPids -contains $CandidatePid) {
        return $true
    }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $CandidatePid" -ErrorAction SilentlyContinue
    if ($proc -and $trackedPids -contains ([int]$proc.ParentProcessId)) {
        return $true
    }
    return $false
}

function Stop-TrackedTree([int]$RootPid, [string]$ExpectedProjectRoot) {
    if ($RootPid -le 0) { return $false }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $RootPid" -ErrorAction SilentlyContinue
    if ($null -eq $proc) {
        return $false
    }
    $cmd = [string]$proc.CommandLine
    $normalizedRoot = $ExpectedProjectRoot.ToLowerInvariant()
    $matchesStackForge = (
        $cmd.ToLowerInvariant().Contains($normalizedRoot) -or
        ($cmd -match "uvicorn\s+app\.main:app") -or
        ($cmd -match "vite\.js")
    )
    if (-not $matchesStackForge) {
        Write-Warn "Skipping PID $RootPid ($($proc.Name)): command line does not match StackForge ($cmd)."
        return $false
    }

    # Find direct/nested child processes belonging to this tracked root process before terminating root
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $RootPid" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        $cPid = [int]$child.ProcessId
        if ($cPid -gt 0 -and $cPid -ne $PID) {
            Stop-Process -Id $cPid -Force -ErrorAction SilentlyContinue
        }
    }
    Stop-Process -Id $RootPid -Force -ErrorAction SilentlyContinue
    Write-Ok "Stopped tracked StackForge process PID $RootPid ($($proc.Name))."
    return $true
}

function Wait-PortReleased([int]$Port, [int]$TimeoutSeconds = 5) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($null -eq (Get-PortListenerInfo -Port $Port)) {
            return
        }
        Start-Sleep -Milliseconds 200
    }
}

function Stop-ServiceSection([string]$Label, $Section, [string]$ExpectedProjectRoot) {
    if ($null -eq $Section -or -not $Section.pid) {
        return
    }
    if ($Section.managed -ne $true) {
        Write-Info "$Label PID $($Section.pid) was reused (not started by launcher); leaving untouched."
        return
    }
    $pidsToStop = @()
    if ($Section.pid) { $pidsToStop += [int]$Section.pid }
    if ($Section.launcherPid -and ($pidsToStop -notcontains [int]$Section.launcherPid)) {
        $pidsToStop += [int]$Section.launcherPid
    }
    foreach ($p in $pidsToStop) {
        [void](Stop-TrackedTree -RootPid $p -ExpectedProjectRoot $ExpectedProjectRoot)
    }
    if ($Section.port) {
        Wait-PortReleased -Port ([int]$Section.port) -TimeoutSeconds 5
    }
}

function Invoke-StackForgeStop {
    if (-not (Test-Path $PidFile)) {
        Write-Info "No tracked launcher PID file found at $PidFile. Nothing to stop."
        return
    }
    try {
        $state = Get-Content -Path $PidFile -Raw | ConvertFrom-Json -ErrorAction Stop
    } catch {
        Write-Warn "Could not parse $PidFile; removing stale PID file without touching running processes."
        Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
        return
    }

    Stop-ServiceSection -Label "Frontend" -Section $state.frontend -ExpectedProjectRoot $ProjectRoot
    Stop-ServiceSection -Label "Backend" -Section $state.backend -ExpectedProjectRoot $ProjectRoot

    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
    Write-Ok "StackForge shutdown complete."
}

if ($Stop) {
    Invoke-StackForgeStop
    exit 0
}

# Pre-flight validation (fail clearly; never auto-install dependencies)
if (-not (Test-Path $BackendDir) -or -not (Test-Path $FrontendDir)) {
    Write-Fail "Expected backend and frontend directories under '$ProjectRoot'."
    exit 1
}

if (-not (Test-Path $VenvPython)) {
    Write-Fail "Missing Python virtual environment at '$VenvPython'."
    Write-Host "Fix: cd `"$BackendDir`" && python -m venv .venv && .\.venv\Scripts\pip install -r requirements.txt"
    exit 1
}

$NodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($null -eq $NodeCmd) {
    Write-Fail "Node.js ('node') was not found on PATH."
    Write-Host "Fix: Install Node.js 18+ and ensure 'node' is available in PATH."
    exit 1
}

if (-not (Test-Path $ViteScript)) {
    Write-Fail "Missing Vite installation at '$ViteScript'."
    Write-Host "Fix: cd `"$FrontendDir`" && npm install"
    exit 1
}

if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

$existingState = $null
if (Test-Path $PidFile) {
    try { $existingState = Get-Content -Path $PidFile -Raw | ConvertFrom-Json -ErrorAction SilentlyContinue } catch {}
}

$backendManaged = $false
$backendPid = $null
$backendLauncherPid = $null
$frontendManaged = $false
$frontendPid = $null
$frontendLauncherPid = $null

# 1. Inspect or start Backend
$backendHealth = Test-StackForgeBackend -Port $BackendPort
$backendListener = Get-PortListenerInfo -Port $BackendPort

if ($null -ne $backendHealth) {
    $backendPid = if ($backendListener) { $backendListener.Pid } else { $null }
    if ($backendPid -and (Test-IsTrackedProcess -CandidatePid $backendPid -StateSection $existingState.backend)) {
        $backendManaged = $true
        $backendLauncherPid = if ($existingState.backend.launcherPid) { [int]$existingState.backend.launcherPid } else { $null }
    }
    Write-Ok "Backend already running & healthy on $BackendUrl (PID: $backendPid) — reusing existing instance."
} elseif ($null -ne $backendListener) {
    Write-Fail "Port $BackendPort is already occupied by an unrelated process: $($backendListener.ProcessName) (PID $($backendListener.Pid))."
    Write-Host "Command: $($backendListener.CommandLine)"
    Write-Host "StackForge will NOT terminate unrelated processes. Free port $BackendPort or pass -BackendPort <port>."
    exit 1
} else {
    Write-Info "Starting StackForge V2 backend on $BackendUrl..."
    "=== StackForge Backend Start $(Get-Date -Format o) (port $BackendPort) ===" | Set-Content -Path $BackendOutLog -Encoding UTF8
    "" | Set-Content -Path $BackendErrLog -Encoding UTF8

    $prevPyUnbuf = $env:PYTHONUNBUFFERED
    $env:PYTHONUNBUFFERED = "1"
    try {
        $procB = Start-Process `
            -FilePath $VenvPython `
            -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort") `
            -WorkingDirectory $BackendDir `
            -WindowStyle Hidden `
            -RedirectStandardOutput $BackendOutLog `
            -RedirectStandardError $BackendErrLog `
            -PassThru
    } finally {
        if ($null -eq $prevPyUnbuf) {
            Remove-Item Env:PYTHONUNBUFFERED -ErrorAction SilentlyContinue
        } else {
            $env:PYTHONUNBUFFERED = $prevPyUnbuf
        }
    }

    $backendLauncherPid = $procB.Id
    $backendPid = $procB.Id
    $backendManaged = $true

    $deadline = (Get-Date).AddSeconds(30)
    $readyB = $false
    while ((Get-Date) -lt $deadline) {
        if ($procB.HasExited) {
            Write-Fail "Backend process exited early with code $($procB.ExitCode)."
            if (Test-Path $BackendErrLog) {
                Get-Content -Path $BackendErrLog -Tail 25 | ForEach-Object { Write-Host "  $_" }
            }
            exit 1
        }
        $backendHealth = Test-StackForgeBackend -Port $BackendPort
        if ($null -ne $backendHealth) {
            $readyB = $true
            break
        }
        Start-Sleep -Milliseconds 400
    }
    if (-not $readyB) {
        Write-Fail "Timed out waiting for StackForge backend health at $BackendUrl/api/health."
        [void](Stop-TrackedTree -RootPid $backendLauncherPid -ExpectedProjectRoot $ProjectRoot)
        exit 1
    }
    $resolvedBackendListener = Get-PortListenerInfo -Port $BackendPort
    if ($resolvedBackendListener -and $resolvedBackendListener.Pid) {
        $backendPid = $resolvedBackendListener.Pid
    }
    Write-Ok "Backend healthy on $BackendUrl (PID: $backendPid, scheduler: $($backendHealth.scheduler))."
}

# 2. Inspect or start Frontend
$frontendHealthy = Test-StackForgeFrontend -Port $FrontendPort
$frontendListener = Get-PortListenerInfo -Port $FrontendPort

if ($frontendHealthy) {
    $frontendPid = if ($frontendListener) { $frontendListener.Pid } else { $null }
    if ($frontendPid -and (Test-IsTrackedProcess -CandidatePid $frontendPid -StateSection $existingState.frontend)) {
        $frontendManaged = $true
        $frontendLauncherPid = if ($existingState.frontend.launcherPid) { [int]$existingState.frontend.launcherPid } else { $null }
    }
    Write-Ok "Frontend already running & healthy on $FrontendUrl (PID: $frontendPid) — reusing existing instance."
} elseif ($null -ne $frontendListener) {
    Write-Fail "Port $FrontendPort is already occupied by an unrelated process: $($frontendListener.ProcessName) (PID $($frontendListener.Pid))."
    Write-Host "Command: $($frontendListener.CommandLine)"
    Write-Host "StackForge will NOT terminate unrelated processes. Free port $FrontendPort or pass -FrontendPort <port>."
    exit 1
} else {
    Write-Info "Starting StackForge V2 frontend on $FrontendUrl (API proxy -> $BackendUrl)..."
    "=== StackForge Frontend Start $(Get-Date -Format o) (port $FrontendPort -> $BackendUrl) ===" | Set-Content -Path $FrontendOutLog -Encoding UTF8
    "" | Set-Content -Path $FrontendErrLog -Encoding UTF8

    $prevTarget = $env:VITE_API_TARGET
    $env:VITE_API_TARGET = $BackendUrl
    try {
        $procF = Start-Process `
            -FilePath $NodeCmd.Source `
            -ArgumentList @($ViteScript, "--host", "127.0.0.1", "--port", "$FrontendPort", "--strictPort") `
            -WorkingDirectory $FrontendDir `
            -WindowStyle Hidden `
            -RedirectStandardOutput $FrontendOutLog `
            -RedirectStandardError $FrontendErrLog `
            -PassThru
    } finally {
        if ($null -eq $prevTarget) {
            Remove-Item Env:VITE_API_TARGET -ErrorAction SilentlyContinue
        } else {
            $env:VITE_API_TARGET = $prevTarget
        }
    }

    $frontendLauncherPid = $procF.Id
    $frontendPid = $procF.Id
    $frontendManaged = $true

    $deadlineF = (Get-Date).AddSeconds(30)
    $readyF = $false
    while ((Get-Date) -lt $deadlineF) {
        if ($procF.HasExited) {
            Write-Fail "Frontend process exited early with code $($procF.ExitCode)."
            if (Test-Path $FrontendErrLog) {
                Get-Content -Path $FrontendErrLog -Tail 25 | ForEach-Object { Write-Host "  $_" }
            }
            if ($backendManaged -and $backendPid) {
                [void](Stop-TrackedTree -RootPid $backendPid -ExpectedProjectRoot $ProjectRoot)
                if ($backendLauncherPid -and $backendLauncherPid -ne $backendPid) {
                    [void](Stop-TrackedTree -RootPid $backendLauncherPid -ExpectedProjectRoot $ProjectRoot)
                }
            }
            exit 1
        }
        if (Test-StackForgeFrontend -Port $FrontendPort) {
            $readyF = $true
            break
        }
        Start-Sleep -Milliseconds 400
    }
    if (-not $readyF) {
        Write-Fail "Timed out waiting for StackForge frontend at $FrontendUrl/."
        [void](Stop-TrackedTree -RootPid $frontendLauncherPid -ExpectedProjectRoot $ProjectRoot)
        if ($backendManaged -and $backendPid) {
            [void](Stop-TrackedTree -RootPid $backendPid -ExpectedProjectRoot $ProjectRoot)
            if ($backendLauncherPid -and $backendLauncherPid -ne $backendPid) {
                [void](Stop-TrackedTree -RootPid $backendLauncherPid -ExpectedProjectRoot $ProjectRoot)
            }
        }
        exit 1
    }
    $resolvedFrontendListener = Get-PortListenerInfo -Port $FrontendPort
    if ($resolvedFrontendListener -and $resolvedFrontendListener.Pid) {
        $frontendPid = $resolvedFrontendListener.Pid
    }
    Write-Ok "Frontend healthy on $FrontendUrl (PID: $frontendPid)."
}

# Persist tracked PID metadata
$pidPayload = @{
    updatedAt = (Get-Date -Format o)
    backend   = @{
        pid         = $backendPid
        launcherPid = $backendLauncherPid
        port        = $BackendPort
        managed     = $backendManaged
    }
    frontend  = @{
        pid         = $frontendPid
        launcherPid = $frontendLauncherPid
        port        = $FrontendPort
        managed     = $frontendManaged
    }
}
$pidPayload | ConvertTo-Json -Depth 4 | Set-Content -Path $PidFile -Encoding UTF8

Write-Host ""
Write-Ok "StackForge Ready:"
Write-Host "  Frontend : $FrontendUrl/"
Write-Host "  Backend  : $BackendUrl/api/health"
Write-Host "  Logs     : $LogsDir"
Write-Host "  Shutdown : .\Start-StackForge.ps1 -Stop"

if (-not $NoBrowser) {
    Write-Info "Opening browser at $FrontendUrl/ ..."
    Start-Process "$FrontendUrl/"
}
exit 0
