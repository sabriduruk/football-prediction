"""
Futbol Tahmin Sistemi - Örnek Kullanım
======================================
Veri çekme ve tahminleme modüllerinin birlikte kullanımı.

GitHub: https://github.com/probberechts/soccerdata
"""

from data_fetcher import fetch_all_data, SUPPORTED_LEAGUES, clear_cache
from predictor import run_predictions, MatchPredictor, print_prediction
import pandas as pd


def main():
    """Ana fonksiyon - Tam sistem örneği."""
    
    print("=" * 70)
    print("🏟️  FUTBOL TAHMİN SİSTEMİ")
    print("=" * 70)
    print("📊 Desteklenen Ligler:")
    for league in SUPPORTED_LEAGUES:
        print(f"   • {league}")
    print("=" * 70)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 1. VERİ ÇEKME (Optimize edilmiş - cache aktif)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    print("\n📥 ADIM 1: Veri Çekme")
    print("-" * 50)
    
    # Premier League için bu haftaki maçlar
    matches_df = fetch_all_data(
        leagues=['ENG-Premier League'],
        days_ahead=7,
        last_n_matches=10,
        verbose=True
    )
    
    if matches_df.empty:
        print("⚠️ Maç verisi bulunamadı!")
        return
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 2. TAHMİN YAPMA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    print("\n🔮 ADIM 2: Tahmin Yapma")
    print("-" * 50)
    
    predictions_df = run_predictions(matches_df, verbose=True)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 3. SONUÇLARI KAYDET
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    print("\n💾 ADIM 3: Sonuçları Kaydet")
    print("-" * 50)
    
    # Maç verilerini kaydet
    matches_df.to_csv('matches_df.csv', index=False)
    print("✅ matches_df.csv kaydedildi")
    
    # Tahminleri kaydet
    predictions_df.to_csv('predictions.csv', index=False)
    print("✅ predictions.csv kaydedildi")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 4. EN İYİ BAHİS FIRSATLARI
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    print("\n🎯 ADIM 4: En İyi Bahis Fırsatları")
    print("-" * 50)
    
    # Yüksek güvenli tahminler
    high_confidence = predictions_df[predictions_df['confidence'] >= 60]
    if not high_confidence.empty:
        print("\n🟢 Yüksek Güvenli Tahminler (>%60):")
        for _, row in high_confidence.iterrows():
            winner = row['home_team'] if row['home_win_%'] > row['away_win_%'] else row['away_team']
            if row['draw_%'] > max(row['home_win_%'], row['away_win_%']):
                winner = "Beraberlik"
            print(f"   • {row['home_team']} vs {row['away_team']}")
            print(f"     Favori: {winner} | Güven: %{row['confidence']}")
            print(f"     Olası Skor: {row['likely_score']}")
    
    # Gol festivali maçları (4+ gol yüksek olasılık)
    goal_fest = predictions_df[predictions_df['over_3.5_%'] >= 50]
    if not goal_fest.empty:
        print("\n⚽ Gol Festivali Beklenen Maçlar (4+ Gol >%50):")
        for _, row in goal_fest.iterrows():
            print(f"   • {row['home_team']} vs {row['away_team']}: %{row['over_3.5_%']}")
    
    print("\n" + "=" * 70)
    print("✅ Analiz tamamlandı!")
    print("=" * 70)


def quick_predict(home_team: str, away_team: str, verbose: bool = True):
    """
    Hızlı tek maç tahmini (manuel veri girişi ile).
    
    Örnek kullanım:
        quick_predict("Arsenal", "Chelsea")
    """
    # Örnek veri oluştur
    match_data = {
        'home_team': home_team,
        'away_team': away_team,
        'home_last5_avg_goals': 2.0,
        'home_last5_avg_conceded': 0.8,
        'home_last5_avg_xg': 2.2,
        'home_last5_avg_xg_against': 0.9,
        'home_last5_form_points': 12,
        'away_last5_avg_goals': 1.5,
        'away_last5_avg_conceded': 1.2,
        'away_last5_avg_xg': 1.4,
        'away_last5_avg_xg_against': 1.3,
        'away_last5_form_points': 8,
        'home_season_red': 2,
        'home_season_pk_won': 5,
        'away_season_red': 3,
        'away_season_pk_won': 3,
    }
    
    predictor = MatchPredictor()
    prediction = predictor.predict_match(pd.Series(match_data))
    
    if verbose:
        print_prediction(prediction)
    
    return prediction


if __name__ == "__main__":
    main()
