@echo off
setlocal

set ENTRY=app/main.py
set NAME=microlan
set ICON=assets\icon.ico

set CMD=pyinstaller --noconsole --onefile --name %NAME% %ENTRY%
if exist "%ICON%" (
  set CMD=%CMD% --icon %ICON%
)

echo Running: %CMD%
%CMD%

endlocal
