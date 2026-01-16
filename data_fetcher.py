"""
Futbol Veri Cekme Modulu (Optimized)
====================================
FBref + ESPN hibrit veri cekme - Hizlandirilmis versiyon.
"""

import soccerdata as sd
import pandas as pd
import numpy as np
from datetime import date, timedelta, datetime
from typing import Optional, List, Dict, Any, Tuple
import pytz
import warnings
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

warnings.filterwarnings('ignore')

# FBREF LIGLERI (Big 5) - ulke adlari ile
FBREF_LEAGUES = {
    'ENG-Premier League': 'Ingiltere Premier League',
    'ESP-La Liga': 'Ispanya La Liga',
    'ITA-Serie A': 'Italya Serie A',
    'GER-Bundesliga': 'Almanya Bundesliga',
    'FRA-Ligue 1': 'Fransa Ligue 1',
}

# ESPN LIGLERI - ulke adlari ile
ESPN_LEAGUES = {
    'TUR-Super Lig': ('tur.1', 'Turkiye Super Lig'),
    'POR-Primeira Liga': ('por.1', 'Portekiz Primeira Liga'),
    'BEL-Pro League': ('bel.1', 'Belcika Pro League'),
    'KSA-Saudi Pro League': ('sau.1', 'Suudi Arabistan Pro League'),
    'INT-Champions League': ('uefa.champions', 'UEFA Sampiyonlar Ligi'),
    'INT-Europa League': ('uefa.europa', 'UEFA Avrupa Ligi'),
    'INT-Conference League': ('uefa.europa.conf', 'UEFA Konferans Ligi'),
}

ALL_LEAGUES = list(FBREF_LEAGUES.keys()) + list(ESPN_LEAGUES.keys())

TURKEY_TZ = pytz.timezone('Europe/Istanbul')
UTC_TZ = pytz.UTC

# GLOBAL CACHE - Uygulama boyunca korunur
_fbref_schedule_cache: Optional[pd.DataFrame] = None
_espn_cache: Dict[str, pd.DataFrame] = {}
_form_cache: Dict[str, Dict] = {}


def clear_cache():
    """Tum cache'i temizle."""
    global _fbref_schedule_cache, _espn_cache, _form_cache
    _fbref_schedule_cache = None
    _espn_cache.clear()
    _form_cache.clear()
    print("[CACHE] Onbellek temizlendi")


def get_current_season() -> str:
    today = date.today()
    year = today.year
    if today.month >= 8:
        return f"{year}-{year + 1}"
    else:
        return f"{year - 1}-{year}"


def get_week_range() -> Tuple[date, date]:
    """Hafta araligi: Bugun - Sali"""
    today = date.today()
    weekday = today.weekday()
    
    if weekday >= 1:
        days_since_tuesday = weekday - 1
    else:
        days_since_tuesday = 6
    
    start_tuesday = today - timedelta(days=days_since_tuesday)
    end_tuesday = start_tuesday + timedelta(days=7)
    
    # Gecmis gosterilmez
    if start_tuesday < today:
        start_tuesday = today
    
    return start_tuesday, end_tuesday


def get_league_display_name(league_code: str) -> str:
    if league_code in FBREF_LEAGUES:
        return FBREF_LEAGUES[league_code]
    elif league_code in ESPN_LEAGUES:
        return ESPN_LEAGUES[league_code][1]
    return league_code


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


def parse_score(score_str: str) -> Tuple[int, int]:
    if pd.isna(score_str) or not score_str:
        return (np.nan, np.nan)
    try:
        for sep in ['–', '-', '—', '−', ':']:
            if sep in str(score_str):
                parts = str(score_str).split(sep)
                if len(parts) == 2:
                    return (int(parts[0].strip()), int(parts[1].strip()))
        return (np.nan, np.nan)
    except:
        return (np.nan, np.nan)


def fetch_fbref_schedule_fast() -> pd.DataFrame:
    """FBref schedule - cache kullan."""
    global _fbref_schedule_cache
    
    if _fbref_schedule_cache is not None:
        print("[FBREF] Cache'den yuklendi (hizli)")
        return _fbref_schedule_cache.copy()
    
    try:
        print("[FBREF] Veri cekiliyor...")
        season = get_current_season()
        fb = sd.FBref(leagues=list(FBREF_LEAGUES.keys()), seasons=[season])
        schedule = fb.read_schedule()
        
        if not schedule.empty:
            schedule = schedule.reset_index()
            schedule['date'] = pd.to_datetime(schedule['date'], errors='coerce')
            schedule['source'] = 'FBref'
            schedule['league_display'] = schedule['league'].map(FBREF_LEAGUES)
            _fbref_schedule_cache = schedule
            print(f"   + {len(schedule)} mac yuklendi")
            return schedule.copy()
        return pd.DataFrame()
    except Exception as e:
        print(f"[FBREF HATA] {e}")
        return pd.DataFrame()


def fetch_espn_single(league_code: str, league_name: str, display_name: str) -> pd.DataFrame:
    """Tek bir ESPN ligi icin veri cek - hizli."""
    global _espn_cache
    
    cache_key = f"espn_{league_code}"
    if cache_key in _espn_cache:
        return _espn_cache[cache_key].copy()
    
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard"
        all_matches = []
        
        # Sadece 7 gun (daha hizli)
        for days_offset in range(0, 7):
            target_date = date.today() + timedelta(days=days_offset)
            params = {'dates': target_date.strftime('%Y%m%d')}
            
            try:
                response = requests.get(url, params=params, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    
                    for event in data.get('events', []):
                        competition = event.get('competitions', [{}])[0]
                        competitors = competition.get('competitors', [])
                        
                        if len(competitors) >= 2:
                            home_team = away_team = None
                            home_score = away_score = None
                            
                            for comp in competitors:
                                if comp.get('homeAway') == 'home':
                                    home_team = comp.get('team', {}).get('displayName', '')
                                    home_score = comp.get('score')
                                else:
                                    away_team = comp.get('team', {}).get('displayName', '')
                                    away_score = comp.get('score')
                            
                            match_date = event.get('date', '')
                            status = event.get('status', {}).get('type', {}).get('name', '')
                            
                            all_matches.append({
                                'league': league_name,
                                'league_display': display_name,
                                'date': pd.to_datetime(match_date),
                                'home_team': home_team,
                                'away_team': away_team,
                                'home_score': int(home_score) if home_score and status == 'STATUS_FINAL' else np.nan,
                                'away_score': int(away_score) if away_score and status == 'STATUS_FINAL' else np.nan,
                                'status': status,
                                'source': 'ESPN'
                            })
            except:
                continue
        
        df = pd.DataFrame(all_matches)
        if not df.empty:
            df = df.drop_duplicates(subset=['home_team', 'away_team', 'date'])
            _espn_cache[cache_key] = df
        return df
    except:
        return pd.DataFrame()


def fetch_all_espn_parallel() -> pd.DataFrame:
    """Tum ESPN liglerini paralel cek."""
    print("[ESPN] Paralel veri cekiliyor...")
    
    all_dfs = []
    
    # 7 paralel baglanti
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {}
        for name, (code, display) in ESPN_LEAGUES.items():
            futures[executor.submit(fetch_espn_single, code, name, display)] = display
        
        for future in as_completed(futures, timeout=30):
            display = futures[future]
            try:
                df = future.result(timeout=10)
                if not df.empty:
                    all_dfs.append(df)
                    print(f"   + {display}: {len(df)} mac")
            except:
                pass
    
    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    return pd.DataFrame()


def fetch_all_fixtures(verbose: bool = True) -> pd.DataFrame:
    """Tum fiksturu cek - optimize edilmis."""
    start_date, end_date = get_week_range()
    
    if verbose:
        print("=" * 50)
        print(f"FIKSTUR: {start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')}")
        print("=" * 50)
    
    all_fixtures = []
    
    # FBref (cache'li)
    fbref_df = fetch_fbref_schedule_fast()
    if not fbref_df.empty:
        all_fixtures.append(fbref_df)
    
    # ESPN (paralel)
    espn_df = fetch_all_espn_parallel()
    if not espn_df.empty:
        all_fixtures.append(espn_df)
    
    if not all_fixtures:
        return pd.DataFrame()
    
    combined = pd.concat(all_fixtures, ignore_index=True)
    
    # Tarih filtresi
    start_ts = pd.Timestamp(start_date, tz='UTC')
    end_ts = pd.Timestamp(end_date, tz='UTC')
    
    combined['date'] = pd.to_datetime(combined['date'], errors='coerce', utc=True)
    weekly = combined[
        (combined['date'] >= start_ts) & 
        (combined['date'] < end_ts)
    ].copy()
    
    weekly['turkey_time'] = weekly['date'].apply(format_turkey_datetime)
    weekly = weekly.sort_values(['date', 'league']).reset_index(drop=True)
    
    if verbose:
        print(f"\n[TOPLAM] {len(weekly)} mac")
    
    return weekly


def calculate_team_form_fast(team: str, schedule: pd.DataFrame) -> Dict[str, Any]:
    """Takim formu - cache'li ve hizli."""
    global _form_cache
    
    if team in _form_cache:
        return _form_cache[team]
    
    default = {
        'avg_goals_scored': 1.2, 'avg_goals_conceded': 1.0,
        'avg_xg_for': 1.2, 'avg_xg_against': 1.0,
        'form_points': 7, 'matches_played': 0
    }
    
    if schedule.empty:
        return default
    
    team_matches = schedule[
        (schedule['home_team'] == team) | (schedule['away_team'] == team)
    ]
    
    if 'score' in team_matches.columns:
        played = team_matches[team_matches['score'].notna()].head(10)
    elif 'home_score' in team_matches.columns:
        played = team_matches[team_matches['home_score'].notna()].head(10)
    else:
        _form_cache[team] = default
        return default
    
    if played.empty:
        _form_cache[team] = default
        return default
    
    wins = draws = goals_scored = goals_conceded = 0
    
    for _, match in played.iterrows():
        is_home = match['home_team'] == team
        
        if 'score' in match.index and pd.notna(match.get('score')):
            home_score, away_score = parse_score(match['score'])
        else:
            home_score = match.get('home_score', 0) or 0
            away_score = match.get('away_score', 0) or 0
        
        if pd.isna(home_score) or pd.isna(away_score):
            continue
            
        gf = home_score if is_home else away_score
        ga = away_score if is_home else home_score
        
        goals_scored += gf
        goals_conceded += ga
        
        if gf > ga:
            wins += 1
        elif gf == ga:
            draws += 1
    
    n = len(played)
    result = {
        'avg_goals_scored': round(goals_scored / n, 2) if n > 0 else 1.2,
        'avg_goals_conceded': round(goals_conceded / n, 2) if n > 0 else 1.0,
        'avg_xg_for': round(goals_scored / n, 2) if n > 0 else 1.2,
        'avg_xg_against': round(goals_conceded / n, 2) if n > 0 else 1.0,
        'form_points': wins * 3 + draws,
        'matches_played': n
    }
    
    _form_cache[team] = result
    return result


def fetch_all_data(
    leagues: Optional[List[str]] = None,
    seasons: Optional[List[str]] = None,
    days_ahead: int = 7,
    last_n_matches: int = 10,
    verbose: bool = True
) -> pd.DataFrame:
    """Ana veri cekme - optimize edilmis."""
    if leagues is None:
        leagues = ALL_LEAGUES
    
    start_date, end_date = get_week_range()
    
    if verbose:
        print("=" * 50)
        print("FUTBOL VERI CEKME (Hizli)")
        print(f"Tarih: {start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')}")
        print("=" * 50)
    
    # Fikstur
    weekly_fixtures = fetch_all_fixtures(verbose)
    
    if weekly_fixtures.empty:
        if verbose:
            print("\nBu hafta mac yok!")
        return pd.DataFrame()
    
    # Schedule (form hesabi icin)
    all_schedule = fetch_fbref_schedule_fast()
    
    if verbose:
        print(f"\n{len(weekly_fixtures)} mac isleniyor...")
    
    matches_data = []
    
    for _, fixture in weekly_fixtures.iterrows():
        home_team = fixture.get('home_team', '')
        away_team = fixture.get('away_team', '')
        league = fixture.get('league', '')
        league_display = fixture.get('league_display', league)
        
        # Form (cache'li)
        home_form = calculate_team_form_fast(home_team, all_schedule)
        away_form = calculate_team_form_fast(away_team, all_schedule)
        
        matches_data.append({
            'match_date': fixture.get('date'),
            'turkey_time': fixture.get('turkey_time', ''),
            'league': league,
            'league_display': league_display,
            'home_team': home_team,
            'away_team': away_team,
            'source': fixture.get('source', 'Unknown'),
            
            'home_last10_avg_goals': home_form['avg_goals_scored'],
            'home_last10_avg_conceded': home_form['avg_goals_conceded'],
            'home_last10_avg_xg': home_form['avg_xg_for'],
            'home_last10_avg_xg_against': home_form['avg_xg_against'],
            
            'away_last10_avg_goals': away_form['avg_goals_scored'],
            'away_last10_avg_conceded': away_form['avg_goals_conceded'],
            'away_last10_avg_xg': away_form['avg_xg_for'],
            'away_last10_avg_xg_against': away_form['avg_xg_against'],
            
            'home_last5_avg_goals': home_form['avg_goals_scored'],
            'home_last5_avg_conceded': home_form['avg_goals_conceded'],
            'home_last5_avg_xg': home_form['avg_xg_for'],
            'home_last5_avg_xg_against': home_form['avg_xg_against'],
            'home_last5_form_points': home_form['form_points'],
            
            'away_last5_avg_goals': away_form['avg_goals_scored'],
            'away_last5_avg_conceded': away_form['avg_goals_conceded'],
            'away_last5_avg_xg': away_form['avg_xg_for'],
            'away_last5_avg_xg_against': away_form['avg_xg_against'],
            'away_last5_form_points': away_form['form_points'],
            
            'home_season_xg': 0, 'away_season_xg': 0,
            'home_season_yellow': 0, 'home_season_red': 0, 'home_season_pk_won': 0,
            'away_season_yellow': 0, 'away_season_red': 0, 'away_season_pk_won': 0,
        })
    
    matches_df = pd.DataFrame(matches_data)
    
    if verbose:
        print(f"\n[TAMAM] {len(matches_df)} mac hazir")
    
    return matches_df


SUPPORTED_LEAGUES = ALL_LEAGUES


if __name__ == "__main__":
    import time
    start = time.time()
    df = fetch_all_data()
    elapsed = time.time() - start
    print(f"\nSure: {elapsed:.1f} saniye")
    if not df.empty:
        print(f"Toplam: {len(df)} mac")
