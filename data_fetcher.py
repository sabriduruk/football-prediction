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


def clear_cache():
    """Tum cache'i temizle."""
    global _team_stats_cache
    _team_stats_cache.clear()
    print("[CACHE] Onbellek temizlendi")


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
                
                for comp in competitors:
                    team_name = comp.get('team', {}).get('displayName', '')
                    records = comp.get('records', [])
                    record = records[0] if records else {}
                    
                    if comp.get('homeAway') == 'home':
                        home_team = team_name
                        home_record = record
                    else:
                        away_team = team_name
                        away_record = record
                
                if not home_team or not away_team:
                    continue
                
                match_date = pd.to_datetime(event.get('date'))
                status = competition.get('status', {}).get('type', {}).get('name', '')
                
                if status in ['STATUS_FINAL', 'STATUS_FULL_TIME', 'STATUS_POSTPONED']:
                    continue
                
                matches.append({
                    'match_date': match_date,
                    'league': league_key,
                    'league_display': display_name,
                    'home_team': home_team,
                    'away_team': away_team,
                    'source': 'ESPN'
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
    
    matches_data = []
    stats_matched = 0
    
    for _, fixture in matches_df.iterrows():
        home_team = fixture.get('home_team', '')
        away_team = fixture.get('away_team', '')
        league = fixture.get('league', '')
        league_display = fixture.get('league_display', league)
        
        home_stats = team_stats.get(home_team, default_stats)
        away_stats = team_stats.get(away_team, default_stats)
        
        if home_team in team_stats or away_team in team_stats:
            stats_matched += 1
        
        # Ev sahibi avantaji
        home_attack = home_stats.get('avg_goals', 1.35) * 1.1
        home_defense = home_stats.get('avg_conceded', 1.2) * 0.95
        away_attack = away_stats.get('avg_goals', 1.35) * 0.9
        away_defense = away_stats.get('avg_conceded', 1.2) * 1.05
        
        matches_data.append({
            'match_date': fixture.get('match_date'),
            'turkey_time': fixture.get('turkey_time', ''),
            'league': league,
            'league_display': league_display,
            'home_team': home_team,
            'away_team': away_team,
            'source': fixture.get('source', 'Unknown'),
            
            'home_last10_avg_goals': round(home_attack, 2),
            'home_last10_avg_conceded': round(home_defense, 2),
            'home_last10_avg_xg': round(home_stats.get('avg_xg', 1.35) * 1.1, 2),
            'home_last10_avg_xg_against': round(home_stats.get('avg_xga', 1.2) * 0.95, 2),
            
            'away_last10_avg_goals': round(away_attack, 2),
            'away_last10_avg_conceded': round(away_defense, 2),
            'away_last10_avg_xg': round(away_stats.get('avg_xg', 1.35) * 0.9, 2),
            'away_last10_avg_xg_against': round(away_stats.get('avg_xga', 1.2) * 1.05, 2),
            
            'home_last5_avg_goals': round(home_attack, 2),
            'home_last5_avg_conceded': round(home_defense, 2),
            'home_last5_avg_xg': round(home_stats.get('avg_xg', 1.35) * 1.1, 2),
            'home_last5_avg_xg_against': round(home_stats.get('avg_xga', 1.2) * 0.95, 2),
            'home_last5_form_points': min(home_stats.get('form_points', 7), 15),
            
            'away_last5_avg_goals': round(away_attack, 2),
            'away_last5_avg_conceded': round(away_defense, 2),
            'away_last5_avg_xg': round(away_stats.get('avg_xg', 1.35) * 0.9, 2),
            'away_last5_avg_xg_against': round(away_stats.get('avg_xga', 1.2) * 1.05, 2),
            'away_last5_form_points': min(away_stats.get('form_points', 7), 15),
            
            'home_season_xg': round(home_stats.get('avg_xg', 1.35) * home_stats.get('matches', 10), 1),
            'away_season_xg': round(away_stats.get('avg_xg', 1.35) * away_stats.get('matches', 10), 1),
            'home_season_yellow': 0, 'home_season_red': 0, 'home_season_pk_won': 0,
            'away_season_yellow': 0, 'away_season_red': 0, 'away_season_pk_won': 0,
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
