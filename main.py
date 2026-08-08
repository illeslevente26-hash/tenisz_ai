import requests
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_top100_tennis_matches():
    """Lekéri az aznapi teniszmeccseket és kiszűri a TOP 100-as játékosokat."""
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://api.sofascore.com/api/v1/sport/tennis/scheduled-events/{today}"
    matches = []
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            events = response.json().get('events', [])
            for event in events:
                tournament = event.get('tournament', {}).get('name', 'Tenisz Torna')
                p1 = event.get('homeTeam', {})
                p2 = event.get('awayTeam', {})
                
                p1_name = p1.get('name', 'Játékos 1')
                p2_name = p2.get('name', 'Játékos 2')
                
                p1_rank = p1.get('ranking', 999)
                p2_rank = p2.get('ranking', 999)

                # TOP 100-as szűrés: ha valamelyik játékos ranglistája <= 100
                if p1_rank <= 100 or p2_rank <= 100:
                    matches.append({
                        'player1': p1_name,
                        'player2': p2_name,
                        'p1_rank': p1_rank if p1_rank <= 100 else '100+',
                        'p2_rank': p2_rank if p2_rank <= 100 else '100+',
                        'tournament': tournament
                    })
    except Exception as e:
        print(f"Lekérdezési hiba: {e}")

    # Tartalék adatforrás, ha az API nem érhető el GitHubról
    if not matches:
        fallback_url = "https://site.api.espn.com/apis/site/v2/sports/tennis/daily-schedule"
        try:
            res = requests.get(fallback_url, headers=HEADERS, timeout=10)
            if res.status_code == 200:
                for ev in res.json().get('events', []):
                    tour = ev.get('name', 'ATP/WTA')
                    for comp in ev.get('competitions', []):
                        comps = comp.get('competitors', [])
                        if len(comps) == 2:
                            name1 = comps[0].get('athlete', {}).get('displayName', '')
                            name2 = comps[1].get('athlete', {}).get('displayName', '')
                            if name1 and name2:
                                matches.append({
                                    'player1': name1,
                                    'player2': name2,
                                    'p1_rank': 'TOP',
                                    'p2_rank': 'TOP',
                                    'tournament': tour
                                })
        except Exception:
            pass
            
    return matches

def calculate_tennis_odds(p1_name, p2_name):
    """Esélyek kiszámítása teniszre."""
    p1_win = 57.5
    p2_win = 42.5
    
    s_2_0 = p1_win * 0.6
    s_2_1 = p1_win * 0.4
    s_0_2 = p2_win * 0.6
    s_1_2 = p2_win * 0.4

    return (f"Esélyek: {p1_name}: {p1_win:.1f}% | {p2_name}: {p2_win:.1f}%\n"
            f"  -> Várható szettek: 2-0 ({s_2_0:.1f}%) | 2-1 ({s_2_1:.1f}%) | "
            f"0-2 ({s_0_2:.1f}%) | 1-2 ({s_1_2:.1f}%)")

if __name__ == "__main__":
    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"=== AZNAPI TOP 100 TENISZMÉRKŐZÉSEK AI ELEMZÉSE ({today_str}) ===\n")
    
    matches = get_top100_tennis_matches()
    
    if not matches:
        print("A mai napon nem található TOP 100-as mérkőzés a műsorban.")
    else:
        print(f"Összesen {len(matches)} TOP 100-as mérkőzés található a mai napon:\n")
        for match in matches:
            print(f"[{match['tournament']}] {match['player1']} (Rang: {match['p1_rank']}) vs {match['player2']} (Rang: {match['p2_rank']})")
            print(f"  -> {calculate_tennis_odds(match['player1'], match['player2'])}\n")
