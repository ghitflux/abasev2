@echo off
setlocal

set "ROOT=%~dp0"

start "ABASE v2 Backend" powershell -NoExit -Command "Set-Location -LiteralPath '%ROOT%backend'; $env:DEBUG='True'; $env:DJANGO_SETTINGS_MODULE='config.settings.development'; $env:DATABASE_NAME='abase'; $env:DATABASE_USER='root'; $env:DATABASE_PASSWORD=''; $env:DATABASE_HOST='127.0.0.1'; $env:DATABASE_PORT='3306'; .\\.venv\\Scripts\\python.exe manage.py runserver 127.0.0.1:8001"
start "ABASE v2 Frontend" powershell -NoExit -Command "Set-Location -LiteralPath '%ROOT%'; pnpm dev"
