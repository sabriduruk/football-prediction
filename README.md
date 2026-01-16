# Futbol Tahmin Sistemi

Hibrit algoritma ile futbol mac tahmin uygulamasi.

## Windows Kurulum

1. **Python 3.11 veya 3.12** indirip kurun: https://www.python.org/downloads/
   - ONEMLI: "Add Python to PATH" secenegini isaretleyin!

2. Bu repoyu indirin (Code > Download ZIP) ve cikartin

3. `install_windows.bat` dosyasina cift tiklayin

4. Kurulum bitince masaustundeki **Futbol Tahmin** kisayoluna tiklayin

## macOS Kurulum

```bash
cd futbol
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Ozellikler

- 12 lig destegi (Premier League, La Liga, Serie A, Bundesliga, Super Lig vs.)
- Poisson + Dixon-Coles + Monte Carlo hibrit analizi
- Modern arayuz (CustomTkinter)
