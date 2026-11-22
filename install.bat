@echo off
chcp 65001 > nul
echo Устанавливаю нужные библиотеки...
python -m pip install --upgrade pip
python -m pip install opencv-python mss numpy python-chess PyQt6
echo.
echo Готово! Теперь можно запускать start.bat
pause