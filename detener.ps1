# AforoVision: detiene el motor, la vista pública y el túnel para liberar la cámara.
$ErrorActionPreference = "SilentlyContinue"

function Detener-Puerto([int]$puerto, [string]$nombre) {
    $conns = Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue
    $detenidos = 0
    foreach ($c in $conns) {
        $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -match "python|uvicorn") {
            Stop-Process -Id $proc.Id -Force
            Write-Host "$nombre detenido (PID $($proc.Id))"
            $detenidos++
        }
    }
    if ($detenidos -eq 0) { Write-Host "${nombre}: no estaba activo" }
}

Detener-Puerto 8000 "Motor de visión"
Detener-Puerto 8001 "Vista pública"
Get-Process cloudflared -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.Id -Force
    Write-Host "Túnel público detenido (PID $($_.Id))"
}

Start-Sleep -Seconds 2
$activos = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in 8000, 8001 }
if ($activos) {
    Write-Host "Advertencia: aún hay procesos en 8000/8001" -ForegroundColor Red
} else {
    Write-Host "Listo: servidores apagados. La cámara debería liberarse en unos segundos." -ForegroundColor Green
}
