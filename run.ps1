#Requires -Version 5.1
# run.ps1 - starts console-error-scanner from source.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Please run .\bootstrap.ps1 first." -ForegroundColor Red
    exit 1
}

# ErrorActionPreference vor dem nativen Aufruf lockern - sonst verpackt PS 5.1
# jede stderr-Zeile in einen ErrorRecord und bricht ab, bevor der Reset laeuft.
$ErrorActionPreference = "Continue"

# try/finally: der Terminal-Reset MUSS auch dann laufen, wenn Ctrl+C das Skript
# abbricht - PowerShell fuehrt finally auch bei Unterbrechung aus.
$code = 0
try {
    & ".venv\Scripts\python.exe" -m console_error_scanner @args
    $code = $LASTEXITCODE
} finally {
    # Terminal nach dem App-Ende IMMER wiederherstellen - egal wie Python endete
    # (sauberes Quit, Ctrl+C, harter oder nativer Crash). Textuals Teardown und
    # der Python-finally-Block greifen bei einem harten Absturz nicht; dieser
    # Shell-Reset laeuft, wenn Python komplett weg ist und PowerShell die Konsole
    # wieder besitzt. Sonst bleibt das Maus-Tracking an und die Shell ist
    # "zerschossen" (jede Mausbewegung kippt Steuerzeichen ins Eingabefeld).
    $esc = [char]27
    [Console]::Write("$esc[?1000l$esc[?1002l$esc[?1003l$esc[?1006l$esc[?1015l$esc[?2004l$esc[?25h$esc[?1049l")
}

exit $code
