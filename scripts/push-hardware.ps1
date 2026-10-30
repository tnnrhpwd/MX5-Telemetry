<#
.SYNOPSIS
    Pushes the current repository state onto every MX5-Telemetry device.

.DESCRIPTION
    One command that gets your changes onto the car:

        android  build both MX5 Remote flavors (parked + drive) and `adb install -r`
                 them on the phone that is plugged in (USB or `adb connect`).
        arduino  build and upload the Nano LED firmware over local USB. If no Nano is
                 plugged into this PC, pass -RemoteArduino to flash the one wired to
                 the Pi instead.
        esp32    build and upload the round-display firmware on the Pi (the ESP32 is
                 permanently wired to the Pi's USB).
        pi       `git pull` on the Pi and restart mx5-display.service.

    The Pi and the ESP32 are updated from GitHub, so any uncommitted work is
    committed and pushed first (disable with -NoGit, override the message with
    -CommitMessage).

    Only components whose sources changed since the last successful push are
    reflashed. That bookkeeping lives in .push-state.json (gitignored). Use -Force
    to reflash everything regardless, e.g. after swapping a board.

.PARAMETER Targets
    Which devices to update: all (default), android, arduino, esp32, pi.
    Accepts several, e.g. -Targets pi,esp32.

.PARAMETER PiHost
    Pi address to use instead of auto-discovery. Auto-discovery tries $env:PI_HOST,
    mx5pi.local, 192.168.1.23 and 10.62.26.67.

.PARAMETER CommitMessage
    Commit message for the auto-commit. Defaults to a generated one that lists the
    areas that changed.

.PARAMETER NoGit
    Do not commit or push. Note that the Pi and ESP32 are updated through git, so
    with -NoGit they only ever receive commits that are already on origin.

.PARAMETER AdbSerial
    Target a specific phone when several are attached (`adb devices` serial).

.PARAMETER ArduinoPort
    Explicit COM port for the Nano, e.g. COM5. Defaults to auto-detection.

.PARAMETER RemoteArduino
    Flash the Arduino through the Pi (/dev/ttyUSB0) instead of the local USB port.
    Also used automatically when no local Nano is detected.

.PARAMETER Esp32Port
    Serial port of the ESP32 on the Pi. Default /dev/ttyACM0.

.PARAMETER InstallPiDeps
    Also run `python3 -m pip install -r pi/ui/requirements.txt` on the Pi.

.PARAMETER Force
    Flash every selected device, even if its sources did not change.

.PARAMETER DryRun
    Print the commands without running them.

.EXAMPLE
    .\scripts\push-hardware.ps1

    Commit + push pending work, then update the phone, Nano, ESP32 and Pi.

.EXAMPLE
    .\scripts\push-hardware.ps1 -Targets esp32,pi -Force

    Reflash the display and restart the Pi UI without touching the phone or Nano.

.EXAMPLE
    .\scripts\push-hardware.ps1 -Targets android -NoGit

    Rebuild and reinstall the phone app from the current working tree.
#>
#Requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('all', 'android', 'arduino', 'esp32', 'pi')]
    [string[]]$Targets = @('all'),

    [string]$PiHost,
    [string]$PiUser = 'pi',
    [string]$CommitMessage,
    [switch]$NoGit,
    [string]$AdbSerial,
    [string]$ArduinoPort,
    [switch]$RemoteArduino,
    [string]$Esp32Port = '/dev/ttyACM0',
    [switch]$InstallPiDeps,
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = 'Continue'

$RepoRoot    = Split-Path -Parent $PSScriptRoot
$StateFile   = Join-Path $RepoRoot '.push-state.json'
$PiRepoDir   = '~/MX5-Telemetry'
$PiService   = 'mx5-display.service'
$ArduinoDir  = Join-Path $RepoRoot 'arduino'
$DisplayDir  = Join-Path $RepoRoot 'display'

# Source trees that belong to each device. A device is reflashed when anything
# under these paths changed since the last successful push.
$ComponentPaths = @{
    android = @('android/')
    arduino = @('arduino/', 'lib/', 'test/')
    esp32   = @('display/', 'lib/')
    pi      = @('pi/')
}

$script:StepNo   = 0
$script:Failures = New-Object System.Collections.ArrayList
$script:Warnings = New-Object System.Collections.ArrayList
$script:Status   = [ordered]@{}
$script:PiTarget = $null

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
function Write-Banner([string]$Text) {
    Write-Host ''
    Write-Host ('=' * 62) -ForegroundColor Cyan
    Write-Host "   $Text" -ForegroundColor Cyan
    Write-Host ('=' * 62) -ForegroundColor Cyan
}

function Write-Step([string]$Text) {
    $script:StepNo++
    Write-Host ''
    Write-Host ("[{0}] {1}" -f $script:StepNo, $Text) -ForegroundColor Cyan
}

function Write-Info([string]$Text) { Write-Host "    $Text" -ForegroundColor Gray }
function Write-Ok([string]$Text)   { Write-Host "    OK   $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) {
    Write-Host "    WARN $Text" -ForegroundColor Yellow
    [void]$script:Warnings.Add($Text)
}
function Write-Fail([string]$Text) {
    Write-Host "    FAIL $Text" -ForegroundColor Red
    [void]$script:Failures.Add($Text)
}
function Write-Cmd([string]$Text)  { Write-Host "    > $Text" -ForegroundColor DarkGray }

function Set-Status([string]$Name, [string]$Text) {
    $script:Status[$Name] = $Text
}

# ---------------------------------------------------------------------------
# Process helpers
# ---------------------------------------------------------------------------
function Invoke-Native {
    <#
        Runs a native executable, echoes its output, and returns the exit code.
        Output is captured (not piped) so native stderr cannot turn into a
        terminating error under $ErrorActionPreference.
    #>
    param(
        [Parameter(Mandatory)][string]$Exe,
        [string[]]$Arguments = @(),
        [switch]$QuietOnSuccess
    )

    Write-Cmd ("{0} {1}" -f $Exe, ($Arguments -join ' '))
    if ($DryRun) { return 0 }

    $output = & $Exe @Arguments 2>&1
    $code = $LASTEXITCODE

    if ($code -eq 0 -and $QuietOnSuccess) {
        $last = @($output) | Where-Object { "$_" -match '\S' } | Select-Object -Last 1
        if ($last) { Write-Info "$last" }
    }
    else {
        foreach ($line in @($output)) { Write-Host "    $_" -ForegroundColor DarkGray }
    }
    return $code
}

function Get-SshArgs {
    return @(
        '-o', 'ConnectTimeout=8',
        '-o', 'ConnectionAttempts=1',
        '-o', 'StrictHostKeyChecking=accept-new',
        '-o', 'ServerAliveInterval=15',
        '-o', 'LogLevel=ERROR'
    )
}

function Invoke-Ssh {
    # Runs a single shell command on the Pi. Returns the exit code.
    param([Parameter(Mandatory)][string]$Command)

    Write-Cmd "ssh $script:PiTarget `"$Command`""
    if ($DryRun) { return 0 }

    $sshArgs = Get-SshArgs
    $output = & ssh @sshArgs $script:PiTarget $Command 2>&1
    $code = $LASTEXITCODE
    foreach ($line in @($output)) { Write-Host "    $_" -ForegroundColor DarkGray }
    return $code
}

# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------
function Resolve-PlatformIO {
    $candidates = @(
        (Join-Path $env:USERPROFILE '.platformio\penv\Scripts\pio.exe'),
        (Get-Command pio -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
        (Get-Command platformio -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    return $null
}

function Resolve-Adb {
    $roots = @($env:ANDROID_HOME, $env:ANDROID_SDK_ROOT, (Join-Path $env:LOCALAPPDATA 'Android\Sdk'))
    foreach ($r in $roots) {
        if (-not $r) { continue }
        $exe = Join-Path $r 'platform-tools\adb.exe'
        if (Test-Path $exe) { return $exe }
    }
    $onPath = Get-Command adb -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    return $null
}

function Resolve-Gradle {
    # Prefer the pinned Gradle the Android README uses, then the repo wrapper.
    $pinned = Join-Path $env:LOCALAPPDATA 'Android\gradle-8.11.1\bin\gradle.bat'
    if (Test-Path $pinned) { return $pinned }
    $wrapper = Join-Path $RepoRoot 'android\gradlew.bat'
    if (Test-Path $wrapper) { return $wrapper }
    $onPath = Get-Command gradle -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    return $null
}

function Ensure-AndroidSdkEnv {
    if ($env:ANDROID_HOME) { return }
    $localProps = Join-Path $RepoRoot 'android\local.properties'
    if (Test-Path $localProps) {
        $line = Get-Content $localProps | Where-Object { $_ -match '^\s*sdk\.dir\s*=' } | Select-Object -First 1
        if ($line) {
            $env:ANDROID_HOME = ($line -replace '^\s*sdk\.dir\s*=', '').Replace('/', '\').Trim()
            Write-Info "ANDROID_HOME=$env:ANDROID_HOME (from android/local.properties)"
            return
        }
    }
    $fallback = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
    if (Test-Path $fallback) { $env:ANDROID_HOME = $fallback }
}

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------
function Invoke-Git {
    param([string[]]$Arguments)
    $output = & git -C $RepoRoot @Arguments 2>&1
    $code = $LASTEXITCODE
    return [pscustomobject]@{ Code = $code; Output = @($output) }
}

function Get-HeadSha {
    if ($DryRun) { return 'HEAD' }
    $r = Invoke-Git @('rev-parse', 'HEAD')
    if ($r.Code -ne 0) { return $null }
    return ("$($r.Output[0])").Trim()
}

function Get-CurrentBranch {
    $r = Invoke-Git @('rev-parse', '--abbrev-ref', 'HEAD')
    if ($r.Code -ne 0) { return 'HEAD' }
    return ("$($r.Output[0])").Trim()
}

function Get-ChangedAreas([string[]]$Porcelain) {
    $areas = New-Object System.Collections.ArrayList
    $map = @(
        @{ Pattern = 'android/'; Label = 'Android' },
        @{ Pattern = 'display/'; Label = 'ESP32' },
        @{ Pattern = 'arduino/'; Label = 'Arduino' },
        @{ Pattern = 'lib/';     Label = 'FirmwareLibs' },
        @{ Pattern = 'pi/';      Label = 'Pi' }
    )
    foreach ($m in $map) {
        if ($Porcelain -match ([regex]::Escape($m.Pattern))) { [void]$areas.Add($m.Label) }
    }
    if ($areas.Count -eq 0) { [void]$areas.Add('misc') }
    return ($areas | Select-Object -Unique)
}

function Invoke-GitSync {
    <#
        Commits pending work and pushes it, because the Pi deploys by pulling from
        GitHub. Returns the commit SHA that the devices should end up running.
    #>
    $porcelain = @()
    $st = Invoke-Git @('status', '--porcelain')
    if ($st.Code -ne 0) {
        Write-Fail "git status failed: $($st.Output -join ' ')"
        return $null
    }
    $porcelain = @($st.Output | Where-Object { "$_" -match '\S' })

    if ($porcelain.Count -gt 0) {
        $areas = Get-ChangedAreas $porcelain
        Write-Info ("{0} uncommitted path(s) detected: {1}" -f $porcelain.Count, ($areas -join ', '))

        $message = if ($CommitMessage) {
            $CommitMessage
        } else {
            "Deploy: {0} - {1}" -f ($areas -join ', '), (Get-Date -Format 'yyyy-MM-dd HH:mm')
        }

        if ($NoGit) {
            Write-Warn "Working tree is dirty and -NoGit was used; the Pi/ESP32 will only see commits already on origin."
        }
        elseif ($DryRun) {
            Write-Info "Would commit all changes as: $message"
        }
        else {
            $add = Invoke-Git @('add', '-A')
            if ($add.Code -ne 0) {
                Write-Fail "git add failed: $($add.Output -join ' ')"
                return $null
            }

            $commitCode = Invoke-Native -Exe 'git' -Arguments @('-C', $RepoRoot, 'commit', '-m', $message) -QuietOnSuccess
            if ($commitCode -ne 0) {
                Write-Fail "git commit failed"
                return $null
            }
            Write-Ok "Committed: $message"
        }
    }
    else {
        Write-Info 'Working tree is clean.'
    }

    if (-not $NoGit) {
        $branch = Get-CurrentBranch
        $ahead = 0
        if (-not $DryRun) {
            $count = Invoke-Git @('rev-list', '--count', "origin/$branch..HEAD")
            if ($count.Code -eq 0) { $ahead = [int]("$($count.Output[0])").Trim() }
            else { $ahead = 1 }   # no upstream tracking branch yet
        }

        if ($ahead -eq 0) {
            Write-Info "Nothing to push; origin/$branch is up to date."
        }
        else {
            $pushArgs = @('-C', $RepoRoot, 'push')
            if ($DryRun) { $pushArgs = @('-C', $RepoRoot, 'push', '-u', 'origin', $branch) }
            elseif ($ahead -eq 1) {
                $hasUpstream = (Invoke-Git @('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}')).Code -eq 0
                if (-not $hasUpstream) { $pushArgs = @('-C', $RepoRoot, 'push', '-u', 'origin', $branch) }
            }

            $pushCode = Invoke-Native -Exe 'git' -Arguments $pushArgs -QuietOnSuccess
            if ($pushCode -ne 0) {
                Write-Fail "git push failed; the Pi would deploy stale code."
                return $null
            }
            Write-Ok "Pushed to origin/$branch."
        }
    }

    return (Get-HeadSha)
}

# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------
function Read-PushState {
    if (-not (Test-Path $StateFile)) { return [pscustomobject]@{} }
    try {
        $parsed = Get-Content $StateFile -Raw | ConvertFrom-Json
        if ($null -eq $parsed) { return [pscustomobject]@{} }
        return $parsed
    }
    catch { return [pscustomobject]@{} }
}

function Save-PushState($State) {
    if ($DryRun) { return }
    try {
        $State | ConvertTo-Json -Depth 5 | Set-Content -Path $StateFile -Encoding UTF8
    }
    catch {
        Write-Warn "Could not write $StateFile ($($_.Exception.Message))"
    }
}

function Test-ComponentChanged {
    <#
        True when any path owned by $Component differs between the last successful
        push of that component and $HeadSha. Unknown/absent state means "changed".
    #>
    param([string]$Component, [string]$HeadSha, $State)

    if ($Force) { return $true }
    if ($DryRun) { return $true }

    $paths = $ComponentPaths[$Component]
    if (-not $paths) { return $true }

    $lastSha = $null
    if ($State -and $State.PSObject.Properties.Name -contains $Component) {
        $lastSha = $State.$Component.sha
    }
    if (-not $lastSha) { return $true }

    $exists = Invoke-Git @('rev-parse', '--verify', '--quiet', "$lastSha^{commit}")
    if ($exists.Code -ne 0) { return $true }

    $diff = Invoke-Git (@('diff', '--name-only', $lastSha, $HeadSha, '--') + $paths)
    if ($diff.Code -ne 0) { return $true }
    return (@($diff.Output | Where-Object { "$_" -match '\S' }).Count -gt 0)
}

function Set-ComponentDeployed {
    param([string]$Component, [string]$HeadSha, $State)
    if (-not $State) { return }
    $entry = [pscustomobject]@{ sha = $HeadSha; at = (Get-Date).ToString('o') }
    if ($State.PSObject.Properties.Name -contains $Component) { $State.$Component = $entry }
    else { $State | Add-Member -NotePropertyName $Component -NotePropertyValue $entry -Force }
}

# ---------------------------------------------------------------------------
# Pi connectivity
# ---------------------------------------------------------------------------
function Resolve-PiTarget {
    if ($script:PiTarget) { return $script:PiTarget }

    $candidates = New-Object System.Collections.ArrayList
    foreach ($c in @($PiHost, $env:PI_HOST, 'mx5pi.local', '192.168.1.23', '10.62.26.67')) {
        if ($c -and -not $candidates.Contains($c)) { [void]$candidates.Add($c) }
    }

    if ($DryRun) {
        $script:PiTarget = "$PiUser@$($candidates[0])"
        Write-Info "Dry run: assuming Pi at $script:PiTarget"
        return $script:PiTarget
    }

    $sshArgs = Get-SshArgs
    foreach ($c in $candidates) {
        Write-Info "Probing $c ..."
        $null = & ssh @sshArgs "$PiUser@$c" 'echo ok' 2>&1
        if ($LASTEXITCODE -eq 0) {
            $script:PiTarget = "$PiUser@$c"
            Write-Ok "Pi reachable at $script:PiTarget"
            return $script:PiTarget
        }
    }
    return $null
}

# ---------------------------------------------------------------------------
# Device phases
# ---------------------------------------------------------------------------
function Invoke-AndroidDeploy {
    Write-Step 'Android app (MX5 Remote + MX5 Drive)'
    Ensure-AndroidSdkEnv

    $gradle = Resolve-Gradle
    if (-not $gradle) {
        Write-Fail 'Gradle not found (looked in %LOCALAPPDATA%\Android, android\gradlew.bat, PATH).'
        Set-Status 'Android' 'FAILED (no gradle)'
        return $false
    }

    $apks = @(
        @{ Flavor = 'parked'; Path = Join-Path $RepoRoot 'android\mx5-remote\build\outputs\apk\parked\debug\mx5-remote-parked-debug.apk' },
        @{ Flavor = 'drive';  Path = Join-Path $RepoRoot 'android\mx5-remote\build\outputs\apk\drive\debug\mx5-remote-drive-debug.apk' }
    )

    Write-Info 'Building both flavors...'
    $buildArgs = @('-p', (Join-Path $RepoRoot 'android'), '--console=plain', '-q',
                   ':mx5-remote:assembleParkedDebug', ':mx5-remote:assembleDriveDebug')
    $buildCode = Invoke-Native -Exe $gradle -Arguments $buildArgs -QuietOnSuccess
    if ($buildCode -ne 0) {
        Write-Fail 'Gradle build failed.'
        Set-Status 'Android' 'FAILED (build)'
        return $false
    }
    Write-Ok 'Build succeeded.'

    foreach ($apk in $apks) {
        if (-not $DryRun -and -not (Test-Path $apk.Path)) {
            Write-Fail "Missing APK: $($apk.Path)"
            Set-Status 'Android' 'FAILED (missing apk)'
            return $false
        }
    }

    $adb = Resolve-Adb
    if (-not $adb) {
        Write-Warn 'adb not found; APKs were built but cannot be installed.'
        Set-Status 'Android' 'BUILT (adb missing)'
        return $false
    }

    $adbPrefix = @()
    if ($AdbSerial) { $adbPrefix = @('-s', $AdbSerial) }
    elseif (-not $DryRun) {
        $adbLines = @(& $adb devices 2>&1 | Select-Object -Skip 1)
        $devices = @($adbLines | Where-Object { "$_" -match '\s+device\s*$' })
        if ($devices.Count -eq 0) {
            if ($adbLines -match 'unauthorized') {
                Write-Warn 'Phone is connected but unauthorized; accept the USB debugging prompt on the phone.'
            }
            else {
                Write-Warn 'No phone detected by adb; APKs built but not installed (plug in USB or run adb connect).'
            }
            Set-Status 'Android' 'BUILT (no device)'
            return $false
        }
        if ($devices.Count -gt 1) {
            Write-Warn ("{0} devices attached; use -AdbSerial to pick one. Using the first." -f $devices.Count)
        }
        $serial = ("$($devices[0])").Split()[0]
        $adbPrefix = @('-s', $serial)
        Write-Info "Installing to $serial"
    }

    $installed = New-Object System.Collections.ArrayList
    foreach ($apk in $apks) {
        $installArgs = $adbPrefix + @('install', '-r', '-d', $apk.Path)
        $code = Invoke-Native -Exe $adb -Arguments $installArgs -QuietOnSuccess
        if ($code -ne 0) {
            Write-Fail "Failed to install $($apk.Flavor) flavor."
            Set-Status 'Android' "FAILED ($($apk.Flavor) install)"
            return $false
        }
        [void]$installed.Add($apk.Flavor)
        Write-Ok "Installed $($apk.Flavor) flavor."
    }

    Set-Status 'Android' ('INSTALLED (' + ($installed -join ' + ') + ')')
    return $true
}

function Get-LocalArduinoPort {
    if ($ArduinoPort) { return $ArduinoPort }

    $pio = Resolve-PlatformIO
    $ports = @()
    if ($pio) {
        $raw = & $pio device list --json-output 2>$null
        if ($raw) {
            try { $ports = @($raw | ConvertFrom-Json) } catch { $ports = @() }
        }
    }

    if ($ports.Count -eq 0) {
        # Fall back to whatever Windows reports.
        foreach ($name in [System.IO.Ports.SerialPort]::GetPortNames()) {
            $ports += [pscustomobject]@{ port = $name; description = ''; hwid = '' }
        }
    }

    $ports = @($ports | Where-Object { $_.port })
    if ($ports.Count -eq 0) { return $null }

    # CH340 (1A86) / FTDI (0403) / genuine USB serial are what Nanos show up as.
    $known = @($ports | Where-Object {
        "$($_.hwid) $($_.description)" -match '1A86|CH340|0403|FTDI|USB.?SERIAL|Arduino'
    })

    if ($known.Count -ge 1) { return $known[0].port }
    if ($ports.Count -eq 1) { return $ports[0].port }
    return $null
}

function Invoke-ArduinoDeploy {
    Write-Step 'Arduino Nano (RPM LED strip)'

    $pio = Resolve-PlatformIO
    if (-not $pio) {
        Write-Fail 'PlatformIO not found; cannot build the Nano firmware.'
        Set-Status 'Arduino' 'FAILED (no pio)'
        return $false
    }

    $port = $null
    if (-not $RemoteArduino) { $port = Get-LocalArduinoPort }

    if ($port) {
        Write-Info "Local Nano detected on $port"
        $code = Invoke-Native -Exe $pio -Arguments @('run', '-d', $ArduinoDir, '--target', 'upload', '--upload-port', $port)
        if ($code -ne 0) {
            Write-Fail "Upload to $port failed (close the serial monitor, or try -RemoteArduino)."
            Set-Status 'Arduino' "FAILED (upload $port)"
            return $false
        }
        Write-Ok "Flashed over USB on $port."
        Set-Status 'Arduino' "UPLOADED ($port)"
        return $true
    }

    if ($RemoteArduino) {
        $target = Resolve-PiTarget
        if (-not $target) {
            Write-Fail 'Arduino remote flash requested but the Pi is unreachable.'
            Set-Status 'Arduino' 'FAILED (no Pi)'
            return $false
        }
        Write-Info 'Flashing the Nano attached to the Pi (/dev/ttyUSB0)'
        $cmd = "cd $PiRepoDir && git pull --ff-only && { PIO=`$HOME/.local/bin/pio; [ -x `"`$PIO`" ] || PIO=pio; `"`$PIO`" run -d arduino --target upload --upload-port /dev/ttyUSB0; }"
        $code = Invoke-Ssh -Command $cmd
        if ($code -ne 0) {
            Write-Fail 'Remote Arduino flash failed.'
            Set-Status 'Arduino' 'FAILED (remote)'
            return $false
        }
        Write-Ok "Flashed via $target."
        Set-Status 'Arduino' "UPLOADED (via $target)"
        return $true
    }

    Write-Warn 'No Nano detected on this PC. Building only; pass -RemoteArduino to flash the one wired to the Pi.'
    $code = Invoke-Native -Exe $pio -Arguments @('run', '-d', $ArduinoDir) -QuietOnSuccess
    if ($code -ne 0) {
        Write-Fail 'Arduino build failed.'
        Set-Status 'Arduino' 'FAILED (build)'
        return $false
    }
    Set-Status 'Arduino' 'BUILT (no device)'
    return $false
}

function Stop-PiDisplayService {
    $null = Invoke-Ssh -Command "sudo systemctl stop $PiService"
}

function Start-PiDisplayService {
    $null = Invoke-Ssh -Command "sudo systemctl start $PiService"
}

function Invoke-Esp32Deploy {
    Write-Step 'ESP32-S3 round display (via Pi)'

    $target = Resolve-PiTarget
    if (-not $target) {
        Write-Fail 'Pi unreachable; the ESP32 can only be flashed through it.'
        Set-Status 'ESP32' 'FAILED (no Pi)'
        return $false
    }

    Write-Info 'Stopping the display service so it releases the ESP32 serial port'
    Stop-PiDisplayService
    $null = Invoke-Ssh -Command "sudo fuser -k $Esp32Port 2>/dev/null || true"
    Start-Sleep -Seconds 2

    $pull = Invoke-Ssh -Command "cd $PiRepoDir && git pull --ff-only"
    if ($pull -ne 0) {
        Write-Fail "git pull failed on $target; ESP32 firmware not updated."
        Start-PiDisplayService
        Set-Status 'ESP32' 'FAILED (pi git pull)'
        return $false
    }

    $flashCmd = "cd $PiRepoDir && { PIO=`$HOME/.local/bin/pio; [ -x `"`$PIO`" ] || PIO=pio; `"`$PIO`" run -d display --target upload --upload-port $Esp32Port; }"
    $code = Invoke-Ssh -Command $flashCmd

    Write-Info 'Restarting the display service'
    Start-PiDisplayService

    if ($code -ne 0) {
        Write-Fail 'ESP32 flash failed (hold BOOT on the ESP32 and retry, or check /dev/ttyACM0).'
        Set-Status 'ESP32' 'FAILED (flash)'
        return $false
    }

    Write-Ok "Flashed via $target ($Esp32Port)."
    Set-Status 'ESP32' "UPLOADED (via $target)"
    return $true
}

function Invoke-PiDeploy {
    Write-Step 'Raspberry Pi application'

    $target = Resolve-PiTarget
    if (-not $target) {
        Write-Fail 'Pi unreachable.'
        Set-Status 'Pi' 'FAILED (no Pi)'
        return $false
    }

    $pull = Invoke-Ssh -Command "cd $PiRepoDir && git pull --ff-only"
    if ($pull -ne 0) {
        Write-Fail "git pull failed on $target. Fix with: ssh $target 'cd MX5-Telemetry && git status'"
        Set-Status 'Pi' 'FAILED (git pull)'
        return $false
    }
    Write-Ok 'Code updated on the Pi.'

    if ($InstallPiDeps) {
        $depCmd = "cd $PiRepoDir && python3 -m pip install -r pi/ui/requirements.txt"
        if ((Invoke-Ssh -Command $depCmd) -ne 0) {
            Write-Warn 'pip install failed; on Raspberry Pi OS Bookworm add --break-system-packages.'
        }
    }

    $restartCmd = "sudo systemctl daemon-reload && sudo systemctl restart $PiService"
    if ((Invoke-Ssh -Command $restartCmd) -ne 0) {
        Write-Fail "Failed to restart $PiService."
        Set-Status 'Pi' 'FAILED (restart)'
        return $false
    }

    Start-Sleep -Seconds 4
    $state = Invoke-Ssh -Command "systemctl is-active $PiService"
    if ($state -ne 0) {
        Write-Fail "$PiService is not active. Recent log:"
        $null = Invoke-Ssh -Command "journalctl -u $PiService -n 40 --no-pager"
        Set-Status 'Pi' 'FAILED (service down)'
        return $false
    }

    Write-Ok "$PiService is running."
    Set-Status 'Pi' "UPDATED + RESTARTED ($target)"
    return $true
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
Write-Banner 'MX5 Telemetry - Push to Hardware'

$selected = $Targets
if ($selected -contains 'all') { $selected = @('android', 'arduino', 'esp32', 'pi') }
$selected = @($selected | Select-Object -Unique)

$wantsAndroid = $selected -contains 'android'
$wantsArduino = $selected -contains 'arduino'
$wantsEsp32   = $selected -contains 'esp32'
$wantsPi      = $selected -contains 'pi'
$needsRemote  = $wantsEsp32 -or $wantsPi -or ($wantsArduino -and $RemoteArduino)

Write-Info "Targets : $($selected -join ', ')"
Write-Info "Repo    : $RepoRoot"
if ($DryRun)    { Write-Info 'Mode    : DRY RUN (no changes are made)' }
if ($Force)     { Write-Info 'Mode    : FORCE (every selected device is reflashed)' }
if ($NoGit)     { Write-Info 'Mode    : NO GIT (nothing committed or pushed)' }

$started = Get-Date

# --- 1. Git sync -----------------------------------------------------------
Write-Step 'Syncing the repository'
$headSha = Invoke-GitSync
$gitOk = [bool]$headSha

if (-not $gitOk) {
    if ($needsRemote) {
        Write-Fail 'Cannot update the Pi/ESP32 without a pushed commit.'
    }
    $wantsEsp32 = $wantsEsp32 -and $false
    $wantsPi = $wantsPi -and $false
    if ($wantsArduino -and $RemoteArduino) { $wantsArduino = $false; Write-Info 'Remote Arduino flash skipped.' }
}

# --- 2. Change detection ---------------------------------------------------
$state = Read-PushState
$plan = @{}
foreach ($c in @('android', 'arduino', 'esp32', 'pi')) {
    $wanted = ($c -eq 'android' -and $wantsAndroid) -or
              ($c -eq 'arduino' -and $wantsArduino) -or
              ($c -eq 'esp32' -and $wantsEsp32) -or
              ($c -eq 'pi' -and $wantsPi)
    if (-not $wanted) { continue }
    $plan[$c] = Test-ComponentChanged -Component $c -HeadSha $headSha -State $state
}

$skipped = @($plan.Keys | Where-Object { -not $plan[$_] })
if ($skipped.Count -gt 0) {
    Write-Info "Unchanged since last push (use -Force to reflash): $($skipped -join ', ')"
    foreach ($c in $skipped) {
        $label = @{ android = 'Android'; arduino = 'Arduino'; esp32 = 'ESP32'; pi = 'Pi' }[$c]
        Set-Status $label 'SKIPPED (unchanged)'
    }
}

# --- 3. Devices ------------------------------------------------------------
$deployed = @{}
if ($plan['android']) { $deployed['android'] = Invoke-AndroidDeploy }
if ($plan['arduino']) { $deployed['arduino'] = Invoke-ArduinoDeploy }
if ($plan['esp32'])   { $deployed['esp32']   = Invoke-Esp32Deploy }
if ($plan['pi'])      { $deployed['pi']      = Invoke-PiDeploy }

# --- 4. Remember what succeeded -------------------------------------------
if (-not $DryRun -and $headSha) {
    $changed = $false
    foreach ($c in $deployed.Keys) {
        if ($deployed[$c]) { Set-ComponentDeployed -Component $c -HeadSha $headSha -State $state; $changed = $true }
    }
    if ($changed) { Save-PushState $state }
}

# --- 5. Summary ------------------------------------------------------------
$elapsed = [int]((Get-Date) - $started).TotalSeconds

Write-Host ''
Write-Host ('-' * 62) -ForegroundColor Cyan
Write-Host '  Summary' -ForegroundColor Cyan
Write-Host ('-' * 62) -ForegroundColor Cyan

$order = @('Android', 'Arduino', 'ESP32', 'Pi')
foreach ($name in $order) {
    if (-not $script:Status.Contains($name)) { continue }
    $value = $script:Status[$name]
    $color = if ($value -match 'FAILED') { 'Red' } elseif ($value -match 'SKIPPED|BUILT') { 'Yellow' } else { 'Green' }
    Write-Host ("  {0,-9} {1}" -f $name, $value) -ForegroundColor $color
}

Write-Host ''
if ($script:Failures.Count -eq 0 -and $script:Warnings.Count -eq 0) {
    Write-Host "  Everything is on the hardware ($elapsed s)." -ForegroundColor Green
}
else {
    if ($script:Warnings.Count -gt 0) {
        Write-Host "  Warnings:" -ForegroundColor Yellow
        foreach ($w in $script:Warnings) { Write-Host "    - $w" -ForegroundColor Yellow }
    }
    if ($script:Failures.Count -gt 0) {
        Write-Host "  Failures:" -ForegroundColor Red
        foreach ($f in $script:Failures) { Write-Host "    - $f" -ForegroundColor Red }
        Write-Host "  Finished with errors ($elapsed s)." -ForegroundColor Red
    }
    else {
        Write-Host "  Finished with warnings ($elapsed s)." -ForegroundColor Yellow
    }
}
Write-Host ''

if ($script:Failures.Count -gt 0) { exit 1 }
exit 0
