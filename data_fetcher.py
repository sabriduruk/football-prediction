"""
Futbol Veri Cekme Modulu
========================
SofaScore API (API key gerektirmez) + ESPN
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta, datetime
from typing import Optional, List, Dict, Any, Tuple
import pytz
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import warnings

warnings.filterwarnings('ignore')

# SofaScore API
SOFASCORE_API = "https://api.sofascore.com/api/v1"

# LIGLER - SofaScore tournament ID'leri
SOFASCORE_LEAGUES = {
    17: ('ENG-Premier League', 'Ingiltere Premier League'),
    8: ('ESP-La Liga', 'Ispanya La Liga'),
    23: ('ITA-Serie A', 'Italya Serie A'),
    35: ('GER-Bundesliga', 'Almanya Bundesliga'),
    34: ('FRA-Ligue 1', 'Fransa Ligue 1'),
    52: ('TUR-Super Lig', 'Turkiye Super Lig'),
    238: ('POR-Primeira Liga', 'Portekiz Primeira Liga'),
    37: ('NED-Eredivisie', 'Hollanda Eredivisie'),
    144: ('BEL-Pro League', 'Belcika Pro League'),
    7: ('INT-Champions League', 'UEFA Sampiyonlar Ligi'),
    679: ('INT-Europa League', 'UEFA Avrupa Ligi'),
    17015: ('INT-Conference League', 'UEFA Konferans Ligi'),
}

# ESPN yedek
ESPN_LEAGUES = {
    'TUR-Super Lig': ('tur.1', 'Turkiye Super Lig'),
    'BEL-Pro League': ('bel.1', 'Belcika Pro League'),
    'INT-Champions League': ('uefa.champions', 'UEFA Sampiyonlar Ligi'),
    'INT-Europa League': ('uefa.europa', 'UEFA Avrupa Ligi'),
    'INT-Conference League': ('uefa.europa.conf', 'UEFA Konferans Ligi'),
    'ENG-Premier League': ('eng.1', 'Ingiltere Premier League'),
    'ESP-La Liga': ('esp.1', 'Ispanya La Liga'),
    'ITA-Serie A': ('ita.1', 'Italya Serie A'),
    'GER-Bundesliga': ('ger.1', 'Almanya Bundesliga'),
    'FRA-Ligue 1': ('fra.1', 'Fransa Ligue 1'),
    'POR-Primeira Liga': ('por.1', 'Portekiz Primeira Liga'),
    'KSA-Pro League': ('ksa.1', 'Suudi Arabistan Pro League'),
}

TURKEY_TZ = pytz.timezone('Europe/Istanbul')
UTC_TZ = pytz.UTC

# Tum ligler
ALL_LEAGUES = list(ESPN_LEAGUES.keys())
SUPPORTED_LEAGUES = ALL_LEAGUES

# CACHE
_team_stats_cache: Dict[str, Dict] = {}
_h2h_cache: Dict[str, Dict] = {}  # Head-to-Head cache
_home_away_cache: Dict[str, Dict] = {}  # Ev/Deplasman cache


def clear_cache():
    """Tum cache'i temizle."""
    global _team_stats_cache, _h2h_cache, _home_away_cache
    _team_stats_cache.clear()
    _h2h_cache.clear()
    _home_away_cache.clear()
    print("[CACHE] Onbellek temizlendi")


def fetch_team_home_away_stats(team_id: str, league_code: str) -> Dict:
    """
    Takımın ev/deplasman ayrımlı istatistiklerini ve son maç sonuçlarını çek.
    
    Returns:
        {
            'home_wins': int, 'home_losses': int, 'home_draws': int,
            'home_goals': int, 'home_conceded': int, 'home_played': int,
            'away_wins': int, 'away_losses': int, 'away_draws': int,
            'away_goals': int, 'away_conceded': int, 'away_played': int,
            'recent_form': ['W', 'D', 'L', ...],  # Son 5 maç (eski->yeni)
            'recent_goals': [2, 1, 0, ...],
            'recent_conceded': [0, 1, 2, ...]
        }
    """
    global _home_away_cache
    
    # Cache kontrolü
    cache_key = f"{team_id}_{league_code}"
    if cache_key in _home_away_cache:
        return _home_away_cache[cache_key]
    
    # team_id yoksa boş dön
    if not team_id:
        return {}
    
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/teams/{team_id}"
        resp = requests.get(url, timeout=5)  # Timeout 10s -> 5s
        
        if resp.status_code != 200:
            return {}
        
        data = resp.json()
        team_data = data.get('team', {})
        record = team_data.get('record', {})
        items = record.get('items', [])
        
        result = {
            'recent_form': [],
            'recent_goals': [],
            'recent_conceded': []
        }
        
        if not items:
            return result
        
        # Stats'ları dict'e çevir
        stats_dict = {}
        for item in items:
            for stat in item.get('stats', []):
                stats_dict[stat['name']] = stat.get('value', 0)
        
        result.update({
            'home_wins': int(stats_dict.get('homeWins', 0)),
            'home_losses': int(stats_dict.get('homeLosses', 0)),
            'home_draws': int(stats_dict.get('homeTies', 0)),
            'home_goals': int(stats_dict.get('homePointsFor', 0)),
            'home_conceded': int(stats_dict.get('homePointsAgainst', 0)),
            'home_played': int(stats_dict.get('homeGamesPlayed', 0)),
            'away_wins': int(stats_dict.get('awayWins', 0)),
            'away_losses': int(stats_dict.get('awayLosses', 0)),
            'away_draws': int(stats_dict.get('awayTies', 0)),
            'away_goals': int(stats_dict.get('awayPointsFor', 0)),
            'away_conceded': int(stats_dict.get('awayPointsAgainst', 0)),
            'away_played': int(stats_dict.get('awayGamesPlayed', 0)),
        })
        
        # Form tahmini: W-D-L kaydından son 5 maç simülasyonu
        # ESPN API son maç detaylarını vermiyor, ama W-D-L oranına göre form tahmin edebiliriz
        try:
            total_played = result.get('home_played', 0) + result.get('away_played', 0)
            total_wins = result.get('home_wins', 0) + result.get('away_wins', 0)
            total_draws = result.get('home_draws', 0) + result.get('away_draws', 0)
            total_losses = result.get('home_losses', 0) + result.get('away_losses', 0)
            total_goals = result.get('home_goals', 0) + result.get('away_goals', 0)
            total_conceded = result.get('home_conceded', 0) + result.get('away_conceded', 0)
            
            if total_played >= 5:
                # W-D-L oranına göre son 5 maç simülasyonu
                win_rate = total_wins / total_played
                draw_rate = total_draws / total_played
                loss_rate = total_losses / total_played
                
                # Rastgele değil, orana göre dağıt
                # Örnek: %60 win, %20 draw, %20 loss -> [W, W, W, D, L]
                simulated_form = []
                wins_to_add = round(win_rate * 5)
                draws_to_add = round(draw_rate * 5)
                losses_to_add = 5 - wins_to_add - draws_to_add
                
                # Son maçlara galibiyet ağırlığı ver (yükseliş etkisi)
                for _ in range(max(0, losses_to_add)):
                    simulated_form.append('L')
                for _ in range(max(0, draws_to_add)):
                    simulated_form.append('D')
                for _ in range(max(0, wins_to_add)):
                    simulated_form.append('W')
                
                # Gol ortalamaları
                avg_goals = total_goals / total_played if total_played > 0 else 1.0
                avg_conceded = total_conceded / total_played if total_played > 0 else 1.0
                
                simulated_goals = [round(avg_goals)] * 5
                simulated_conceded = [round(avg_conceded)] * 5
                
                result['recent_form'] = simulated_form[-5:]
                result['recent_goals'] = simulated_goals
                result['recent_conceded'] = simulated_conceded
                
                # Ekstra: Form puanı hesapla (trend için)
                # Galibiyet oranı yüksekse pozitif trend
                result['form_momentum'] = round((win_rate - 0.33) * 3, 2)  # -1 ile +2 arası
        except:
            pass
        
        # Cache'e kaydet
        _home_away_cache[cache_key] = result
        return result
        
    except Exception as e:
        return {}


def fetch_head_to_head(event_id: str, league_code: str) -> Dict:
    """
    ESPN'den kafa kafaya (H2H) verisi cek.
    
    Returns:
        {
            'total_matches': int,
            'home_wins': int,
            'away_wins': int,
            'draws': int,
            'home_goals': int,
            'away_goals': int,
            'last_5_results': list  # ['W', 'L', 'D', ...]
        }
    """
    global _h2h_cache
    
    cache_key = f"{event_id}"
    if cache_key in _h2h_cache:
        return _h2h_cache[cache_key]
    
    if not event_id:
        return {}
    
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/summary?event={event_id}"
        resp = requests.get(url, timeout=5)  # Timeout 10s -> 5s
        
        if resp.status_code != 200:
            return {}
        
        data = resp.json()
        h2h_games = data.get('headToHeadGames', [])
        
        if not h2h_games:
            return {}
        
        # İlk takım perspektifinden (W = ev sahibi kazandı bu maçta)
        team1_data = h2h_games[0]
        team1_events = team1_data.get('events', [])[:10]  # Son 10 maç
        
        if not team1_events:
            return {}
        
        h2h_stats = {
            'total_matches': len(team1_events),
            'home_wins': 0,  # Ev sahibi takımın galibiyetleri
            'away_wins': 0,  # Deplasman takımının galibiyetleri
            'draws': 0,
            'home_goals': 0,
            'away_goals': 0,
            'last_5_results': []
        }
        
        for event in team1_events:
            result = event.get('gameResult', '')  # W/L/D (takım perspektifinden)
            home_score = int(event.get('homeTeamScore', 0) or 0)
            away_score = int(event.get('awayTeamScore', 0) or 0)
            
            # gameResult takımın kazanıp kaybettiğini gösterir
            # W = bu takım (ev sahibi) kazandı, L = kaybetti, D = beraberlik
            if result == 'W':
                h2h_stats['home_wins'] += 1
            elif result == 'L':
                h2h_stats['away_wins'] += 1
            elif result == 'D':
                h2h_stats['draws'] += 1
            
            h2h_stats['home_goals'] += home_score
            h2h_stats['away_goals'] += away_score
            
            if len(h2h_stats['last_5_results']) < 5:
                h2h_stats['last_5_results'].append(result)
        
        _h2h_cache[cache_key] = h2h_stats
        return h2h_stats
        
    except Exception as e:
        return {}


def get_week_range() -> Tuple[date, date]:
    """Hafta araligi: Bugun - Gelecek Sali"""
    today = date.today()
    weekday = today.weekday()
    
    days_until_tuesday = (1 - weekday) % 7
    if days_until_tuesday == 0:
        days_until_tuesday = 7
    
    end_date = today + timedelta(days=days_until_tuesday)
    return today, end_date


def format_turkey_datetime(dt) -> str:
    if dt is None or pd.isna(dt):
        return ""
    try:
        if isinstance(dt, str):
            dt = pd.to_datetime(dt)
        if dt.tzinfo is None:
            dt = UTC_TZ.localize(dt)
        turkey_dt = dt.astimezone(TURKEY_TZ)
        return turkey_dt.strftime('%d/%m %H:%M')
    except:
        return str(dt)[:16] if dt else ""


def fetch_sofascore_events(tournament_id: int, verbose: bool = True) -> Tuple[pd.DataFrame, Dict[str, Dict]]:
    """SofaScore'dan mac ve takim verisi cek."""
    
    league_info = SOFASCORE_LEAGUES.get(tournament_id)
    if not league_info:
        return pd.DataFrame(), {}
    
    league_key, display_name = league_info
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
    }
    
    try:
        # Bugunun maclari ve gelecek maclar
        start_date, end_date = get_week_range()
        
        matches = []
        team_stats = {}
        
        # Her gun icin mac cek
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            url = f"{SOFASCORE_API}/sport/football/scheduled-events/{date_str}"
            
            try:
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code != 200:
                    current_date += timedelta(days=1)
                    continue
                
                data = response.json()
                events = data.get('events', [])
                
                for event in events:
                    try:
                        # Turnuva kontrolu
                        tournament = event.get('tournament', {})
                        if tournament.get('uniqueTournament', {}).get('id') != tournament_id:
                            continue
                        
                        # Mac durumu (sadece oynanmamis)
                        status = event.get('status', {}).get('type', '')
                        if status in ['finished', 'canceled', 'postponed']:
                            continue
                        
                        home_team = event.get('homeTeam', {}).get('name', '')
                        away_team = event.get('awayTeam', {}).get('name', '')
                        
                        if not home_team or not away_team:
                            continue
                        
                        # Unix timestamp -> datetime
                        start_ts = event.get('startTimestamp', 0)
                        match_date = datetime.utcfromtimestamp(start_ts)
                        match_date = UTC_TZ.localize(match_date)
                        
                        matches.append({
                            'match_date': match_date,
                            'league': league_key,
                            'league_display': display_name,
                            'home_team': home_team,
                            'away_team': away_team,
                            'source': 'SofaScore'
                        })
                        
                        # Takim istatistikleri (varsa)
                        for team_data, team_name in [
                            (event.get('homeTeam', {}), home_team),
                            (event.get('awayTeam', {}), away_team)
                        ]:
                            if team_name not in team_stats:
                                # SofaScore'dan form verisi al
                                team_id = team_data.get('id')
                                if team_id:
                                    try:
                                        form_url = f"{SOFASCORE_API}/team/{team_id}/performance"
                                        form_resp = requests.get(form_url, headers=headers, timeout=10)
                                        if form_resp.status_code == 200:
                                            form_data = form_resp.json()
                                            
                                            # Form puani
                                            form = form_data.get('form', [])
                                            form_points = sum(3 if f == 'W' else 1 if f == 'D' else 0 for f in form[-5:])
                                            
                                            # Gol ortalamasi
                                            scored = form_data.get('goalsScored', 0)
                                            conceded = form_data.get('goalsConceded', 0)
                                            played = form_data.get('matchesPlayed', 1) or 1
                                            
                                            team_stats[team_name] = {
                                                'avg_goals': round(scored / played, 2),
                                                'avg_conceded': round(conceded / played, 2),
                                                'avg_xg': round(scored / played, 2),
                                                'avg_xga': round(conceded / played, 2),
                                                'form_points': form_points,
                                                'matches': played
                                            }
                                        time.sleep(0.1)
                                    except:
                                        pass
                    except:
                        continue
                        
            except Exception as e:
                pass
            
            current_date += timedelta(days=1)
            time.sleep(0.2)
        
        if matches:
            if verbose:
                print(f"   + {display_name}: {len(matches)} mac")
            return pd.DataFrame(matches), team_stats
        else:
            if verbose:
                print(f"   - {display_name}: mac yok")
            return pd.DataFrame(), team_stats
        
    except Exception as e:
        if verbose:
            print(f"   ! {display_name}: Hata")
        return pd.DataFrame(), {}


def fetch_espn_single(league_key: str, league_info: tuple, start_date: date, end_date: date) -> Tuple[pd.DataFrame, Dict]:
    """ESPN'den tek lig verisi cek."""
    espn_code, display_name = league_info
    
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{espn_code}/scoreboard"
        params = {
            'dates': f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}",
            'limit': 100
        }
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        events = data.get('events', [])
        if not events:
            return pd.DataFrame(), {}
        
        matches = []
        team_stats = {}
        
        for event in events:
            try:
                competition = event.get('competitions', [{}])[0]
                competitors = competition.get('competitors', [])
                
                if len(competitors) != 2:
                    continue
                
                home_team = away_team = None
                home_record = away_record = None
                home_team_id = away_team_id = None
                
                for comp in competitors:
                    team_data = comp.get('team', {})
                    team_name = team_data.get('displayName', '')
                    team_id = team_data.get('id', '')
                    records = comp.get('records', [])
                    record = records[0] if records else {}
                    
                    if comp.get('homeAway') == 'home':
                        home_team = team_name
                        home_record = record
                        home_team_id = team_id
                    else:
                        away_team = team_name
                        away_record = record
                        away_team_id = team_id
                
                if not home_team or not away_team:
                    continue
                
                match_date = pd.to_datetime(event.get('date'))
                status = competition.get('status', {}).get('type', {}).get('name', '')
                
                if status in ['STATUS_FINAL', 'STATUS_FULL_TIME', 'STATUS_POSTPONED']:
                    continue
                
                # Event ID - H2H icin lazim
                event_id = event.get('id', '')
                
                matches.append({
                    'match_date': match_date,
                    'league': league_key,
                    'league_display': display_name,
                    'home_team': home_team,
                    'away_team': away_team,
                    'source': 'ESPN',
                    'event_id': event_id,
                    'espn_code': espn_code,
                    'home_team_id': home_team_id,
                    'away_team_id': away_team_id
                })
                
                # Takim istatistikleri (ESPN records'dan)
                for team_name, record in [(home_team, home_record), (away_team, away_record)]:
                    if team_name and record:
                        try:
                            # "W-D-L" formatinda (ornek: "10-5-3")
                            summary = record.get('summary', '0-0-0')
                            parts = summary.split('-')
                            if len(parts) >= 3:
                                wins = int(parts[0])
                                draws = int(parts[1])
                                losses = int(parts[2])
                                played = wins + draws + losses
                                
                                if played > 0:
                                    # Lig ortalamasina gore tahmin
                                    attack_factor = 1.0 + (wins - losses) / (played * 2)
                                    defense_factor = 1.0 - (wins - losses) / (played * 2)
                                    
                                    new_stats = {
                                        'avg_goals': round(1.35 * attack_factor, 2),
                                        'avg_conceded': round(1.2 * defense_factor, 2),
                                        'avg_xg': round(1.35 * attack_factor, 2),
                                        'avg_xga': round(1.2 * defense_factor, 2),
                                        'form_points': min(wins * 3 + draws, 15),
                                        'matches': played
                                    }
                                    
                                    # Eger takim yoksa veya yeni kayit daha fazla mac iceriyorsa guncelle
                                    # (Lig mac sayisi > UEFA mac sayisi, bu yuzden lig verileri oncelikli)
                                    if team_name not in team_stats or played > team_stats[team_name].get('matches', 0):
                                        team_stats[team_name] = new_stats
                        except:
                            pass
            except:
                continue
        
        return pd.DataFrame(matches), team_stats
        
    except:
        return pd.DataFrame(), {}


def fetch_all_data(
    leagues: Optional[List[str]] = None,
    seasons: Optional[List[str]] = None,
    days_ahead: int = 7,
    last_n_matches: int = 10,
    verbose: bool = True
) -> pd.DataFrame:
    """Ana veri cekme fonksiyonu."""
    global _team_stats_cache
    
    start_date, end_date = get_week_range()
    
    if verbose:
        print("=" * 50)
        print("FUTBOL VERI CEKME")
        print(f"Tarih: {start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')}")
        print("=" * 50)
    
    all_fixtures = []
    team_stats = {}
    
    # ESPN'den tum ligleri cek (daha hizli ve guvenilir)
    if verbose:
        print(f"\n[ESPN] {len(ESPN_LEAGUES)} lig...")
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(fetch_espn_single, key, info, start_date, end_date): key 
            for key, info in ESPN_LEAGUES.items()
        }
        
        for future in as_completed(futures):
            league_key = futures[future]
            try:
                df, stats = future.result()
                if not df.empty:
                    all_fixtures.append(df)
                    display_name = ESPN_LEAGUES[league_key][1]
                    if verbose:
                        print(f"   + {display_name}: {len(df)} mac, {len(stats)} takim")
                    team_stats.update(stats)
                else:
                    if verbose:
                        display_name = ESPN_LEAGUES[league_key][1]
                        print(f"   - {display_name}: mac yok")
            except:
                pass
    
    # Birlestir
    if not all_fixtures:
        if verbose:
            print("\nBu hafta mac yok!")
        return pd.DataFrame()
    
    matches_df = pd.concat(all_fixtures, ignore_index=True)
    
    # Tarih filtresi - gecmis maclari cikar
    today_start = pd.Timestamp.now(tz='UTC').normalize()
    matches_df['match_date'] = pd.to_datetime(matches_df['match_date'], utc=True)
    matches_df = matches_df[matches_df['match_date'] >= today_start].copy()
    
    if matches_df.empty:
        if verbose:
            print("\nBu hafta mac yok!")
        return pd.DataFrame()
    
    if verbose:
        print(f"\n[TOPLAM] {len(matches_df)} mac, {len(team_stats)} takim istatistigi")
    
    # Turkiye saati ekle
    matches_df['turkey_time'] = matches_df['match_date'].apply(format_turkey_datetime)
    matches_df = matches_df.sort_values(['match_date', 'league']).reset_index(drop=True)
    
    # Cache guncelle
    _team_stats_cache.update(team_stats)
    
    if verbose:
        print(f"\n{len(matches_df)} mac isleniyor...")
    
    # Istatistikleri ekle
    default_stats = {
        'avg_goals': 1.35, 'avg_conceded': 1.2,
        'avg_xg': 1.35, 'avg_xga': 1.2,
        'form_points': 7, 'matches': 10
    }
    
    # Ev/Deplasman istatistiklerini topla
    home_away_stats_cache = {}
    
    # Benzersiz takım-lig çiftlerini topla
    team_league_pairs = set()
    for _, fixture in matches_df.iterrows():
        espn_code = fixture.get('espn_code', '')
        home_team_id = fixture.get('home_team_id', '')
        away_team_id = fixture.get('away_team_id', '')
        home_team = fixture.get('home_team', '')
        away_team = fixture.get('away_team', '')
        
        if espn_code and home_team_id:
            team_league_pairs.add((home_team, home_team_id, espn_code))
        if espn_code and away_team_id:
            team_league_pairs.add((away_team, away_team_id, espn_code))
    
    # Cache'den zaten var olanları çıkar
    pairs_to_fetch = []
    for pair in team_league_pairs:
        team_name, team_id, league_code = pair
        cache_key = f"{team_id}_{league_code}"
        if cache_key in _home_away_cache:
            # Cache'den al
            home_away_stats_cache[team_name] = _home_away_cache[cache_key]
        else:
            pairs_to_fetch.append(pair)
    
    if verbose:
        cached = len(team_league_pairs) - len(pairs_to_fetch)
        print(f"\n[EV/DEPLASMAN] {len(pairs_to_fetch)} takim icin veri cekilecek ({cached} cache'den)")
    
    # Paralel olarak ev/deplasman istatistiklerini çek (arttırılmış worker sayısı)
    def fetch_ha_stats(args):
        team_name, team_id, league_code = args
        stats = fetch_team_home_away_stats(team_id, league_code)
        return team_name, stats
    
    if pairs_to_fetch:
        # max_workers artırıldı: 10 -> 25 (daha hızlı)
        with ThreadPoolExecutor(max_workers=25) as executor:
            futures = [executor.submit(fetch_ha_stats, pair) for pair in pairs_to_fetch]
            completed = 0
            for future in as_completed(futures):
                try:
                    team_name, stats = future.result()
                    if stats:
                        home_away_stats_cache[team_name] = stats
                    completed += 1
                    # Her 20 takımda bir ilerleme göster
                    if verbose and completed % 20 == 0:
                        print(f"   ... {completed}/{len(pairs_to_fetch)} takim")
                except:
                    pass
    
    if verbose:
        print(f"   {len(home_away_stats_cache)} takim icin ev/deplasman verisi hazir")
    
    # =====================================================
    # H2H VERİLERİNİ PARALEL ÇEK
    # =====================================================
    h2h_cache_local = {}
    
    # Çekilecek H2H event'lerini topla
    h2h_to_fetch = []
    for _, fixture in matches_df.iterrows():
        event_id = fixture.get('event_id', '')
        espn_code = fixture.get('espn_code', '')
        if event_id and espn_code and event_id not in _h2h_cache:
            h2h_to_fetch.append((event_id, espn_code))
    
    if h2h_to_fetch:
        if verbose:
            print(f"\n[H2H] {len(h2h_to_fetch)} mac icin kafa-kafaya verisi cekilecek...")
        
        def fetch_h2h_wrapper(args):
            event_id, league_code = args
            return event_id, fetch_head_to_head(event_id, league_code)
        
        with ThreadPoolExecutor(max_workers=25) as executor:
            futures = [executor.submit(fetch_h2h_wrapper, pair) for pair in h2h_to_fetch]
            for future in as_completed(futures):
                try:
                    event_id, h2h_data = future.result()
                    if h2h_data:
                        h2h_cache_local[event_id] = h2h_data
                except:
                    pass
        
        if verbose:
            print(f"   {len(h2h_cache_local)} mac icin H2H verisi alindi")
    
    matches_data = []
    stats_matched = 0
    
    for _, fixture in matches_df.iterrows():
        home_team = fixture.get('home_team', '')
        away_team = fixture.get('away_team', '')
        league = fixture.get('league', '')
        league_display = fixture.get('league_display', league)
        
        home_stats = team_stats.get(home_team, default_stats)
        away_stats = team_stats.get(away_team, default_stats)
        
        # Ev/Deplasman ayrımlı istatistikler
        home_ha_stats = home_away_stats_cache.get(home_team, {})
        away_ha_stats = home_away_stats_cache.get(away_team, {})
        
        if home_team in team_stats or away_team in team_stats:
            stats_matched += 1
        
        # ---- EV SAHİBİ İSTATİSTİKLERİ ----
        # Ev sahibi takımın EVDEKİ performansı
        home_played_at_home = home_ha_stats.get('home_played', 0)
        if home_played_at_home > 0:
            home_attack_at_home = home_ha_stats.get('home_goals', 0) / home_played_at_home
            home_defense_at_home = home_ha_stats.get('home_conceded', 0) / home_played_at_home
            home_form_at_home = (home_ha_stats.get('home_wins', 0) * 3 + home_ha_stats.get('home_draws', 0))
        else:
            # Varsayılan: genel ortalama * ev avantajı
            home_attack_at_home = home_stats.get('avg_goals', 1.35) * 1.15
            home_defense_at_home = home_stats.get('avg_conceded', 1.2) * 0.9
            home_form_at_home = home_stats.get('form_points', 7)
        
        # ---- DEPLASMAN TAKIMI İSTATİSTİKLERİ ----
        # Deplasman takımının DEPLASMANDAKİ performansı
        away_played_away = away_ha_stats.get('away_played', 0)
        if away_played_away > 0:
            away_attack_away = away_ha_stats.get('away_goals', 0) / away_played_away
            away_defense_away = away_ha_stats.get('away_conceded', 0) / away_played_away
            away_form_away = (away_ha_stats.get('away_wins', 0) * 3 + away_ha_stats.get('away_draws', 0))
        else:
            # Varsayılan: genel ortalama * deplasman dezavantajı
            away_attack_away = away_stats.get('avg_goals', 1.35) * 0.85
            away_defense_away = away_stats.get('avg_conceded', 1.2) * 1.1
            away_form_away = away_stats.get('form_points', 7)
        
        # Head-to-Head verisi (önce local cache, sonra global cache)
        event_id = fixture.get('event_id', '')
        h2h_data = h2h_cache_local.get(event_id, {}) or _h2h_cache.get(event_id, {})
        
        matches_data.append({
            'match_date': fixture.get('match_date'),
            'turkey_time': fixture.get('turkey_time', ''),
            'league': league,
            'league_display': league_display,
            'home_team': home_team,
            'away_team': away_team,
            'source': fixture.get('source', 'Unknown'),
            
            # Genel istatistikler
            'home_last10_avg_goals': round(home_stats.get('avg_goals', 1.35), 2),
            'home_last10_avg_conceded': round(home_stats.get('avg_conceded', 1.2), 2),
            'home_last10_avg_xg': round(home_stats.get('avg_xg', 1.35), 2),
            'home_last10_avg_xg_against': round(home_stats.get('avg_xga', 1.2), 2),
            
            'away_last10_avg_goals': round(away_stats.get('avg_goals', 1.35), 2),
            'away_last10_avg_conceded': round(away_stats.get('avg_conceded', 1.2), 2),
            'away_last10_avg_xg': round(away_stats.get('avg_xg', 1.35), 2),
            'away_last10_avg_xg_against': round(away_stats.get('avg_xga', 1.2), 2),
            
            # Son 5 maç (genel)
            'home_last5_avg_goals': round(home_stats.get('avg_goals', 1.35), 2),
            'home_last5_avg_conceded': round(home_stats.get('avg_conceded', 1.2), 2),
            'home_last5_avg_xg': round(home_stats.get('avg_xg', 1.35), 2),
            'home_last5_avg_xg_against': round(home_stats.get('avg_xga', 1.2), 2),
            'home_last5_form_points': min(home_stats.get('form_points', 7), 15),
            
            'away_last5_avg_goals': round(away_stats.get('avg_goals', 1.35), 2),
            'away_last5_avg_conceded': round(away_stats.get('avg_conceded', 1.2), 2),
            'away_last5_avg_xg': round(away_stats.get('avg_xg', 1.35), 2),
            'away_last5_avg_xg_against': round(away_stats.get('avg_xga', 1.2), 2),
            'away_last5_form_points': min(away_stats.get('form_points', 7), 15),
            
            # *** EV/DEPLASMAN AYRIMI ***
            # Ev sahibi takımın EVDEKİ istatistikleri
            'home_at_home_avg_goals': round(home_attack_at_home, 2),
            'home_at_home_avg_conceded': round(home_defense_at_home, 2),
            'home_at_home_played': home_played_at_home,
            'home_at_home_form': min(home_form_at_home, 15),
            
            # Deplasman takımının DEPLASMANDAKİ istatistikleri
            'away_at_away_avg_goals': round(away_attack_away, 2),
            'away_at_away_avg_conceded': round(away_defense_away, 2),
            'away_at_away_played': away_played_away,
            'away_at_away_form': min(away_form_away, 15),
            
            # *** SON 5 MAÇ TRENDİ ***
            # Ev sahibi son 5 maç (eski->yeni sıralı)
            'home_recent_form': ','.join(home_ha_stats.get('recent_form', [])),
            'home_recent_goals': ','.join(map(str, home_ha_stats.get('recent_goals', []))),
            'home_recent_conceded': ','.join(map(str, home_ha_stats.get('recent_conceded', []))),
            'home_form_momentum': home_ha_stats.get('form_momentum', 0.0),
            
            # Deplasman son 5 maç
            'away_recent_form': ','.join(away_ha_stats.get('recent_form', [])),
            'away_recent_goals': ','.join(map(str, away_ha_stats.get('recent_goals', []))),
            'away_recent_conceded': ','.join(map(str, away_ha_stats.get('recent_conceded', []))),
            'away_form_momentum': away_ha_stats.get('form_momentum', 0.0),
            
            'home_season_xg': round(home_stats.get('avg_xg', 1.35) * home_stats.get('matches', 10), 1),
            'away_season_xg': round(away_stats.get('avg_xg', 1.35) * away_stats.get('matches', 10), 1),
            'home_season_yellow': 0, 'home_season_red': 0, 'home_season_pk_won': 0,
            'away_season_yellow': 0, 'away_season_red': 0, 'away_season_pk_won': 0,
            
            # Head-to-Head verisi
            'h2h_total_matches': h2h_data.get('total_matches', 0),
            'h2h_home_wins': h2h_data.get('home_wins', 0),
            'h2h_away_wins': h2h_data.get('away_wins', 0),
            'h2h_draws': h2h_data.get('draws', 0),
            'h2h_home_goals': h2h_data.get('home_goals', 0),
            'h2h_away_goals': h2h_data.get('away_goals', 0),
        })
    
    result_df = pd.DataFrame(matches_data)
    
    if verbose:
        print(f"\n[TAMAM] {len(result_df)} mac hazir")
        print("\nLig dagilimi:")
        for lg, count in result_df['league_display'].value_counts().items():
            print(f"   {lg}: {count} mac")
        
        print(f"\nIstatistik eslesmesi: {stats_matched}/{len(result_df)} mac")
    
    return result_df


# Uyumluluk
def fetch_all_fixtures(verbose: bool = True) -> pd.DataFrame:
    return fetch_all_data(verbose=verbose)


if __name__ == "__main__":
    start = time.time()
    df = fetch_all_data()
    elapsed = time.time() - start
    print(f"\nSure: {elapsed:.1f} saniye")
    
    if not df.empty:
        print("\nOrnek maclar (istatistiklerle):")
        cols = ['league_display', 'home_team', 'away_team', 
                'home_last5_avg_goals', 'home_last5_form_points']
        print(df[cols].head(15).to_string())
