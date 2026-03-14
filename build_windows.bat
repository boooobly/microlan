@echo off
setlocal
chcp 65001 >nul

echo ==============================================
echo Сборка LAN голосовые звонки для Windows (onedir)
echo ==============================================

if exist "build" (
  echo [INFO] Удаление папки build...
  rmdir /s /q "build"
)

if exist "dist\microlan" (
  echo [INFO] Удаление старой сборки dist\microlan...
  rmdir /s /q "dist\microlan"
)

if not exist "microlan.spec" (
  echo [ERROR] Не найден файл microlan.spec
  echo Проверьте, что скрипт запускается из корня проекта.
  exit /b 1
)

echo [INFO] Запуск PyInstaller...
pyinstaller microlan.spec --noconfirm
if errorlevel 1 (
  echo [ERROR] Сборка завершилась с ошибкой.
  exit /b 1
)

echo.
echo [OK] Сборка успешно завершена.
echo Готовая portable-сборка находится в: dist\microlan\
if exist "dist\microlan\microlan.exe" (
  echo Основной файл запуска: dist\microlan\microlan.exe
)
if not exist "assets\icon.ico" (
  echo [INFO] icon.ico не найден, сборка выполнена без пользовательской иконки.
)

echo.
echo Для сборки установщика используйте: build_installer.bat
endlocal
