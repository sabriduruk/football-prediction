@echo off
chcp 65001 >nul
title Futbol Tahmin - Kurulum
color 0A

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║          FUTBOL TAHMIN SISTEMI - WINDOWS KURULUM             ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: Python kontrolu
echo [1/5] Python kontrol ediliyor...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [HATA] Python bulunamadi!
    echo.
    echo Python 3.11 veya 3.12 indirip kurun:
    echo https://www.python.org/downloads/
    echo.
    echo ONEMLI: Kurulum sirasinda "Add Python to PATH" secenegini isaretleyin!
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYVER=%%i
echo        Python %PYVER% bulundu

:: Klasor kontrolu
echo.
echo [2/5] Proje klasoru hazirlaniyor...
cd /d "%~dp0"
echo        Klasor: %cd%

:: Virtual environment
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

:: Dependencies kurulumu
echo.
echo [4/5] Kutuphaneler kuruluyor (bu biraz zaman alabilir)...
echo.
call venv\Scripts\activate.bat
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [HATA] Kutuphane kurulumu basarisiz!
    echo Lütfen internet baglantinizi kontrol edin.
    pause
    exit /b 1
)
echo.
echo        Tum kutuphaneler kuruldu

:: Masaustu kisayolu
echo.
echo [5/5] Masaustu kisayolu olusturuluyor...
set SCRIPT_PATH=%~dp0run_futbol.bat
set SHORTCUT_PATH=%USERPROFILE%\Desktop\Futbol Tahmin.lnk

:: PowerShell ile kisayol olustur
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = '%SCRIPT_PATH%'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'Futbol Mac Tahmin Sistemi'; $s.Save()"
echo        Masaustune kisayol eklendi

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    KURULUM TAMAMLANDI!                       ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║  Uygulamayi baslatmak icin:                                  ║
echo ║    - Masaustundeki "Futbol Tahmin" kisayoluna tiklayin       ║
echo ║    - VEYA bu klasordeki "run_futbol.bat" dosyasini calistirin║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
pause
