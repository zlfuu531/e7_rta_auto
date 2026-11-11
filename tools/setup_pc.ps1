param(
    [string]$PythonExe,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

function Test-Python([string]$Executable, [string[]]$PrefixArgs = @()) {
    try {
        & $Executable @PrefixArgs -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3,12) and sys.maxsize > 2**32 else 1)' 2>$null
        return $LASTEXITCODE -eq 0
    } catch { return $false }
}

try {
    $pythonCommand = $null
    $pythonArgs = @()
    if ($PythonExe) {
        if (-not (Test-Python $PythonExe)) { throw 'PythonExe must be Python 3.12 x64.' }
        $pythonCommand = $PythonExe
    } elseif (Test-Path -LiteralPath $venvPython) {
        if (Test-Python $venvPython) { $pythonCommand = $venvPython }
    }
    if (-not $pythonCommand -and (Get-Command py -ErrorAction SilentlyContinue)) {
        if (Test-Python 'py' @('-3.12')) {
            $pythonCommand = 'py'
            $pythonArgs = @('-3.12')
        }
    }
    if (-not $pythonCommand -and (Get-Command python -ErrorAction SilentlyContinue)) {
        if (Test-Python 'python') { $pythonCommand = 'python' }
    }
    if (-not $pythonCommand) {
        throw 'Install Python 3.12 x64 from https://www.python.org/downloads/windows/ (include Tcl/Tk and the Python launcher), then run setup.bat again.'
    }
    if ($CheckOnly) {
        Write-Output "Python 3.12 x64 found: $pythonCommand $pythonArgs"
        exit 0
    }
    if ((Test-Path -LiteralPath $venvPython) -and -not (Test-Python $venvPython)) {
        throw 'Existing .venv is not Python 3.12 x64. Rename that folder and rerun setup.bat.'
    }
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & $pythonCommand @pythonArgs -m venv (Join-Path $projectRoot '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Creating .venv failed.' }
    }
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Updating pip failed.' }
    & $venvPython -m pip install -r (Join-Path $projectRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check your network and rerun setup.bat.' }
    & $venvPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency validation failed.' }
    & $venvPython -c 'import tkinter,torch,cv2,ddddocr,zhconv,pyautogui; print(torch.__version__); print(torch.cuda.is_available())'
    if ($LASTEXITCODE -ne 0) { throw 'Import validation failed.' }
    Write-Output 'Setup complete. Open the game, then double-click start.bat.'
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
