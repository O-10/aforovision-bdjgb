# AforoVision: levanta el motor, la vista pública y un túnel HTTPS compartible.
$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$data = Join-Path $root "data"
New-Item -ItemType Directory -Force -Path $data | Out-Null
$archivoUrl = Join-Path $data "enlace_publico.txt"

function Puesto-En-Escucha([int]$puerto) {
    return [bool](Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue)
}

if (-not (Puesto-En-Escucha 8000)) {
    Start-Process py -ArgumentList "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8000" -WindowStyle Hidden
    Write-Host "Motor de vision iniciado en 8000"
}
if (-not (Puesto-En-Escucha 8001)) {
    Start-Process py -ArgumentList "-m", "uvicorn", "public_server:app", "--host", "127.0.0.1", "--port", "8001" -WindowStyle Hidden
    Write-Host "Vista publica iniciada en 8001"
}
Start-Sleep -Seconds 4

$cloudflared = Join-Path $root "herramientas\cloudflared.exe"
$proceso = Get-Process cloudflared -ErrorAction SilentlyContinue | Select-Object -First 1
$url = $null

if ($proceso -and (Test-Path $archivoUrl)) {
    $url = (Get-Content $archivoUrl -Raw).Trim()
}

if (-not $proceso) {
    $salida = Join-Path $data "tunel.out"
    $errores = Join-Path $data "tunel.log"
    $proceso = Start-Process -FilePath $cloudflared `
        -ArgumentList "tunnel", "--url", "http://127.0.0.1:8001", "--no-autoupdate" `
        -RedirectStandardOutput $salida -RedirectStandardError $errores -PassThru -WindowStyle Hidden
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        $todo = (Get-Content $errores -Raw) + (Get-Content $salida -Raw)
        if ($todo -match "https://[a-z0-9-]+\.trycloudflare\.com") {
            $url = $matches[0]
            Set-Content -Path $archivoUrl -Value $url -Encoding UTF8
            break
        }
    }
}

Write-Host ""
if ($url) {
    Set-Clipboard -Value $url
    Write-Host "ENLACE PARA COMPARTIR:" -ForegroundColor Green
    Write-Host $url -ForegroundColor Cyan
    Write-Host "(copiado al portapapeles; tambien esta en data\enlace_publico.txt)"
} else {
    Write-Host "No se pudo leer el enlace. Revise data\tunel.log" -ForegroundColor Red
}
Write-Host "El enlace cambia cada vez que se reinicia el tunel."
Write-Host "Para detener el tunel: Stop-Process -Id $($proceso.Id)"
