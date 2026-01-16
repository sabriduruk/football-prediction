@echo off
title Futbol Tahmin - Kurulum
color 0A

echo.
echo ========================================================
echo         FUTBOL TAHMIN SISTEMI - WINDOWS KURULUM
echo ========================================================
echo.

echo [1/5] Python kontrol ediliyor...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [HATA] Python bulunamadi!
    echo Python 3.11 veya 3.12 indirip kurun:
    echo https://www.python.org/downloads/
    echo ONEMLI: Add Python to PATH secenegini isaretleyin!
    pause
    exit /b 1
)
echo        Python bulundu

echo.
echo [2/5] Proje klasoru hazirlaniyor...
cd /d "%~dp0"
echo        Klasor: %cd%

echo.
echo [3/5] Virtual environment olusturuluyor...
if exist "venv" (
    echo        Mevcut venv siliniyor...
    rmdir /s /q venv
)
python -m venv venv
if %errorlevel% neq 0 (
    echo [HATA] Virtual environment olusturulamadi!
    pause
    exit /b 1
)
echo        venv olusturuldu

echo.
echo [4/5] Kutuphaneler kuruluyor...
echo        Bu biraz zaman alabilir...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [HATA] Kutuphane kurulumu basarisiz!
    pause
    exit /b 1
)
echo        Kutuphaneler kuruldu

echo.
echo [5/5] Masaustu kisayolu olusturuluyor...
set SCRIPT="%~dp0run_futbol.bat"
set SHORTCUT="%USERPROFILE%\Desktop\Futbol Tahmin.lnk"
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%USERPROFILE%\Desktop\Futbol Tahmin.lnk'); $s.TargetPath = '%~dp0run_futbol.bat'; $s.WorkingDirectory = '%~dp0'; $s.Save()"
echo        Kisayol olusturuldu

echo.
echo ========================================================
echo              KURULUM TAMAMLANDI!
echo ========================================================
echo.
echo Masaustundeki "Futbol Tahmin" kisayoluna tiklayin
echo.
pause
