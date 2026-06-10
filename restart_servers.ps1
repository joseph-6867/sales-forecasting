$proj = 'C:\Users\josep\Downloads\sales_forecasting_platform1\final project\sales_platform11'
$py = Join-Path $proj '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    Write-Error "Python executable not found: $py"
    exit 1
}

$old = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn|streamlit' }
if ($old) {
    $old | ForEach-Object {
        Write-Host "Stopping process $($_.ProcessId): $($_.CommandLine)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 1

Write-Host 'Launching backend...'
Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoExit','-Command', "Set-Location '$proj'; & '$py' -m uvicorn backend.server:app --reload --port 8000"
Start-Sleep -Milliseconds 500
Write-Host 'Launching frontend...'
Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoExit','-Command', "Set-Location '$proj'; & '$py' -m streamlit run app.py"
Start-Sleep -Seconds 2
Write-Host 'Restart script completed. Backend and frontend should now be running in separate windows.'
