#!/usr/bin/env python3
"""
Tennis AI - Javított verzió
"""

import os
import sys
import json
import logging
from datetime import datetime
import argparse

import numpy as np
import requests

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# API KLIENS - JAVÍTVA
# ============================================================================

def get_api_key():
    """API kulcs biztonságos beolvasása"""
    api_key = os.getenv('RAPIDAPI_KEY', '')
    
    # Tisztítás - eltávolítjuk a whitespace karaktereket
    api_key = api_key.strip()
    api_key = api_key.replace('\n', '')
    api_key = api_key.replace('\r', '')
    api_key = api_key.replace(' ', '')
    
    if not api_key:
        logger.error("❌ Nincs RAPIDAPI_KEY beállítva!")
        return None
    
    logger.info(f"✅ API kulcs betöltve (hossz: {len(api_key)})")
    return api_key

def test_api_connection():
    """API kapcsolat tesztelése"""
    api_key = get_api_key()
    
    if not api_key:
        return False, "Nincs API kulcs"
    
    headers = {
        'X-RapidAPI-Key': api_key,
        'X-RapidAPI-Host': 'tennis-live-data.p.rapidapi.com'
    }
    
    # Teszt hívás
    try:
        url = "https://tennis-live-data.p.rapidapi.com/matches/today"
        logger.info("📡 API hívás...")
        
        response = requests.get(url, headers=headers, timeout=10)
        
        logger.info(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"   Válasz típusa: {type(data)}")
            logger.info(f"   Kulcsok: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
            return True, data
        elif response.status_code == 403:
            return False, "Érvénytelen API kulcs vagy lejárt előfizetés"
        else:
            return False, f"HTTP {response.status_code}: {response.text[:200]}"
            
    except requests.exceptions.Timeout:
        return False, "API időtúllépés"
    except Exception as e:
        return False, f"Hiba: {str(e)}"

def get_today_matches():
    """Mai mérkőzések lekérése"""
    api_key = get_api_key()
    
    if not api_key:
        return []
    
    headers = {
        'X-RapidAPI-Key': api_key,
        'X-RapidAPI-Host': 'tennis-live-data.p.rapidapi.com'
    }
    
    try:
        url = "https://tennis-live-data.p.rapidapi.com/matches/today"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Különböző API válaszformátumok kezelése
            if isinstance(data, dict):
                matches = data.get('matches', data.get('results', data.get('data', [])))
            elif isinstance(data, list):
                matches = data
            else:
                matches = []
            
            logger.info(f"✅ {len(matches)} mérkőzés található")
            return matches
        else:
            logger.error(f"❌ API hiba: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Hiba: {e}")
        return []

# ============================================================================
# EGYSZERŰ PREDIKCIÓ
# ============================================================================

def simple_prediction(player_a, player_b, surface="hard"):
    """Egyszerű predikció (demo)"""
    
    # Véletlen alapú predikció demo célra
    # Élesben itt ML modell lenne
    prob = np.random.normal(0.5, 0.1)
    prob = max(0.05, min(0.95, prob))
    
    return {
        'player_a': player_a,
        'player_b': player_b,
        'player_a_win_pct': round(prob * 100, 1),
        'player_b_win_pct': round((1 - prob) * 100, 1),
        'predicted_winner': player_a if prob > 0.5 else player_b,
        'surface': surface
    }

# ============================================================================
# FŐ FUNKCIÓ
# ============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--today', action='store_true')
    parser.add_argument('--test', action='store_true', help='API teszt')
    parser.add_argument('--player1', type=str)
    parser.add_argument('--player2', type=str)
    parser.add_argument('--surface', type=str, default='hard')
    parser.add_argument('--output', type=str, default='json')
    
    args = parser.parse_args()
    
    # API teszt mód
    if args.test:
        logger.info("🔍 API teszt futtatása...")
        success, result = test_api_connection()
        
        if success:
            logger.info("✅ API kapcsolat OK!")
            if isinstance(result, dict):
                logger.info(f"Válasz kulcsok: {list(result.keys())}")
                # Mutassunk pár mérkőzést ha vannak
                matches = result.get('matches', result.get('results', []))
                if matches:
                    logger.info(f"Találatok: {len(matches)} mérkőzés")
                    for i, match in enumerate(matches[:3]):
                        logger.info(f"  {i+1}. {match}")
        else:
            logger.error(f"❌ API hiba: {result}")
        return
    
    # Mai mérkőzések
    if args.today:
        logger.info("📅 Mai mérkőzések lekérése...")
        
        # Először teszteljük az API-t
        success, test_result = test_api_connection()
        
        if not success:
            # Demo mód - generáljunk fake predikciókat
            logger.warning("⚠️ API nem elérhető, demo mód")
            
            demo_matches = [
                {"player1": "Djokovic", "player2": "Alcaraz", "surface": "hard"},
                {"player1": "Swiatek", "player2": "Sabalenka", "surface": "clay"},
                {"player1": "Sinner", "player2": "Medvedev", "surface": "grass"},
            ]
            
            results = []
            for match in demo_matches:
                pred = simple_prediction(match['player1'], match['player2'], match['surface'])
                results.append(pred)
            
        else:
            # Valós API adatok
            matches = get_today_matches()
            
            if not matches:
                logger.warning("Nincsenek mai mérkőzések az API-ban")
                results = [{"message": "No matches today"}]
            else:
                results = []
                for match in matches[:10]:
                    if isinstance(match, dict):
                        p1 = match.get('player1', match.get('home', {}))
                        p2 = match.get('player2', match.get('away', {}))
                        
                        if isinstance(p1, dict):
                            p1 = p1.get('name', 'Player A')
                        if isinstance(p2, dict):
                            p2 = p2.get('name', 'Player B')
                        
                        surface = match.get('surface', 'hard')
                        pred = simple_prediction(str(p1), str(p2), surface)
                        results.append(pred)
        
        # Mentés
        os.makedirs('results', exist_ok=True)
        output_file = f"results/predictions_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'total': len(results),
            'predictions': results
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Eredmény mentve: {output_file}")
        
        # Kiírás
        print(json.dumps(output_data, indent=2, ensure_ascii=False))
        
    elif args.player1 and args.player2:
        # Egyéni predikció
        pred = simple_prediction(args.player1, args.player2, args.surface)
        print(json.dumps(pred, indent=2, ensure_ascii=False))
        
    else:
        print("""
Használat:
  python main.py --test              # API teszt
  python main.py --today             # Mai mérkőzések
  python main.py --player1 X --player2 Y  # Egyéni predikció
        """)

if __name__ == "__main__":
    main()
