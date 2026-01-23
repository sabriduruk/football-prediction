@echo off
chcp 65001 >nul
title Futbol Tahmin - Windows Build

echo ========================================
echo    FUTBOL TAHMIN - WINDOWS BUILD
echo ========================================
echo.

:: Python kontrolü
python --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python bulunamadi!
    echo Python 3.9+ yukleyin: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/5] Sanal ortam olusturuluyor...
python -m venv venv
call venv\Scripts\activate.bat

echo [2/5] Bagimliliklar yukleniyor...
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo [3/5] Executable olusturuluyor...
pyinstaller --noconfirm --onedir --windowed ^
    --name "FutbolTahmin" ^
    --icon "icon.ico" ^
    --add-data "requirements.txt;." ^
    --hidden-import "customtkinter" ^
    --hidden-import "PIL" ^
    --hidden-import "PIL._tkinter_finder" ^
    --collect-all "customtkinter" ^
    app.py

echo [4/5] Dosyalar kopyalaniyor...
if not exist "dist\FutbolTahmin" mkdir "dist\FutbolTahmin"
copy /Y data_fetcher.py "dist\FutbolTahmin\" >nul
copy /Y predictor.py "dist\FutbolTahmin\" >nul

echo [5/5] Temizlik yapiliyor...
rmdir /s /q build 2>nul
del /f /q *.spec 2>nul

echo.
echo ========================================
echo    BUILD TAMAMLANDI!
echo ========================================
echo.
echo Executable: dist\FutbolTahmin\FutbolTahmin.exe
echo.
echo Simdi Inno Setup ile installer olusturabilirsiniz.
echo.
pause
