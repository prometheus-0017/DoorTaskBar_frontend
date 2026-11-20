@echo off
echo %taskbar_http_port%
curl -X POST http://localhost:%taskbar_http_port%/expand
pause