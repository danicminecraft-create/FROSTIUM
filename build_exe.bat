@echo off
chcp 65001 >nul
echo === Сборка Frostium.exe ===
python -m pip install -r requirements.txt || goto :err
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Frostium ^
  --icon assets\icon.ico --add-data "assets;assets" frostium.py || goto :err

echo.
echo Готово! Один файл: dist\Frostium.exe
echo Его можно копировать и отправлять отдельно.
pause
exit /b 0
:err
echo Ошибка сборки.
pause
exit /b 1
