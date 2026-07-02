@echo off
rem 釣りマップ起動: サーバーが無ければ起動してブラウザで開く
netstat -ano | findstr /r ":8765 .*LISTENING" >nul
if errorlevel 1 (
  start "fishing-map-server" /min cmd /c python -m http.server 8765 --directory "C:\Users\kahoo\Downloads\fishing-map\docs"
  timeout /t 1 /nobreak >nul
)
start "" "http://localhost:8765/"
