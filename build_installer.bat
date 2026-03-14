@echo off
setlocal
chcp 65001 >nul

echo ==============================================
echo Сборка установщика Inno Setup

echo ==============================================

if not exist "dist\microlan\microlan.exe" (
  echo [ERROR] Не найдена portable-сборка dist\microlan\microlan.exe
  echo Сначала выполните build_windows.bat
  exit /b 1
)

set "ISS_FILE=installer\microlan_installer.iss"
if not exist "%ISS_FILE%" (
  echo [ERROR] Не найден скрипт установщика %ISS_FILE%
  exit /b 1
)

set "ISCC_PATH="
if not "%INNO_SETUP_COMPILER%"=="" (
  set "ISCC_PATH=%INNO_SETUP_COMPILER%"
) else (
  if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
  if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if "%ISCC_PATH%"=="" (
  echo [ERROR] Не найден ISCC.exe ^(Inno Setup Compiler^).
  echo Установите Inno Setup 6: https://jrsoftware.org/isdl.php
  echo Затем:
  echo   1^) добавьте ISCC.exe в PATH, или
  echo   2^) задайте переменную окружения INNO_SETUP_COMPILER, например:
  echo      set INNO_SETUP_COMPILER="C:\Program Files ^(x86^)\Inno Setup 6\ISCC.exe"
  exit /b 1
)

echo [INFO] Компиляция installer\microlan_installer.iss ...
"%ISCC_PATH%" "%ISS_FILE%"
if errorlevel 1 (
  echo [ERROR] Сборка установщика завершилась с ошибкой.
  exit /b 1
)

echo [OK] Установщик успешно собран.
echo Ищите файл setup в папке: dist\
endlocal
