@echo off
setlocal
py -m pip install --upgrade pip
py -m pip install -r requirements.txt pyinstaller
py -m PyInstaller --noconfirm --clean --windowed --onefile --name salehiMaps map_viewer.py
echo.
echo Executable created at dist\salehiMaps.exe
pause
