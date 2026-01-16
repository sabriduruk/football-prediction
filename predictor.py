"""
Futbol Maç Tahmin Modülü
========================
Poisson dağılımı ve güç puanı hesaplaması ile maç sonucu tahmini.

Algoritma:
1. Güç Puanı: Takımların son 5 maçtaki form ve xG performansına göre
   Hücum ve Savunma rating'i hesapla.
2. Poisson Dağılımı: Rating'leri kullanarak muhtemel skorları simüle et.
3. Olasılık Hesaplama: 1X2, 0-3 gol, 4+ gol olasılıkları.
4. Risk/Ödül Çarpanı: Kırmızı kart ve penaltı sıklığına göre ayarlama.
"""

import numpy as np
import pandas as pd
from scipy.stats import poisson
from typing import Dict, Tuple, List, Any
from dataclasses import dataclass


@dataclass
class TeamRating:
    """Takım güç puanı."""
    attack: float      # Hücum gücü
    defense: float     # Savunma gücü
    form: float        # Son maç formu (0-1)
    risk_factor: float # Risk faktörü (kart, penaltı)


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


class MatchPredictor:
    """
    Hibrit Maç Tahmin Motoru
    ========================
    - Poisson Dağılımı: Temel gol olasılıkları
    - Dixon-Coles Düzeltmesi: Düşük skorlu maçlar için korelasyon
    - Monte Carlo Simülasyonu: Belirsizlik ve güven aralığı
    """
    
    # Lig ortalamaları (referans değerler)
    LEAGUE_AVG_GOALS = 2.7
    HOME_ADVANTAGE = 1.15
    
    # xG ağırlıkları
    XG_WEIGHT = 0.6
    ACTUAL_GOALS_WEIGHT = 0.4
    
    # Dixon-Coles rho parametresi (düşük skor korelasyonu)
    DIXON_COLES_RHO = 0.03
    
    # Monte Carlo simülasyon sayısı
    MONTE_CARLO_SIMS = 5000
    
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
    
    def get_team_rating(self, match_row: pd.Series, team: str = 'home') -> TeamRating:
        """Takım rating'ini hesapla."""
        prefix = f'{team}_'
        
        # Son 5 maç verileri
        avg_goals = match_row.get(f'{prefix}last5_avg_goals', 1.0)
        avg_conceded = match_row.get(f'{prefix}last5_avg_conceded', 1.0)
        avg_xg = match_row.get(f'{prefix}last5_avg_xg', avg_goals)
        avg_xg_against = match_row.get(f'{prefix}last5_avg_xg_against', avg_conceded)
        form_points = match_row.get(f'{prefix}last5_form_points', 7)
        
        # Sezon verileri (risk faktörü için)
        red_cards = match_row.get(f'{prefix}season_red', 0)
        pk_won = match_row.get(f'{prefix}season_pk_won', 0)
        
        # Rating hesapla
        attack = self.calculate_attack_rating(avg_goals, avg_xg, form_points)
        defense = self.calculate_defense_rating(avg_conceded, avg_xg_against, form_points)
        form = form_points / 15.0  # Normalize (0-1)
        risk = self.calculate_risk_factor(red_cards, pk_won)
        
        return TeamRating(
            attack=attack,
            defense=defense,
            form=form,
            risk_factor=risk
        )
    
    def calculate_expected_goals(
        self,
        home_rating: TeamRating,
        away_rating: TeamRating
    ) -> Tuple[float, float]:
        """
        Beklenen gol sayısını hesapla.
        
        Ev Sahibi xG = Ev Hücum * Deplasman Savunma (ters) * Lig Ort * Ev Avantajı
        """
        # Temel beklenen goller
        home_xg = (home_rating.attack * 
                   (1 / away_rating.defense) * 
                   self.avg_goals_per_team * 
                   self.HOME_ADVANTAGE)
        
        away_xg = (away_rating.attack * 
                   (1 / home_rating.defense) * 
                   self.avg_goals_per_team)
        
        # Risk faktörü uygula
        home_xg *= (1 + home_rating.risk_factor - away_rating.risk_factor * 0.5)
        away_xg *= (1 + away_rating.risk_factor - home_rating.risk_factor * 0.5)
        
        # Minimum ve maksimum sınırları
        home_xg = max(0.3, min(4.5, home_xg))
        away_xg = max(0.2, min(4.0, away_xg))
        
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
        
        # Takım rating'leri
        home_rating = self.get_team_rating(match_row, 'home')
        away_rating = self.get_team_rating(match_row, 'away')
        
        # Beklenen goller
        home_xg, away_xg = self.calculate_expected_goals(home_rating, away_rating)
        
        # 1. Poisson + Dixon-Coles
        score_probs = self.calculate_score_probabilities(home_xg, away_xg, use_dixon_coles=True)
        poisson_odds = self.calculate_match_odds(score_probs)
        
        # 2. Monte Carlo simülasyonu
        if use_monte_carlo:
            mc_results = self.monte_carlo_simulation(home_xg, away_xg)
            
            # Hibrit sonuç: Poisson %60 + Monte Carlo %40
            POISSON_WEIGHT = 0.6
            MC_WEIGHT = 0.4
            
            final_odds = {
                'home_win': poisson_odds['home_win'] * POISSON_WEIGHT + mc_results['home_win_pct'] * MC_WEIGHT,
                'draw': poisson_odds['draw'] * POISSON_WEIGHT + mc_results['draw_pct'] * MC_WEIGHT,
                'away_win': poisson_odds['away_win'] * POISSON_WEIGHT + mc_results['away_win_pct'] * MC_WEIGHT,
                'under_3_5': poisson_odds['under_3_5'] * POISSON_WEIGHT + mc_results['under_3_5_pct'] * MC_WEIGHT,
                'over_3_5': poisson_odds['over_3_5'] * POISSON_WEIGHT + mc_results['over_3_5_pct'] * MC_WEIGHT,
            }
        else:
            final_odds = poisson_odds
        
        # Normalize
        total_1x2 = final_odds['home_win'] + final_odds['draw'] + final_odds['away_win']
        final_odds['home_win'] = round(final_odds['home_win'] / total_1x2 * 100, 1)
        final_odds['draw'] = round(final_odds['draw'] / total_1x2 * 100, 1)
        final_odds['away_win'] = round(final_odds['away_win'] / total_1x2 * 100, 1)
        final_odds['under_3_5'] = round(final_odds['under_3_5'], 1)
        final_odds['over_3_5'] = round(final_odds['over_3_5'], 1)
        
        # En olası skor
        likely_score, likely_prob = self.get_most_likely_score(score_probs)
        
        # Güven skoru (Monte Carlo varyansı da dahil)
        confidence = self.calculate_confidence(home_rating, away_rating, final_odds)
        
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
            confidence=confidence
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
