# Futbol Tahmin - Windows Kurulum Rehberi

## Yöntem 1: Windows Bilgisayarda Build (Önerilen)

### Gereksinimler
1. Windows 10 veya 11
2. Python 3.9+ ([İndir](https://www.python.org/downloads/))
3. Inno Setup ([İndir](https://jrsoftware.org/isdl.php)) - Kurulum dosyası oluşturmak için

### Adımlar

1. **Tüm proje dosyalarını Windows'a kopyala**
   ```
   futbol/
   ├── app.py
   ├── data_fetcher.py
   ├── predictor.py
   ├── requirements.txt
   └── windows_build/
       ├── build_windows.bat
       └── installer_script.iss
   ```

2. **Executable oluştur**
   ```batch
   cd futbol\windows_build
   build_windows.bat
   ```

3. **Installer oluştur (opsiyonel)**
   - Inno Setup'ı aç
   - `installer_script.iss` dosyasını aç
   - Compile (Ctrl+F9)
   - `installer_output/FutbolTahmin_Setup.exe` oluşacak

### Sonuç
- `dist/FutbolTahmin/FutbolTahmin.exe` - Standalone çalıştırılabilir
- `installer_output/FutbolTahmin_Setup.exe` - Kurulum dosyası

---

## Yöntem 2: GitHub Actions ile Otomatik Build

Eğer Windows bilgisayarın yoksa, GitHub Actions kullanarak otomatik build yapabilirsin.

1. Projeyi GitHub'a yükle
2. `.github/workflows/build-windows.yml` dosyasını ekle
3. Her push'ta otomatik Windows build oluşur

---

## Sorun Giderme

### "Python bulunamadı" hatası
- Python'u PATH'e eklediğinizden emin olun
- Kurulum sırasında "Add Python to PATH" seçeneğini işaretleyin

### "customtkinter bulunamadı" hatası
```batch
pip install customtkinter
```

### Antivirüs uyarısı
- PyInstaller ile oluşturulan .exe dosyaları bazen yanlış pozitif verir
- Antivirüs programınızda istisna ekleyin

---

## Dosya Boyutları (Tahmini)
- Standalone exe: ~150-200 MB (tüm Python dahil)
- Installer: ~50-80 MB (sıkıştırılmış)
