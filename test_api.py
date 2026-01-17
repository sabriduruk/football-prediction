"""API Test - Hangi kaynak calisiyor?"""
import requests
import json

print("=" * 50)
print("API TEST")
print("=" * 50)

# 1. ESPN Test
print("\n[1] ESPN API Test...")
try:
    url = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        data = r.json()
        events = data.get('events', [])
        print(f"   ESPN OK - {len(events)} mac bulundu")
        if events:
            e = events[0]
            print(f"   Ornek: {e.get('name', 'N/A')}")
    else:
        print(f"   ESPN HATA: {r.status_code}")
except Exception as e:
    print(f"   ESPN HATA: {e}")

# 2. FotMob Test
print("\n[2] FotMob API Test...")
try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    }
    url = "https://www.fotmob.com/api/leagues?id=47"  # Premier League
    r = requests.get(url, headers=headers, timeout=10)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   Keys: {list(data.keys())[:10]}")
        
        # Matches
        matches = data.get('matches', {})
        print(f"   Matches keys: {list(matches.keys()) if isinstance(matches, dict) else type(matches)}")
        
        all_matches = matches.get('allMatches', []) if isinstance(matches, dict) else []
        print(f"   allMatches: {len(all_matches)} mac")
        
        if all_matches:
            m = all_matches[0]
            print(f"   Ornek mac keys: {list(m.keys())}")
    else:
        print(f"   FotMob HATA: {r.status_code}")
        print(f"   Response: {r.text[:200]}")
except Exception as e:
    print(f"   FotMob HATA: {e}")

# 3. API-Football Test (free tier)
print("\n[3] Football-Data.org Test...")
try:
    url = "https://api.football-data.org/v4/matches"
    headers = {'X-Auth-Token': 'test'}  # Free tier
    r = requests.get(url, headers=headers, timeout=10)
    print(f"   Status: {r.status_code}")
except Exception as e:
    print(f"   HATA: {e}")

print("\n" + "=" * 50)
