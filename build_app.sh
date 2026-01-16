#!/bin/bash
cd /Users/sabri/Desktop/futbol
source venv/bin/activate

echo "=== TEMIZLENIYOR ==="
rm -rf build dist *.spec
rm -rf "/Users/sabri/Desktop/Futbol Tahmin.app" 2>/dev/null
rm -rf "/Users/sabri/Desktop/FutbolTahmin.app" 2>/dev/null

echo "=== PAKETLENIYOR ==="
pyinstaller \
  --onedir \
  --windowed \
  --name "FutbolTahmin" \
  --osx-bundle-identifier "com.futbol.tahmin" \
  --noconfirm \
  app.py

echo ""
echo "=== SONUC ==="
if [ -d "dist/FutbolTahmin.app" ]; then
    echo "Basarili!"
    ls -la dist/
    
    # Info.plist'e ayar ekle (tekrar baslatmayi engelle)
    PLIST="dist/FutbolTahmin.app/Contents/Info.plist"
    /usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string 10.13" "$PLIST" 2>/dev/null
    /usr/libexec/PlistBuddy -c "Add :NSSupportsAutomaticTermination bool false" "$PLIST" 2>/dev/null
    /usr/libexec/PlistBuddy -c "Add :NSSupportsSuddenTermination bool false" "$PLIST" 2>/dev/null
    
    # Desktop'a kopyala
    cp -R "dist/FutbolTahmin.app" "/Users/sabri/Desktop/"
    echo ""
    echo "=== DESKTOP'A KOPYALANDI ==="
    ls -la "/Users/sabri/Desktop/FutbolTahmin.app"
else
    echo "HATA: Build basarisiz!"
    ls -la dist/ 2>/dev/null
fi
