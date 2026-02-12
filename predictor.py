"""
Futbol Maç Tahmin Modülü - FiveThirtyEight SPI Modeli
=====================================================
FiveThirtyEight'in Soccer Power Index (SPI) sistemine dayalı tahmin modeli.

Kaynak: https://fivethirtyeight.com/methodology/how-our-club-soccer-predictions-work/

Algoritma (FiveThirtyEight Metodolojisi):
1. SPI Rating: Her takımın Hücum ve Savunma rating'i
   - Hücum = Ortalama bir takıma karşı beklenen gol
   - Savunma = Ortalama bir takıma karşı beklenen yenilen gol
   
2. Performans Metrikleri (3 metrik ortalaması):
   - Düzeltilmiş Goller (kırmızı kart, geç goller için düzeltme)
   - Şut bazlı xG (şut kalitesi)
   - Form bazlı performans
   
3. Maç Tahmini (3 adım):
   - Adım 1: Her takımın beklenen golünü hesapla
   - Adım 2: Poisson dağılımı ile gol olasılıkları
   - Adım 3: Skor matrisi oluştur, beraberlik düzeltmesi uygula
   
4. Monte Carlo: 10.000 simülasyon ile belirsizlik modelleme

5. Lig Gücü: Her ligin kendine özel güç faktörü
"""

import numpy as np
import pandas as pd
from scipy.stats import poisson
from typing import Dict, Tuple, List, Any
from dataclasses import dataclass


@dataclass
class SPIRating:
    """
    FiveThirtyEight SPI (Soccer Power Index) Rating.
    
    Her takımın iki temel rating'i var:
    - offensive: Ortalama takıma karşı beklenen gol
    - defensive: Ortalama takıma karşı beklenen yenilen gol
    """
    offensive: float      # Hücum rating (beklenen gol)
    defensive: float      # Savunma rating (beklenen yenilen gol)
    spi: float            # Genel SPI puanı (0-100)
    form: float           # Son maç formu (0-1)
    home_offensive: float = 0.0  # Evdeki hücum
    home_defensive: float = 0.0  # Evdeki savunma
    away_offensive: float = 0.0  # Deplasmandaki hücum
    away_defensive: float = 0.0  # Deplasmandaki savunma


@dataclass 
class TeamRating:
    """Takım güç puanı (geriye uyumluluk için)."""
    attack: float      # Hücum gücü
    defense: float     # Savunma gücü
    form: float        # Son maç formu (0-1)
    risk_factor: float # Risk faktörü (kart, penaltı)
    h2h_factor: float = 0.0
    form_trend: float = 0.0
    elo_rating: float = 1500.0
    xg_quality: float = 1.0
    squad_strength: float = 1.0


@dataclass
class FactorContribution:
    """
    FiveThirtyEight Metodolojisine Dayalı Veri Faktörleri.
    
    =====================================================
    %100 VERİ BAZLI SİSTEM
    =====================================================
    
    Tüm tahminler gerçek maç verilerine dayanır.
    Poisson ve Monte Carlo veri DEĞİL, hesaplama aracıdır.
    
    SEZON PERFORMANSI (%40)
    - season_record: %25 (W-D-L kaydı, puan)
    - goal_difference: %15 (atılan-yenilen gol farkı)
    
    SON MAÇ FORMU (%25)
    - recent_form: %15 (son 5-10 maç sonuçları)
    - form_trend: %10 (yükseliş/düşüş trendi)
    
    EV/DEPLASMAN (%15)
    - home_performance: %8 (evdeki performans)
    - away_performance: %7 (deplasmandaki performans)
    
    KAFA KAFAYA (%10)
    - h2h_record: %6 (geçmiş karşılaşma sonuçları)
    - h2h_goals: %4 (geçmiş karşılaşma golleri)
    
    LİG FAKTÖRLERİ (%10)
    - league_strength: %6 (lig kalitesi - PL > La Liga > ...)
    - home_advantage: %4 (lige özel ev avantajı)
    
    =====================================================
    HESAPLAMA YÖNTEMLERİ (Ağırlık değil, araç)
    =====================================================
    - Poisson Dağılımı: Verileri gol olasılığına çevirir
    - Dixon-Coles: Beraberlik olasılığını düzeltir (+%9)
    - Monte Carlo: 10.000 simülasyon ile belirsizlik ölçer
    =====================================================
    """
    # Sezon Performansı (%40)
    season_record: float = 25.0
    goal_difference: float = 15.0
    
    # Son Maç Formu (%25)
    recent_form: float = 15.0
    form_trend: float = 10.0
    
    # Ev/Deplasman (%15)
    home_performance: float = 8.0
    away_performance: float = 7.0
    
    # Kafa Kafaya (%10)
    h2h_record: float = 6.0
    h2h_goals: float = 4.0
    
    # Lig Faktörleri (%10)
    league_strength: float = 6.0
    home_advantage: float = 4.0


@dataclass
class MatchPrediction:
    """Maç tahmin sonucu."""
    home_team: str
    away_team: str
    
    # Beklenen goller
    home_expected_goals: float
    away_expected_goals: float
    
    # 1X2 Olasılıkları
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    
    # Gol olasılıkları
    under_3_5_prob: float  # 0-3 gol
    over_3_5_prob: float   # 4+ gol
    
    # En olası skor
    most_likely_score: Tuple[int, int]
    most_likely_score_prob: float
    
    # Risk faktörleri
    home_risk_factor: float
    away_risk_factor: float
    
    # Güven skoru (0-100)
    confidence: float
    
    # Faktör katkıları (opsiyonel)
    factor_contributions: FactorContribution = None


class MatchPredictor:
    """
    FiveThirtyEight SPI Tabanlı Maç Tahmin Motoru
    =============================================
    
    FiveThirtyEight metodolojisine dayalı profesyonel tahmin sistemi.
    
    Kaynak: fivethirtyeight.com/methodology/how-our-club-soccer-predictions-work
    
    Temel Prensipler:
    1. SPI Rating: Hücum + Savunma rating'leri
    2. Poisson Dağılımı: Gol olasılıkları
    3. Beraberlik Düzeltmesi: ~9% diagonal inflation
    4. Monte Carlo: 10.000 simülasyon
    5. Lig Gücü: Farklı ligler için düzeltme
    """
    
    # =====================================================
    # FiveThirtyEight Sabitleri
    # =====================================================
    
    # Lig ortalamaları (global ortalama: 2.7 gol/maç)
    LEAGUE_AVG_GOALS = 2.7
    AVG_GOALS_PER_TEAM = 1.35  # 2.7 / 2
    
    # Ev avantajı (FiveThirtyEight: ~%12 gol artışı)
    BASE_HOME_ADVANTAGE = 1.12
    
    # Dixon-Coles düzeltmesi (düşük skor korelasyonu)
    DIXON_COLES_RHO = 0.03
    
    # Beraberlik düzeltmesi (FiveThirtyEight: ~%9, biz %12 kullanıyoruz)
    # Gerçek dünya beraberlik oranı: %25-27
    DRAW_INFLATION = 0.12
    
    # Monte Carlo simülasyon sayısı (FiveThirtyEight: 20.000)
    MONTE_CARLO_SIMS = 10000
    
    # xG vs Gerçek Gol ağırlıkları (rating hesaplamasında)
    XG_WEIGHT = 0.6
    ACTUAL_GOALS_WEIGHT = 0.4
    
    # SPI Ağırlıkları (tahmin hesaplamasında)
    SPI_WEIGHT = 0.50          # %50 SPI rating
    FORM_WEIGHT = 0.25         # %25 form & performans
    CONTEXT_WEIGHT = 0.15      # %15 maç bağlamı (H2H, lig)
    CALCULATION_WEIGHT = 0.10  # %10 hesaplama modeli
    
    # Lig bazlı ev avantajları (istatistiksel veriler)
    LEAGUE_HOME_ADVANTAGE = {
        'TUR-Super Lig': 1.18,        # Türkiye'de ev avantajı yüksek
        'KSA-Pro League': 1.15,       # Suudi'de de yüksek
        'ENG-Premier League': 1.10,   # Premier League'de düşük
        'ESP-La Liga': 1.12,
        'GER-Bundesliga': 1.11,
        'ITA-Serie A': 1.13,
        'FRA-Ligue 1': 1.11,
        'POR-Primeira Liga': 1.14,
        'BEL-Pro League': 1.12,
        'INT-Champions League': 1.08,  # UEFA'da düşük
        'INT-Europa League': 1.10,
        'INT-Conference League': 1.12,
    }
    
    # Lig bazlı temel Elo puanları (lig gücüne göre)
    # Daha güçlü ligler = daha yüksek base Elo
    LEAGUE_BASE_ELO = {
        'ENG-Premier League': 1650,   # En güçlü lig
        'ESP-La Liga': 1620,
        'GER-Bundesliga': 1600,
        'ITA-Serie A': 1600,
        'FRA-Ligue 1': 1550,
        'POR-Primeira Liga': 1480,
        'TUR-Super Lig': 1450,
        'BEL-Pro League': 1430,
        'KSA-Pro League': 1400,
        'INT-Champions League': 1700,  # CL takımları güçlü
        'INT-Europa League': 1550,
        'INT-Conference League': 1450,
    }
    
    # Elo K-faktörü (her maçın etkisi)
    ELO_K_FACTOR = 32
    
    def __init__(self, league_avg_goals: float = 2.7):
        self.league_avg_goals = league_avg_goals
        self.avg_goals_per_team = league_avg_goals / 2
    
    def calculate_attack_rating(
        self,
        avg_goals: float,
        avg_xg: float,
        form_points: int,
        max_form_points: int = 15
    ) -> float:
        """
        Hücum gücü hesapla.
        
        Rating = (Gerçek Gol * 0.4 + xG * 0.6) / Lig Ortalaması * Form Faktörü
        """
        # Gol ve xG kombinasyonu
        combined_goals = (avg_goals * self.ACTUAL_GOALS_WEIGHT + 
                         avg_xg * self.XG_WEIGHT)
        
        # Lig ortalamasına göre normalize et
        base_rating = combined_goals / self.avg_goals_per_team
        
        # Form faktörü (0.8 - 1.2 arası)
        form_factor = 0.8 + (form_points / max_form_points) * 0.4
        
        return round(base_rating * form_factor, 3)
    
    def calculate_defense_rating(
        self,
        avg_conceded: float,
        avg_xg_against: float,
        form_points: int,
        max_form_points: int = 15
    ) -> float:
        """
        Savunma gücü hesapla.
        Düşük = iyi savunma (az gol yiyor).
        
        Rating = Lig Ortalaması / (Yenilen Gol * 0.4 + xG Against * 0.6)
        """
        # Gol ve xG kombinasyonu
        combined_conceded = (avg_conceded * self.ACTUAL_GOALS_WEIGHT + 
                            avg_xg_against * self.XG_WEIGHT)
        
        # Sıfıra bölmeyi önle
        if combined_conceded < 0.1:
            combined_conceded = 0.1
        
        # Ters orantılı rating (az yemek = yüksek rating)
        base_rating = self.avg_goals_per_team / combined_conceded
        
        # Form faktörü
        form_factor = 0.8 + (form_points / max_form_points) * 0.4
        
        return round(base_rating * form_factor, 3)
    
    def calculate_risk_factor(
        self,
        red_cards: int,
        pk_won: int,
        matches_played: int = 20
    ) -> float:
        """
        Risk/Ödül faktörü hesapla.
        
        - Kırmızı kart: Negatif etki (eksik oyuncu riski)
        - Penaltı kazanma: Pozitif etki (ekstra gol fırsatı)
        
        Returns: -0.1 ile +0.1 arası çarpan
        """
        if matches_played < 1:
            matches_played = 1
        
        # Maç başına oranlar
        red_per_match = red_cards / matches_played
        pk_per_match = pk_won / matches_played
        
        # Risk faktörü
        # Kırmızı kart: olumsuz (-0.05 per 0.1 red/match)
        # Penaltı: olumlu (+0.03 per 0.1 pk/match)
        risk = (pk_per_match * 0.3) - (red_per_match * 0.5)
        
        # -0.1 ile +0.1 arası sınırla
        return round(max(-0.1, min(0.1, risk)), 3)
    
    def calculate_xg_quality(
        self,
        goals_scored: float,
        goals_conceded: float,
        wins: int,
        draws: int,
        losses: int,
        total_matches: int
    ) -> float:
        """
        xG kalitesini hesapla.
        
        xG Kalitesi = Gol verimliliği + Şut kalitesi tahmini
        
        Yüksek gol/maç oranı + yüksek galibiyet oranı = kaliteli şanslar yaratıyor
        Düşük gol/maç oranı + düşük galibiyet oranı = zayıf şut kalitesi
        
        Args:
            goals_scored: Atılan gol sayısı
            goals_conceded: Yenilen gol sayısı
            wins, draws, losses: W-D-L kaydı
            total_matches: Toplam maç
        
        Returns:
            xG kalitesi (0.7-1.3 arası)
        """
        if total_matches < 3:
            return 1.0  # Varsayılan
        
        # Gol ortalaması
        goals_per_match = goals_scored / total_matches
        
        # Beklenen gol (lig ortalaması 1.35)
        league_avg = 1.35
        
        # Gol verimliliği
        # 2+ gol/maç = yüksek verimlilik, <1 gol/maç = düşük verimlilik
        goal_efficiency = goals_per_match / league_avg
        
        # Galibiyet oranı etkisi
        # Çok gol atan ama kazanamayan takım = iyi şans yaratamıyor olabilir
        win_rate = wins / total_matches if total_matches > 0 else 0.33
        
        # xG kalitesi
        # Gol verimliliği * galibiyet bonus
        xg_quality = goal_efficiency * (0.8 + win_rate * 0.4)
        
        # 0.7-1.3 arası sınırla
        return round(max(0.7, min(1.3, xg_quality)), 3)
    
    def calculate_squad_strength(
        self,
        recent_form: List[str],
        goals_per_match: float,
        conceded_per_match: float,
        form_momentum: float = 0.0
    ) -> float:
        """
        Kadro gücü faktörü hesapla.
        
        Sakatlık/ceza verisi olmadığında, performans düşüşünden tahmin ediyoruz:
        - Ani performans düşüşü = muhtemelen kadro eksikliği
        - Beklenenden düşük gol = ofansif oyuncu eksikliği
        - Beklenenden yüksek yenilen gol = defansif oyuncu eksikliği
        
        Args:
            recent_form: Son maç sonuçları ['W', 'D', 'L', ...]
            goals_per_match: Maç başı gol
            conceded_per_match: Maç başı yenilen gol
            form_momentum: Form momentumu
        
        Returns:
            Kadro gücü (0.8-1.1 arası)
        """
        base_strength = 1.0
        
        # 1. Son maçlardaki düşüş = olası sakatlık sorunu
        if len(recent_form) >= 3:
            last_3 = recent_form[-3:]
            losses_in_last_3 = sum(1 for r in last_3 if r == 'L')
            
            # 3 maçta 2+ mağlubiyet = kadro sorunu olabilir
            if losses_in_last_3 >= 2:
                base_strength -= 0.08
            elif losses_in_last_3 == 0 and all(r == 'W' for r in last_3):
                # 3 galibiyet = tam kadro
                base_strength += 0.05
        
        # 2. Gol düşüşü = hücum oyuncusu eksikliği
        if goals_per_match < 0.8:
            base_strength -= 0.05
        elif goals_per_match > 2.0:
            base_strength += 0.03
        
        # 3. Savunma sorunları = defans oyuncusu eksikliği
        if conceded_per_match > 2.0:
            base_strength -= 0.05
        elif conceded_per_match < 0.8:
            base_strength += 0.03
        
        # 4. Form momentumu etkisi
        if form_momentum < -0.5:
            base_strength -= 0.05  # Kötü form = kadro sorunu olabilir
        elif form_momentum > 0.5:
            base_strength += 0.03  # İyi form = sağlıklı kadro
        
        # 0.8-1.1 arası sınırla
        return round(max(0.8, min(1.1, base_strength)), 3)
    
    def calculate_elo_rating(
        self,
        wins: int,
        draws: int,
        losses: int,
        goals_for: int,
        goals_against: int,
        league: str = ''
    ) -> float:
        """
        Takımın Elo puanını hesapla.
        
        Elo hesaplama:
        1. Lig bazlı temel puan ile başla
        2. Galibiyet oranına göre ayarla
        3. Gol farkına göre bonus/ceza
        
        Args:
            wins, draws, losses: Sezon W-D-L kaydı
            goals_for, goals_against: Atılan/yenilen goller
            league: Lig kodu
        
        Returns:
            Elo puanı (1200-1900 arası)
        """
        # Temel Elo (lig gücüne göre)
        base_elo = self.LEAGUE_BASE_ELO.get(league, 1500)
        
        total_matches = wins + draws + losses
        if total_matches < 3:
            return base_elo  # Yeterli maç yok
        
        # Puan hesapla (W=3, D=1, L=0)
        points = wins * 3 + draws
        max_points = total_matches * 3
        
        # Puan yüzdesi (0-1 arası)
        point_pct = points / max_points if max_points > 0 else 0.33
        
        # Elo ayarlaması
        # %66+ puan = şampiyon adayı (+150)
        # %50 puan = orta sıra (0)
        # %33- puan = düşme hattı (-150)
        elo_adjustment = (point_pct - 0.5) * 300
        
        # Gol farkı bonusu
        goal_diff = goals_for - goals_against
        goal_diff_per_match = goal_diff / total_matches if total_matches > 0 else 0
        
        # Her maç başına +1 gol farkı = +20 Elo
        goal_bonus = goal_diff_per_match * 20
        goal_bonus = max(-50, min(50, goal_bonus))  # -50 ile +50 arası sınırla
        
        # Final Elo
        elo = base_elo + elo_adjustment + goal_bonus
        
        # 1200-1900 arası sınırla
        return round(max(1200, min(1900, elo)), 0)
    
    def calculate_elo_win_probability(
        self,
        home_elo: float,
        away_elo: float,
        home_advantage: float = 65
    ) -> Tuple[float, float, float]:
        """
        Elo puanlarından kazanma olasılıklarını hesapla.
        
        Elo formülü: E = 1 / (1 + 10^((Rb - Ra) / 400))
        
        Args:
            home_elo: Ev sahibi Elo puanı
            away_elo: Deplasman Elo puanı
            home_advantage: Ev avantajı Elo karşılığı (varsayılan 65)
        
        Returns:
            (home_win_prob, draw_prob, away_win_prob) - 0-1 arası
        """
        # Ev avantajı ekle
        effective_home_elo = home_elo + home_advantage
        
        # Beklenen skor (0-1 arası)
        elo_diff = effective_home_elo - away_elo
        home_expected = 1 / (1 + 10 ** (-elo_diff / 400))
        away_expected = 1 - home_expected
        
        # Beraberlik olasılığı (Elo farkı azaldıkça artar)
        # Fark 0 ise: %28 beraberlik, fark 200 ise: %20, fark 400 ise: %15
        draw_base = 0.28 - abs(elo_diff) / 2000
        draw_prob = max(0.12, min(0.30, draw_base))
        
        # Galibiyet olasılıklarını ayarla
        remaining = 1 - draw_prob
        home_win_prob = home_expected * remaining
        away_win_prob = away_expected * remaining
        
        # Normalize et
        total = home_win_prob + draw_prob + away_win_prob
        return (
            home_win_prob / total,
            draw_prob / total,
            away_win_prob / total
        )
    
    def calculate_form_trend(
        self,
        recent_results: List[str],
        recent_goals: List[int] = None,
        recent_conceded: List[int] = None
    ) -> float:
        """
        Son maçlardaki form trendini hesapla.
        
        Son maçlar daha ağırlıklı:
        - 5. maç (en son): %30 ağırlık
        - 4. maç: %25 ağırlık
        - 3. maç: %20 ağırlık
        - 2. maç: %15 ağırlık
        - 1. maç (en eski): %10 ağırlık
        
        Args:
            recent_results: ['W', 'W', 'D', 'L', 'W'] formatında (eski->yeni)
            recent_goals: [2, 1, 0, 3, 2] formatında gol sayıları
            recent_conceded: [0, 1, 1, 2, 0] formatında yenilen goller
        
        Returns: -0.15 ile +0.15 arası trend faktörü
        """
        if not recent_results or len(recent_results) < 2:
            return 0.0
        
        # Ağırlıklar (son maça doğru artıyor)
        weights = [0.10, 0.15, 0.20, 0.25, 0.30]
        
        # Sonuç sayısına göre ağırlıkları ayarla
        n = min(len(recent_results), 5)
        if n < 5:
            # Daha az maç varsa ağırlıkları yeniden normalize et
            weights = weights[-n:]
            total_w = sum(weights)
            weights = [w / total_w for w in weights]
        
        # Puan hesapla (W=3, D=1, L=0)
        points = []
        for r in recent_results[-n:]:
            if r == 'W':
                points.append(3)
            elif r == 'D':
                points.append(1)
            else:
                points.append(0)
        
        # Ağırlıklı puan ortalaması
        weighted_avg = sum(p * w for p, w in zip(points, weights))
        
        # İlk yarı vs son yarı karşılaştırması (trend yönü)
        half = n // 2
        if half > 0:
            first_half_avg = sum(points[:half]) / half
            second_half_avg = sum(points[half:]) / len(points[half:])
            trend_direction = (second_half_avg - first_half_avg) / 3.0  # -1 ile +1 arası normalize
        else:
            trend_direction = 0.0
        
        # Gol trendi (varsa)
        goal_trend = 0.0
        if recent_goals and recent_conceded and len(recent_goals) >= 2:
            n_goals = min(len(recent_goals), 5)
            # Son maçlardaki gol farkı trendi
            goal_diffs = [g - c for g, c in zip(recent_goals[-n_goals:], recent_conceded[-n_goals:])]
            if len(goal_diffs) >= 2:
                first_gd = sum(goal_diffs[:len(goal_diffs)//2]) / max(1, len(goal_diffs)//2)
                second_gd = sum(goal_diffs[len(goal_diffs)//2:]) / max(1, len(goal_diffs) - len(goal_diffs)//2)
                goal_trend = (second_gd - first_gd) * 0.02  # Küçük etki
                goal_trend = max(-0.05, min(0.05, goal_trend))
        
        # Toplam trend
        # Ağırlıklı ortalama etkisi: (weighted_avg - 1.5) / 3 -> yüksek puan = pozitif
        avg_effect = (weighted_avg - 1.5) / 10  # -0.05 ile +0.05 arası
        
        # Trend yönü etkisi
        direction_effect = trend_direction * 0.08  # -0.08 ile +0.08 arası
        
        # Toplam
        total_trend = avg_effect + direction_effect + goal_trend
        
        # -0.15 ile +0.15 arası sınırla
        return round(max(-0.15, min(0.15, total_trend)), 3)
    
    def calculate_h2h_factor(
        self,
        h2h_wins: int,
        h2h_losses: int,
        h2h_draws: int,
        h2h_goals_for: int,
        h2h_goals_against: int,
        total_matches: int
    ) -> float:
        """
        Kafa kafaya (Head-to-Head) faktörü hesapla.
        
        - Geçmiş karşılaşmalarda üstünlük = pozitif etki
        - Gol farkı da hesaba katılır
        - Maç sayısına göre güvenilirlik ağırlığı
        
        Returns: -0.12 ile +0.12 arası çarpan
        """
        if total_matches < 2:
            # 2'den az maç = güvenilir değil, etkisini azalt
            return 0.0
        
        # Güvenilirlik ağırlığı (2-10 maç arası ölçeklenir)
        # 2 maç = 0.4, 5 maç = 0.7, 10+ maç = 1.0
        reliability = min(1.0, 0.3 + (total_matches - 2) * 0.0875)
        
        # Galibiyet oranı hesapla
        # Galibiyetler tam puan, beraberlikler yarım puan
        win_score = (h2h_wins * 1.0 + h2h_draws * 0.4) / total_matches
        loss_score = (h2h_losses * 1.0 + h2h_draws * 0.4) / total_matches
        
        # Net avantaj (-1 ile +1 arası)
        net_advantage = win_score - loss_score
        
        # Gol farkı etkisi (maç başına)
        if total_matches > 0:
            goal_diff_per_match = (h2h_goals_for - h2h_goals_against) / total_matches
            # Gol farkı etkisi: her gol farkı için +/- 0.01
            goal_effect = max(-0.04, min(0.04, goal_diff_per_match * 0.02))
        else:
            goal_effect = 0.0
        
        # H2H faktörü hesapla
        # Net avantaj: -0.08 ile +0.08 arası
        # Gol etkisi: -0.04 ile +0.04 arası
        base_h2h = net_advantage * 0.08 + goal_effect
        
        # Güvenilirlik ağırlığı uygula
        h2h = base_h2h * reliability
        
        # -0.12 ile +0.12 arası sınırla (maks %12 etki)
        return round(max(-0.12, min(0.12, h2h)), 3)
    
    def get_team_rating(self, match_row: pd.Series, team: str = 'home') -> TeamRating:
        """
        Takım rating'ini hesapla.
        
        Ev/Deplasman Ayrımı:
        - Ev sahibi takım için: EVDEKİ istatistikleri öncelikli kullan
        - Deplasman takımı için: DEPLASMANDAKİ istatistikleri öncelikli kullan
        """
        prefix = f'{team}_'
        
        # ---- EV/DEPLASMAN AYRIMI ----
        if team == 'home':
            # Ev sahibi: EVDEKİ performans
            ha_played = match_row.get('home_at_home_played', 0)
            if ha_played >= 3:  # En az 3 ev maçı varsa ev istatistiklerini kullan
                avg_goals = match_row.get('home_at_home_avg_goals', 1.35)
                avg_conceded = match_row.get('home_at_home_avg_conceded', 1.2)
                ha_form = match_row.get('home_at_home_form', 7)
                # xG için genel veriyi kullan (ev/deplasman xG yok)
                avg_xg = match_row.get(f'{prefix}last5_avg_xg', avg_goals)
                avg_xg_against = match_row.get(f'{prefix}last5_avg_xg_against', avg_conceded)
                # Form: %60 ev formu + %40 genel form
                general_form = match_row.get(f'{prefix}last5_form_points', 7)
                form_points = int(ha_form * 0.6 + general_form * 0.4)
            else:
                # Yeterli ev maçı yok, genel istatistikleri kullan (ev avantajı ile)
                avg_goals = match_row.get(f'{prefix}last5_avg_goals', 1.0) * 1.1  # %10 ev bonusu
                avg_conceded = match_row.get(f'{prefix}last5_avg_conceded', 1.0) * 0.95  # %5 ev bonusu
                avg_xg = match_row.get(f'{prefix}last5_avg_xg', avg_goals)
                avg_xg_against = match_row.get(f'{prefix}last5_avg_xg_against', avg_conceded)
                form_points = match_row.get(f'{prefix}last5_form_points', 7)
        else:
            # Deplasman: DEPLASMANDAKİ performans
            ha_played = match_row.get('away_at_away_played', 0)
            if ha_played >= 3:  # En az 3 deplasman maçı varsa deplasman istatistiklerini kullan
                avg_goals = match_row.get('away_at_away_avg_goals', 1.0)
                avg_conceded = match_row.get('away_at_away_avg_conceded', 1.4)
                ha_form = match_row.get('away_at_away_form', 5)
                # xG için genel veriyi kullan
                avg_xg = match_row.get(f'{prefix}last5_avg_xg', avg_goals)
                avg_xg_against = match_row.get(f'{prefix}last5_avg_xg_against', avg_conceded)
                # Form: %60 deplasman formu + %40 genel form
                general_form = match_row.get(f'{prefix}last5_form_points', 7)
                form_points = int(ha_form * 0.6 + general_form * 0.4)
            else:
                # Yeterli deplasman maçı yok, genel istatistikleri kullan (deplasman dezavantajı ile)
                avg_goals = match_row.get(f'{prefix}last5_avg_goals', 1.0) * 0.9  # %10 deplasman cezası
                avg_conceded = match_row.get(f'{prefix}last5_avg_conceded', 1.0) * 1.05  # %5 deplasman cezası
                avg_xg = match_row.get(f'{prefix}last5_avg_xg', avg_goals)
                avg_xg_against = match_row.get(f'{prefix}last5_avg_xg_against', avg_conceded)
                form_points = match_row.get(f'{prefix}last5_form_points', 7)
        
        # Sezon verileri (risk faktörü için)
        red_cards = match_row.get(f'{prefix}season_red', 0)
        pk_won = match_row.get(f'{prefix}season_pk_won', 0)
        
        # Head-to-Head verisi
        h2h_total = match_row.get('h2h_total_matches', 0)
        if team == 'home':
            h2h_wins = match_row.get('h2h_home_wins', 0)
            h2h_losses = match_row.get('h2h_away_wins', 0)
            h2h_goals_for = match_row.get('h2h_home_goals', 0)
            h2h_goals_against = match_row.get('h2h_away_goals', 0)
        else:
            h2h_wins = match_row.get('h2h_away_wins', 0)
            h2h_losses = match_row.get('h2h_home_wins', 0)
            h2h_goals_for = match_row.get('h2h_away_goals', 0)
            h2h_goals_against = match_row.get('h2h_home_goals', 0)
        h2h_draws = match_row.get('h2h_draws', 0)
        
        # Son 5 maç trendi
        form_str = match_row.get(f'{prefix}recent_form', '')
        goals_str = match_row.get(f'{prefix}recent_goals', '')
        conceded_str = match_row.get(f'{prefix}recent_conceded', '')
        form_momentum = match_row.get(f'{prefix}form_momentum', 0.0)
        
        recent_form = form_str.split(',') if form_str else []
        recent_goals = [int(x) for x in goals_str.split(',') if x.isdigit()] if goals_str else []
        recent_conceded = [int(x) for x in conceded_str.split(',') if x.isdigit()] if conceded_str else []
        
        # Form momentum'u recent_form'a ekle (momentum pozitifse son maçlara galibiyet ekle)
        if not recent_form and form_momentum != 0:
            # W-D-L kaydından tahmini form oluştur
            if form_momentum > 0.5:
                recent_form = ['D', 'W', 'W', 'W', 'W']  # Güçlü form
            elif form_momentum > 0:
                recent_form = ['L', 'D', 'W', 'W', 'W']  # İyi form
            elif form_momentum > -0.5:
                recent_form = ['L', 'L', 'D', 'W', 'W']  # Orta form
            else:
                recent_form = ['L', 'L', 'L', 'D', 'W']  # Zayıf form
        
        # Rating hesapla
        attack = self.calculate_attack_rating(avg_goals, avg_xg, form_points)
        defense = self.calculate_defense_rating(avg_conceded, avg_xg_against, form_points)
        form = form_points / 15.0  # Normalize (0-1)
        risk = self.calculate_risk_factor(red_cards, pk_won)
        h2h = self.calculate_h2h_factor(h2h_wins, h2h_losses, h2h_draws, h2h_goals_for, h2h_goals_against, h2h_total)
        trend = self.calculate_form_trend(recent_form, recent_goals, recent_conceded)
        
        # Elo Rating hesapla
        league = match_row.get('league', '')
        
        # Ev/Deplasman istatistiklerinden toplam W-D-L hesapla
        if team == 'home':
            ha_played = match_row.get('home_at_home_played', 0)
            # Genel istatistikler (tüm maçlar)
            total_goals = match_row.get('home_last10_avg_goals', 1.35) * 10
            total_conceded = match_row.get('home_last10_avg_conceded', 1.2) * 10
            goals_per_match = match_row.get('home_at_home_avg_goals', avg_goals)
            conceded_per_match = match_row.get('home_at_home_avg_conceded', avg_conceded)
        else:
            ha_played = match_row.get('away_at_away_played', 0)
            total_goals = match_row.get('away_last10_avg_goals', 1.35) * 10
            total_conceded = match_row.get('away_last10_avg_conceded', 1.2) * 10
            goals_per_match = match_row.get('away_at_away_avg_goals', avg_goals)
            conceded_per_match = match_row.get('away_at_away_avg_conceded', avg_conceded)
        
        # Form puanından W-D-L tahmini
        # 15 puan = 5W, 10 puan = 3W1D1L, 5 puan = 1W2D2L
        estimated_wins = form_points // 3
        estimated_draws = (form_points % 3)
        estimated_losses = 5 - estimated_wins - estimated_draws
        
        elo = self.calculate_elo_rating(
            wins=max(0, estimated_wins),
            draws=max(0, estimated_draws),
            losses=max(0, estimated_losses),
            goals_for=int(total_goals),
            goals_against=int(total_conceded),
            league=league
        )
        
        # xG Kalitesi hesapla
        xg_quality = self.calculate_xg_quality(
            goals_scored=total_goals,
            goals_conceded=total_conceded,
            wins=max(0, estimated_wins),
            draws=max(0, estimated_draws),
            losses=max(0, estimated_losses),
            total_matches=5
        )
        
        # Kadro Gücü hesapla
        squad_strength = self.calculate_squad_strength(
            recent_form=recent_form,
            goals_per_match=goals_per_match,
            conceded_per_match=conceded_per_match,
            form_momentum=form_momentum
        )
        
        return TeamRating(
            attack=attack,
            defense=defense,
            form=form,
            risk_factor=risk,
            h2h_factor=h2h,
            form_trend=trend,
            elo_rating=elo,
            xg_quality=xg_quality,
            squad_strength=squad_strength
        )
    
    def calculate_expected_goals(
        self,
        home_rating: TeamRating,
        away_rating: TeamRating,
        league: str = ''
    ) -> Tuple[float, float]:
        """
        FiveThirtyEight Metodolojisi ile Beklenen Gol Hesaplama.
        
        FiveThirtyEight'in yaklaşımı:
        1. Her takımın hücum ve savunma rating'i var
        2. Beklenen gol = Hücum Rating * (Lig Ort / Savunma Rating) * Ev Avantajı
        3. Faktörler çarpan olarak değil, SPI içinde zaten mevcut
        
        Kaynak: fivethirtyeight.com/methodology/how-our-club-soccer-predictions-work
        """
        # Lig bazlı ev avantajı (FiveThirtyEight: ~%10-18 arası)
        home_advantage = self.LEAGUE_HOME_ADVANTAGE.get(league, self.BASE_HOME_ADVANTAGE)
        
        # =====================================================
        # FiveThirtyEight SPI FORMÜLÜ
        # =====================================================
        # Ev sahibi beklenen gol = (Ev Hücum / Lig Ort) * (Lig Ort / Dep Savunma) * Lig Ort * Ev Avantajı
        # Basitleştirilmiş: Ev Hücum * (1/Dep Savunma) * Lig Ort * Ev Avantajı
        
        # Temel xG hesaplama (SPI bazlı)
        home_xg = (home_rating.attack / away_rating.defense) * self.AVG_GOALS_PER_TEAM * home_advantage
        
        # Deplasman için ters ev avantajı
        away_disadvantage = 2 - home_advantage  # 1.12 -> 0.88
        away_xg = (away_rating.attack / home_rating.defense) * self.AVG_GOALS_PER_TEAM * away_disadvantage
        
        # =====================================================
        # FORM DÜZELTMES İ(FiveThirtyEight: son maç performansı)
        # =====================================================
        # Form trendi küçük bir düzeltme olarak uygulanır
        # FiveThirtyEight'te bu zaten rating içinde ama biz ekstra form ekleriz
        form_adj_home = 1.0 + (home_rating.form_trend * 0.3)  # max ±4.5%
        form_adj_away = 1.0 + (away_rating.form_trend * 0.3)
        
        home_xg *= max(0.92, min(1.08, form_adj_home))
        away_xg *= max(0.92, min(1.08, form_adj_away))
        
        # =====================================================
        # H2H DÜZELTMESİ (Kafa kafaya tarihçe)
        # =====================================================
        # FiveThirtyEight H2H kullanmıyor ama biz küçük bir faktör olarak ekleriz
        h2h_adj_home = 1.0 + (home_rating.h2h_factor * 0.25)  # max ±3%
        h2h_adj_away = 1.0 + (away_rating.h2h_factor * 0.25)
        
        home_xg *= max(0.95, min(1.05, h2h_adj_home))
        away_xg *= max(0.95, min(1.05, h2h_adj_away))
        
        # =====================================================
        # LİMİT YOK - HAM VERİ İLE HESAPLAMA
        # =====================================================
        # Limit koymuyoruz! Veriler ne gösteriyorsa o.
        # Eğer takım gerçekten çok güçlüyse ve 5.0 xG çıkıyorsa,
        # bunu 4.0'a düşürmek yanlış. Ham veri daha doğru.
        # 
        # Sadece minimum limit (negatif olmasın diye)
        # =====================================================
        
        home_xg = max(0.3, home_xg)  # Sadece negatif olmasın
        away_xg = max(0.2, away_xg)   # Sadece negatif olmasın
        
        return round(home_xg, 2), round(away_xg, 2)
    
    def poisson_probability(self, expected: float, actual: int) -> float:
        """Poisson olasılığı hesapla."""
        return poisson.pmf(actual, expected)
    
    def dixon_coles_adjustment(
        self,
        home_goals: int,
        away_goals: int,
        home_xg: float,
        away_xg: float,
        rho: float = None
    ) -> float:
        """
        Dixon-Coles düzeltme faktörü.
        Düşük skorlu maçlarda (0-0, 1-0, 0-1, 1-1) bağımlılık düzeltmesi yapar.
        
        Kaynak: Dixon & Coles (1997) - "Modelling Association Football Scores"
        """
        if rho is None:
            rho = self.DIXON_COLES_RHO
        
        if home_goals == 0 and away_goals == 0:
            return 1 - home_xg * away_xg * rho
        elif home_goals == 0 and away_goals == 1:
            return 1 + home_xg * rho
        elif home_goals == 1 and away_goals == 0:
            return 1 + away_xg * rho
        elif home_goals == 1 and away_goals == 1:
            return 1 - rho
        else:
            return 1.0
    
    def monte_carlo_simulation(
        self,
        home_xg: float,
        away_xg: float,
        n_sims: int = None
    ) -> Dict[str, Any]:
        """
        Monte Carlo simülasyonu ile belirsizlik analizi.
        
        Returns:
            home_win_pct, draw_pct, away_win_pct, 
            avg_home_goals, avg_away_goals,
            confidence_interval
        """
        if n_sims is None:
            n_sims = self.MONTE_CARLO_SIMS
        
        # xG değerlerinde küçük varyasyon ekle (gerçekçilik için)
        home_xg_samples = np.random.normal(home_xg, home_xg * 0.15, n_sims)
        away_xg_samples = np.random.normal(away_xg, away_xg * 0.15, n_sims)
        
        # Negatif değerleri düzelt
        home_xg_samples = np.maximum(home_xg_samples, 0.1)
        away_xg_samples = np.maximum(away_xg_samples, 0.1)
        
        # Simülasyon
        home_goals = np.random.poisson(home_xg_samples)
        away_goals = np.random.poisson(away_xg_samples)
        
        # Sonuçları hesapla
        home_wins = np.sum(home_goals > away_goals)
        draws = np.sum(home_goals == away_goals)
        away_wins = np.sum(home_goals < away_goals)
        
        # Gol dağılımları
        total_goals = home_goals + away_goals
        under_3_5 = np.sum(total_goals <= 3)
        over_3_5 = np.sum(total_goals > 3)
        
        return {
            'home_win_pct': (home_wins / n_sims) * 100,
            'draw_pct': (draws / n_sims) * 100,
            'away_win_pct': (away_wins / n_sims) * 100,
            'under_3_5_pct': (under_3_5 / n_sims) * 100,
            'over_3_5_pct': (over_3_5 / n_sims) * 100,
            'avg_home_goals': np.mean(home_goals),
            'avg_away_goals': np.mean(away_goals),
            'std_home_goals': np.std(home_goals),
            'std_away_goals': np.std(away_goals),
        }
    
    def calculate_score_probabilities(
        self,
        home_xg: float,
        away_xg: float,
        max_goals: int = 8,
        use_dixon_coles: bool = True
    ) -> Dict[Tuple[int, int], float]:
        """
        Tüm muhtemel skorların olasılıklarını hesapla.
        Dixon-Coles düzeltmesi ile.
        """
        probabilities = {}
        
        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                # Temel Poisson olasılığı
                prob = (self.poisson_probability(home_xg, home_goals) * 
                       self.poisson_probability(away_xg, away_goals))
                
                # Dixon-Coles düzeltmesi
                if use_dixon_coles:
                    adjustment = self.dixon_coles_adjustment(
                        home_goals, away_goals, home_xg, away_xg
                    )
                    prob *= adjustment
                
                probabilities[(home_goals, away_goals)] = max(0, prob)
        
        # Normalize et
        total = sum(probabilities.values())
        if total > 0:
            probabilities = {k: v/total for k, v in probabilities.items()}
        
        return probabilities
    
    def calculate_match_odds(
        self,
        score_probs: Dict[Tuple[int, int], float]
    ) -> Dict[str, float]:
        """
        1X2 ve gol olasılıklarını hesapla.
        """
        home_win = 0.0
        draw = 0.0
        away_win = 0.0
        
        goals_0_3 = 0.0  # 0, 1, 2, 3 toplam gol
        
        for (h, a), prob in score_probs.items():
            total_goals = h + a
            
            if h > a:
                home_win += prob
            elif h == a:
                draw += prob
            else:
                away_win += prob
            
            if total_goals <= 3:
                goals_0_3 += prob
        
        # Normalize et (toplam 100%)
        total = home_win + draw + away_win
        if total > 0:
            home_win /= total
            draw /= total
            away_win /= total
        
        return {
            'home_win': round(home_win * 100, 1),
            'draw': round(draw * 100, 1),
            'away_win': round(away_win * 100, 1),
            'under_3_5': round(goals_0_3 * 100, 1),
            'over_3_5': round((1 - goals_0_3) * 100, 1)
        }
    
    def get_most_likely_score(
        self,
        score_probs: Dict[Tuple[int, int], float]
    ) -> Tuple[Tuple[int, int], float]:
        """En olası skoru bul."""
        most_likely = max(score_probs.items(), key=lambda x: x[1])
        return most_likely[0], round(most_likely[1] * 100, 1)
    
    def calculate_confidence(
        self,
        home_rating: TeamRating,
        away_rating: TeamRating,
        odds: Dict[str, float]
    ) -> float:
        """
        Tahmin güven skoru hesapla (0-100).
        
        Faktörler:
        - Form istikrarı
        - Olasılık farkı (açık favori = yüksek güven)
        - Rating kalitesi
        """
        # Form ortalaması
        avg_form = (home_rating.form + away_rating.form) / 2
        
        # Olasılık dağılımı (açık favori = yüksek güven)
        max_prob = max(odds['home_win'], odds['draw'], odds['away_win'])
        prob_confidence = (max_prob - 33.3) / 66.7  # 0-1 arası
        
        # Rating kalitesi (ortalamaya yakınlık)
        rating_quality = 1 - abs(1 - (home_rating.attack + away_rating.attack) / 2) * 0.5
        
        # Toplam güven
        confidence = (avg_form * 30 + prob_confidence * 50 + rating_quality * 20)
        
        return round(min(95, max(25, confidence)), 1)
    
    def predict_match(self, match_row: pd.Series, use_monte_carlo: bool = True) -> MatchPrediction:
        """
        Hibrit tahmin: Poisson + Dixon-Coles + Monte Carlo
        """
        home_team = match_row.get('home_team', 'Home')
        away_team = match_row.get('away_team', 'Away')
        league = match_row.get('league', '')
        
        # Takım rating'leri
        home_rating = self.get_team_rating(match_row, 'home')
        away_rating = self.get_team_rating(match_row, 'away')
        
        # Beklenen goller (lig bazlı ev avantajı ile)
        home_xg, away_xg = self.calculate_expected_goals(home_rating, away_rating, league)
        
        # 1. Poisson + Dixon-Coles
        score_probs = self.calculate_score_probabilities(home_xg, away_xg, use_dixon_coles=True)
        poisson_odds = self.calculate_match_odds(score_probs)
        
        # 2. Monte Carlo simülasyonu
        if use_monte_carlo:
            mc_results = self.monte_carlo_simulation(home_xg, away_xg)
            
            # 3. Elo tabanlı olasılıklar
            elo_home, elo_draw, elo_away = self.calculate_elo_win_probability(
                home_rating.elo_rating,
                away_rating.elo_rating,
                home_advantage=65 if league not in ['INT-Champions League', 'INT-Europa League'] else 40
            )
            
            # =====================================================
            # FiveThirtyEight METODOLOJİSİ
            # =====================================================
            # 
            # FiveThirtyEight'in yaklaşımı:
            # 1. SPI rating'lerinden beklenen gol hesapla
            # 2. Poisson dağılımı ile tüm skorları hesapla
            # 3. Beraberlik olasılığını %9 artır (draw inflation)
            # 4. Monte Carlo ile belirsizlik ekle
            #
            # Kaynak: fivethirtyeight.com/methodology
            # =====================================================
            
            # =====================================================
            # ADIM 1: SPI BAZLI TAHMİN (%70)
            # =====================================================
            # SPI rating'leri zaten tüm veriyi içeriyor:
            # - Sezon performansı (W-D-L)
            # - Gol ortalamaları
            # - Ev/Deplasman ayrımı
            # - Form (son maçlar)
            #
            # Poisson bu verileri kullanarak olasılık hesaplıyor
            # =====================================================
            
            SPI_WEIGHT = 0.70  # SPI bazlı Poisson tahmini
            MC_WEIGHT = 0.20   # Monte Carlo belirsizlik
            ELO_WEIGHT = 0.10  # Ek Elo düzeltmesi
            
            # Temel 1X2 olasılıkları (Poisson + Dixon-Coles)
            base_home = poisson_odds['home_win']
            base_draw = poisson_odds['draw']
            base_away = poisson_odds['away_win']
            
            # =====================================================
            # ADIM 2: BERABERLİK DÜZELTMESİ (FiveThirtyEight: ~%9)
            # =====================================================
            # FiveThirtyEight beraberlik olasılığını artırır
            # çünkü Poisson beraberlikleri eksik sayar
            # =====================================================
            
            draw_boost = base_draw * self.DRAW_INFLATION  # ~%9 artış
            base_draw += draw_boost
            
            # Diğerlerinden orantılı olarak düş
            home_reduction = draw_boost * (base_home / (base_home + base_away))
            away_reduction = draw_boost * (base_away / (base_home + base_away))
            base_home -= home_reduction
            base_away -= away_reduction
            
            # =====================================================
            # ADIM 3: HİBRİT HESAPLAMA
            # =====================================================
            # %70 SPI/Poisson + %20 Monte Carlo + %10 Elo
            # =====================================================
            
            final_odds = {
                'home_win': (
                    base_home * SPI_WEIGHT +
                    mc_results['home_win_pct'] * MC_WEIGHT +
                    elo_home * 100 * ELO_WEIGHT
                ),
                'draw': (
                    base_draw * SPI_WEIGHT +
                    mc_results['draw_pct'] * MC_WEIGHT +
                    elo_draw * 100 * ELO_WEIGHT
                ),
                'away_win': (
                    base_away * SPI_WEIGHT +
                    mc_results['away_win_pct'] * MC_WEIGHT +
                    elo_away * 100 * ELO_WEIGHT
                ),
            }
            
            # =====================================================
            # ADIM 4: H2H VE FORM KÜÇÜK DÜZELTMELERİ
            # =====================================================
            # FiveThirtyEight H2H kullanmıyor ama biz küçük bir
            # düzeltme olarak ekliyoruz (max ±2%)
            # =====================================================
            
            # H2H düzeltmesi (max ±2%)
            h2h_adj = (home_rating.h2h_factor - away_rating.h2h_factor) * 2
            final_odds['home_win'] += h2h_adj
            final_odds['away_win'] -= h2h_adj
            
            # Form düzeltmesi (max ±3%)
            form_adj = (home_rating.form_trend - away_rating.form_trend) * 3
            final_odds['home_win'] += form_adj
            final_odds['away_win'] -= form_adj
            
            # =====================================================
            # GOL OLASILIKLARI - HAM VERİ İLE HESAPLAMA
            # =====================================================
            # Limit yok! Poisson ve Monte Carlo'nun verdiği sonuçları
            # olduğu gibi kullanıyoruz. Veriler ne gösteriyorsa o.
            # =====================================================
            
            # Poisson ve MC'nin ağırlıklı ortalaması (ham veri)
            final_odds['under_3_5'] = poisson_odds['under_3_5'] * 0.7 + mc_results['under_3_5_pct'] * 0.3
            final_odds['over_3_5'] = poisson_odds['over_3_5'] * 0.7 + mc_results['over_3_5_pct'] * 0.3
            
            # Sadece normalize et (toplam 100% olsun)
            total_goals_prob = final_odds['under_3_5'] + final_odds['over_3_5']
            if total_goals_prob > 0:
                final_odds['under_3_5'] = (final_odds['under_3_5'] / total_goals_prob) * 100
                final_odds['over_3_5'] = (final_odds['over_3_5'] / total_goals_prob) * 100
        else:
            final_odds = poisson_odds
        
        # Normalize 1X2
        total_1x2 = final_odds['home_win'] + final_odds['draw'] + final_odds['away_win']
        final_odds['home_win'] = round(final_odds['home_win'] / total_1x2 * 100, 1)
        final_odds['draw'] = round(final_odds['draw'] / total_1x2 * 100, 1)
        final_odds['away_win'] = round(final_odds['away_win'] / total_1x2 * 100, 1)
        
        # Under/Over normalize
        total_goals = final_odds['under_3_5'] + final_odds['over_3_5']
        final_odds['under_3_5'] = round(final_odds['under_3_5'] / total_goals * 100, 1)
        final_odds['over_3_5'] = round(final_odds['over_3_5'] / total_goals * 100, 1)
        
        # En olası skor
        likely_score, likely_prob = self.get_most_likely_score(score_probs)
        
        # Güven skoru (Monte Carlo varyansı da dahil)
        confidence = self.calculate_confidence(home_rating, away_rating, final_odds)
        
        # =====================================================
        # FAKTÖR KATKILARI - %100 VERİ BAZLI
        # =====================================================
        # Tüm tahminler gerçek maç verilerine dayanır.
        # Poisson/Monte Carlo veri değil, hesaplama aracıdır.
        # =====================================================
        
        factor_contributions = FactorContribution(
            # Sezon Performansı (%40)
            season_record=25.0,     # W-D-L kaydı
            goal_difference=15.0,   # Gol farkı
            
            # Son Maç Formu (%25)
            recent_form=15.0,       # Son 5-10 maç
            form_trend=10.0,        # Yükseliş/düşüş trendi
            
            # Ev/Deplasman (%15)
            home_performance=8.0,   # Evdeki performans
            away_performance=7.0,   # Deplasmandaki performans
            
            # Kafa Kafaya (%10)
            h2h_record=6.0,         # Geçmiş karşılaşmalar
            h2h_goals=4.0,          # Geçmiş gol farkı
            
            # Lig Faktörleri (%10)
            league_strength=6.0,    # Lig kalitesi
            home_advantage=4.0      # Lige özel ev avantajı
        )
        
        return MatchPrediction(
            home_team=home_team,
            away_team=away_team,
            home_expected_goals=home_xg,
            away_expected_goals=away_xg,
            home_win_prob=final_odds['home_win'],
            draw_prob=final_odds['draw'],
            away_win_prob=final_odds['away_win'],
            under_3_5_prob=final_odds['under_3_5'],
            over_3_5_prob=final_odds['over_3_5'],
            most_likely_score=likely_score,
            most_likely_score_prob=likely_prob,
            home_risk_factor=home_rating.risk_factor,
            away_risk_factor=away_rating.risk_factor,
            confidence=confidence,
            factor_contributions=factor_contributions
        )
    
    def predict_all_matches(self, matches_df: pd.DataFrame) -> List[MatchPrediction]:
        """Tüm maçlar için tahmin yap."""
        predictions = []
        
        for _, row in matches_df.iterrows():
            pred = self.predict_match(row)
            predictions.append(pred)
        
        return predictions


def predictions_to_dataframe(predictions: List[MatchPrediction]) -> pd.DataFrame:
    """Tahminleri DataFrame'e çevir."""
    data = []
    
    for p in predictions:
        data.append({
            'home_team': p.home_team,
            'away_team': p.away_team,
            'home_xg': p.home_expected_goals,
            'away_xg': p.away_expected_goals,
            'home_win_%': p.home_win_prob,
            'draw_%': p.draw_prob,
            'away_win_%': p.away_win_prob,
            'under_3.5_%': p.under_3_5_prob,
            'over_3.5_%': p.over_3_5_prob,
            'likely_score': f"{p.most_likely_score[0]}-{p.most_likely_score[1]}",
            'score_prob_%': p.most_likely_score_prob,
            'confidence': p.confidence,
            'home_risk': p.home_risk_factor,
            'away_risk': p.away_risk_factor
        })
    
    return pd.DataFrame(data)


def print_prediction(pred: MatchPrediction) -> None:
    """Tahmini güzel formatta yazdır."""
    print("\n" + "=" * 60)
    print(f"⚽ {pred.home_team} vs {pred.away_team}")
    print("=" * 60)
    
    # Beklenen goller
    print(f"\n📊 Beklenen Goller:")
    print(f"   {pred.home_team}: {pred.home_expected_goals} xG")
    print(f"   {pred.away_team}: {pred.away_expected_goals} xG")
    
    # 1X2 Olasılıkları
    print(f"\n🎯 Maç Sonucu Olasılıkları:")
    print(f"   Ev Sahibi Kazanır: %{pred.home_win_prob}")
    print(f"   Beraberlik:        %{pred.draw_prob}")
    print(f"   Deplasman Kazanır: %{pred.away_win_prob}")
    
    # Favori belirleme
    if pred.home_win_prob > pred.away_win_prob and pred.home_win_prob > pred.draw_prob:
        favorite = f"🏠 {pred.home_team}"
    elif pred.away_win_prob > pred.home_win_prob and pred.away_win_prob > pred.draw_prob:
        favorite = f"✈️ {pred.away_team}"
    else:
        favorite = "⚖️ Beraberlik"
    print(f"   Favori: {favorite}")
    
    # Gol Olasılıkları
    print(f"\n⚽ Toplam Gol Olasılıkları:")
    print(f"   0-3 Gol (Alt 3.5): %{pred.under_3_5_prob}")
    print(f"   4+ Gol (Üst 3.5):  %{pred.over_3_5_prob}")
    
    # En Olası Skor
    print(f"\n🎲 En Olası Skor:")
    print(f"   {pred.most_likely_score[0]}-{pred.most_likely_score[1]} (%{pred.most_likely_score_prob})")
    
    # Risk Faktörleri
    print(f"\n⚠️ Risk Faktörleri:")
    print(f"   {pred.home_team}: {'+' if pred.home_risk_factor > 0 else ''}{pred.home_risk_factor}")
    print(f"   {pred.away_team}: {'+' if pred.away_risk_factor > 0 else ''}{pred.away_risk_factor}")
    
    # Güven Skoru
    confidence_emoji = "🟢" if pred.confidence >= 60 else "🟡" if pred.confidence >= 40 else "🔴"
    print(f"\n{confidence_emoji} Tahmin Güveni: %{pred.confidence}")
    
    print("=" * 60)


def calculate_banko_score(row: dict) -> Tuple[float, str]:
    """
    Banko skoru hesapla.
    
    Banko Skoru = Kazanma Olasılığı × max(0-3 Gol, 4+ Gol) Olasılığı
    
    Returns:
        (banko_score, best_goal_bet)
    """
    # Favori ve kazanma olasılığı
    home_win = row['home_win_%']
    away_win = row['away_win_%']
    draw = row['draw_%']
    
    max_win = max(home_win, away_win, draw)
    
    # En iyi gol tahmini
    under = row['under_3.5_%']
    over = row['over_3.5_%']
    
    if under >= over:
        best_goal = under
        goal_bet = '0-3'
    else:
        best_goal = over
        goal_bet = '4+'
    
    # Banko skoru
    banko_score = (max_win / 100) * (best_goal / 100) * 100
    
    return banko_score, goal_bet


def get_match_status(row: dict) -> str:
    """Maç durumunu belirle (BANKO, Yüksek Güvenli, Normal)."""
    home_win = row['home_win_%']
    away_win = row['away_win_%']
    max_win = max(home_win, away_win)
    
    under = row['under_3.5_%']
    over = row['over_3.5_%']
    max_goal = max(under, over)
    
    if max_win >= 70 and max_goal >= 65:
        return '🔥 Yüksek Güvenli'
    return ''


def print_analysis_table(predictions_df: pd.DataFrame, matches_df: pd.DataFrame) -> None:
    """
    Şık tablo formatında analiz çıktısı.
    """
    if predictions_df.empty:
        print("⚠️ Gösterilecek tahmin yok.")
        return
    
    # Lig bilgisini ekle
    if 'league' in matches_df.columns:
        predictions_df = predictions_df.copy()
        predictions_df['league'] = matches_df['league'].values
    else:
        predictions_df['league'] = 'N/A'
    
    # Banko skorlarını hesapla
    banko_scores = []
    goal_bets = []
    favorites = []
    win_probs = []
    statuses = []
    
    for _, row in predictions_df.iterrows():
        score, goal_bet = calculate_banko_score(row)
        banko_scores.append(score)
        goal_bets.append(goal_bet)
        
        # Favori belirleme
        if row['home_win_%'] > row['away_win_%'] and row['home_win_%'] > row['draw_%']:
            favorites.append(row['home_team'])
            win_probs.append(row['home_win_%'])
        elif row['away_win_%'] > row['home_win_%'] and row['away_win_%'] > row['draw_%']:
            favorites.append(row['away_team'])
            win_probs.append(row['away_win_%'])
        else:
            favorites.append('Beraberlik')
            win_probs.append(row['draw_%'])
        
        statuses.append(get_match_status(row))
    
    predictions_df['banko_score'] = banko_scores
    predictions_df['goal_bet'] = goal_bets
    predictions_df['favorite'] = favorites
    predictions_df['win_prob'] = win_probs
    predictions_df['status'] = statuses
    
    # Banko maçı bul
    banko_idx = predictions_df['banko_score'].idxmax()
    predictions_df.loc[banko_idx, 'status'] = '🏆 HAFTANIN BANKOSU'
    
    # Tablo genişliği
    W = 100
    
    # Tablo başlığı
    print("\n")
    print("╔" + "═" * W + "╗")
    title = "🔮 HAFTALIK MAÇ ANALİZİ 🔮"
    print("║" + title.center(W) + "║")
    print("╠" + "═" * W + "╣")
    
    # Sütun başlıkları
    header = "║ {:^28} │ {:^14} │ {:^14} │ {:^9} │ {:^9} │ {:^9} ║"
    print(header.format("MAÇ", "LİG", "FAVORİ", "KAZAN %", "0-3 GOL %", "4+ GOL %"))
    print("╠" + "═" * W + "╣")
    
    row_format = "║ {:^28} │ {:^14} │ {:^14} │ {:^9.1f} │ {:^9.1f} │ {:^9.1f} ║"
    
    # Önce BANKO'yu yazdır
    banko_row = predictions_df.loc[banko_idx]
    match_str = f"{banko_row['home_team'][:12]}  vs  {banko_row['away_team'][:12]}"
    league_str = banko_row['league'].replace('ENG-', '').replace('ESP-', '').replace('ITA-', '').replace('GER-', '').replace('FRA-', '')[:14]
    
    banko_title = "🏆 HAFTANIN BANKOSU 🏆"
    print("║" + banko_title.center(W) + "║")
    print("║" + "─" * W + "║")
    
    print(row_format.format(
        match_str,
        league_str,
        banko_row['favorite'][:14],
        banko_row['win_prob'],
        banko_row['under_3.5_%'],
        banko_row['over_3.5_%']
    ))
    
    # Banko detayları
    goal_rec = f"{'0-3 Gol' if banko_row['goal_bet'] == '0-3' else '4+ Gol'} önerisi"
    banko_info = f"⭐ Banko Skoru: {banko_row['banko_score']:.1f}  |  {goal_rec}"
    print("║" + banko_info.center(W) + "║")
    
    print("╠" + "═" * W + "╣")
    
    # Yüksek Güvenli maçlar
    high_conf = predictions_df[(predictions_df['status'] == '🔥 Yüksek Güvenli') & (predictions_df.index != banko_idx)]
    if not high_conf.empty:
        hc_title = "🔥 YÜKSEK GÜVENLİ MAÇLAR 🔥"
        print("║" + hc_title.center(W) + "║")
        print("║" + "─" * W + "║")
        
        for _, row in high_conf.iterrows():
            match_str = f"{row['home_team'][:12]}  vs  {row['away_team'][:12]}"
            league_str = row['league'].replace('ENG-', '').replace('ESP-', '').replace('ITA-', '').replace('GER-', '').replace('FRA-', '')[:14]
            print(row_format.format(
                match_str,
                league_str,
                row['favorite'][:14],
                row['win_prob'],
                row['under_3.5_%'],
                row['over_3.5_%']
            ))
        
        print("╠" + "═" * W + "╣")
    
    # Diğer maçlar
    other_matches = predictions_df[(predictions_df['status'] != '🏆 HAFTANIN BANKOSU') & 
                                    (predictions_df['status'] != '🔥 Yüksek Güvenli')]
    
    if not other_matches.empty:
        other_title = "📋 DİĞER MAÇLAR"
        print("║" + other_title.center(W) + "║")
        print("║" + "─" * W + "║")
        
        # Banko skoruna göre sırala
        other_matches = other_matches.sort_values('banko_score', ascending=False)
        
        for _, row in other_matches.iterrows():
            match_str = f"{row['home_team'][:12]}  vs  {row['away_team'][:12]}"
            league_str = row['league'].replace('ENG-', '').replace('ESP-', '').replace('ITA-', '').replace('GER-', '').replace('FRA-', '')[:14]
            print(row_format.format(
                match_str,
                league_str,
                row['favorite'][:14],
                row['win_prob'],
                row['under_3.5_%'],
                row['over_3.5_%']
            ))
    
    # Alt bilgi
    print("╠" + "═" * W + "╣")
    footer1 = "📌 Banko Skoru = Kazanma% × Gol Aralığı%"
    footer2 = "🔥 Yüksek Güvenli = Kazanma >70% & Gol >65%"
    print("║" + footer1.center(W) + "║")
    print("║" + footer2.center(W) + "║")
    print("╚" + "═" * W + "╝")


def run_predictions(matches_df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Ana tahmin fonksiyonu.
    
    Args:
        matches_df: Maç verileri DataFrame'i
        verbose: Detaylı çıktı göster
    
    Returns:
        Tahminleri içeren DataFrame
    """
    if matches_df.empty:
        print("⚠️ Tahmin yapılacak maç yok.")
        return pd.DataFrame()
    
    if verbose:
        print("\n" + "=" * 60)
        print("🔮 MAÇ TAHMİN MOTORU")
        print("=" * 60)
        print("📈 Algoritma: Poisson Dağılımı + Güç Puanı")
        print(f"📊 Analiz edilecek maç sayısı: {len(matches_df)}")
        print("=" * 60)
    
    # Tahmin motoru
    predictor = MatchPredictor()
    
    # Tüm tahminler
    predictions = predictor.predict_all_matches(matches_df)
    
    # DataFrame'e çevir
    predictions_df = predictions_to_dataframe(predictions)
    
    # Şık tablo çıktısı
    if verbose:
        print_analysis_table(predictions_df, matches_df)
    
    return predictions_df


# Ana çalıştırma
if __name__ == "__main__":
    from data_fetcher import fetch_all_data
    
    # Veri çek
    print("📊 Veriler çekiliyor...")
    matches_df = fetch_all_data(
        leagues=['ENG-Premier League'],
        days_ahead=7,
        verbose=True
    )
    
    if not matches_df.empty:
        # Tahmin yap
        predictions_df = run_predictions(matches_df, verbose=True)
        
        # Kaydet
        predictions_df.to_csv('predictions.csv', index=False)
        print("\n💾 Tahminler predictions.csv dosyasına kaydedildi.")
