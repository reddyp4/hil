# run.ps1 — compile + simulate buck_plant_tb, optionally open GTKWave.
#
# Usage (from anywhere):
#   .\run.ps1              # compile, simulate, open GTKWave
#   .\run.ps1 -NoView      # compile + simulate only (no GUI)
#   .\run.ps1 -Clean       # delete generated artifacts and exit

param(
    [switch]$NoView,
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$Vvp  = 'buck_plant_tb.vvp'
$Vcd  = 'buck_plant_tb.vcd'
$Srcs = @('buck_plant.v', 'buck_plant_tb.v')

if ($Clean) {
    Remove-Item -Force -ErrorAction SilentlyContinue $Vvp, $Vcd
    Write-Host "Cleaned $Vvp and $Vcd."
    exit 0
}

# Tool checks
foreach ($tool in @('iverilog', 'vvp')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Error "$tool not found on PATH. Install Icarus Verilog (e.g. 'winget install Icarus.IcarusVerilog') and open a new shell."
    }
}

# Compile
Write-Host "[1/3] Compiling..." -ForegroundColor Cyan
& iverilog -g2012 -o $Vvp @Srcs
if ($LASTEXITCODE -ne 0) { Write-Error "iverilog failed (exit $LASTEXITCODE)." }

# Simulate
Write-Host "[2/3] Simulating..." -ForegroundColor Cyan
& vvp $Vvp
if ($LASTEXITCODE -ne 0) { Write-Error "vvp failed (exit $LASTEXITCODE)." }

# View
if ($NoView) {
    Write-Host "[3/3] Skipping GTKWave (-NoView). VCD written to $Vcd." -ForegroundColor Cyan
    exit 0
}

if (-not (Get-Command gtkwave -ErrorAction SilentlyContinue)) {
    Write-Warning "gtkwave not on PATH — skipping viewer. VCD written to $Vcd."
    exit 0
}

Write-Host "[3/3] Launching GTKWave..." -ForegroundColor Cyan
Start-Process gtkwave -ArgumentList $Vcd
