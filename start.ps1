cd D:\个人项目\跑得快\client
npm run build
Copy-Item public\sw.js dist\sw.js -Force
Start-Process "D:\python\python.exe" "-m uvicorn server.main:app --host 0.0.0.0 --port 8000"
Start-Sleep 2
Start-Process "D:\ngrok\ngrok.exe" "http 8000 --log=stdout"
Start-Sleep 5
Write-Host "`nOpen http://127.0.0.1:4040 in browser for public URL"
Read-Host "Press Enter to exit"