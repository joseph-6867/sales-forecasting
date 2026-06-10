$proj = "C:\Users\josep\Downloads\sales_forecasting_platform1\final project\sales_platform11"
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -and ($_.CommandLine -match "uvicorn|streamlit") } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1
$backendCmd = 'if (Test-Path ".venv\Scripts\python.exe") { & ".venv\Scripts\python.exe" -m uvicorn backend.server:app --reload --port 8000 } else { python -m uvicorn backend.server:app --reload --port 8000 }'
$frontendCmd = 'if (Test-Path ".venv\Scripts\python.exe") { & ".venv\Scripts\python.exe" -m streamlit run app.py } else { streamlit run app.py }'
Start-Process powershell -ArgumentList '-NoExit','-Command',$backendCmd -WorkingDirectory $proj
Start-Process powershell -ArgumentList '-NoExit','-Command',$frontendCmd -WorkingDirectory $proj
