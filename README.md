# Futbol Tahmin

FiveThirtyEight SPI metodolojisine dayalı profesyonel futbol maç tahmin uygulaması.

## Özellikler

- **%100 Veri Bazlı Tahmin** - Tüm tahminler gerçek maç verilerine dayanır
- **12 Lig Desteği** - Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Süper Lig ve daha fazlası
- **Detaylı Analiz** - 1X2, gol olasılıkları, güven skoru
- **Modern Arayüz** - CustomTkinter ile modern GUI


## Algoritma

```
%100 VERİ BAZLI SİSTEM
├── Sezon Performansı (%40)
│   ├── W-D-L Kaydı (%25)
│   └── Gol Farkı (%15)
├── Son Maç Formu (%25)
│   ├── Son 5-10 Maç (%15)
│   └── Form Trendi (%10)
├── Ev/Deplasman (%15)
├── Kafa Kafaya (%10)
└── Lig Faktörleri (%10)

Hesaplama Araçları: Poisson + Dixon-Coles + Monte Carlo
```

## Desteklenen Ligler

- İngiltere Premier League
- İspanya La Liga
- İtalya Serie A
- Almanya Bundesliga
- Fransa Ligue 1
- Türkiye Süper Lig
- Portekiz Primeira Liga
- Belçika Pro League
- Suudi Arabistan Pro League
- UEFA Şampiyonlar Ligi
- UEFA Avrupa Ligi
- UEFA Konferans Ligi

## Lisans

MIT License
