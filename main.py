#!/usr/bin/env python3
"""
Tennis AI Analyst - Éles verzió RapidAPI-val
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import argparse

import numpy as np
import requests
from sklearn.ensemble import RandomForestClassifier
import xgboost as xgb

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tennis_ai.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# API KLIENS
# ============================================================================

class TennisAPI:
    """Tennis Live Data API kliens"""
    
    def __init__(self):
        # API kulcs a környezeti változóból vagy a kódból
        self.api_key = os.getenv('RAPIDAPI_KEY', '')
        self.headers = {
            'X-RapidAPI-Key': self.api_key,
            'X-RapidAPI-Host': 'tennis-live-data.p.rapidapi.com'
        }
        
        if not self.api_key:
            logger.warning("⚠️ Nincs API kulcs! Használj RAPIDAPI_KEY környezeti változót")
    
    def get_today_matches(self):
        """Mai mérkőzések lekérése"""
        try:
            url = "https://tennis-live-data.p.rapidapi.com/matches/today"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                matches = data.get('matches', data.get('results', []))
                logger.info(f"✅ {len(matches)} mai mérkőzés lekérve")
                return matches
            else:
                logger.error(f"❌ API hiba: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ API hiba: {e}")
            return []
    
    def search_player(self, name):
        """Játékos keresése"""
        try:
            url = f"https://tennis-live-data.p.rapidapi.com/players/search/{name}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('players', data.get('results', []))
            return []
            
        except Exception as e:
            logger.error(f"Keresési hiba: {e}")
            return []

# ============================================================================
# PREDIKCIÓS MOTOR
# ============================================================================

class Predictor:
    """AI Predikciós motor"""
    
    def predict_match(self, player_a, player_b, surface="hard"):
        """
        Mérkőzés predikció
        """
        # Feature-ök generálása
        features = self._create_features(player_a, player_b, surface)
        
        # Mock modell predikció (élesben itt tanított modell lenne)
        import numpy as np
        prob = np.random.uniform(0.45, 0.55)  # Placeholder
        
        return {
            'player_a_win_probability': prob,
            'player_b_win_probability': 1 - prob,
            'predicted_winner': player_a if prob > 0.5 else player_b,
            'confidence': 0.65  # Placeholder
        }
    
    def _create_features(self, player_a, player_b, surface):
        """Feature engineering"""
        return np.random.rand(10)  # Placeholder

# ============================================================================
# FŐ FUNKCIÓ
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Tennis AI Predictor')
    parser.add_argument('--today', action='store_true', help='Mai mérkőzések')
    parser.add_argument('--player1', type=str, help='1. játékos')
    parser.add_argument('--player2', type=str, help='2. játékos')
    parser.add_argument('--surface', type=str, default='hard')
    parser.add_argument('--output', type=str, default='json')
    
    args = parser.parse_args()
    
    # API inicializálása
    api = TennisAPI()
    predictor = Predictor()
    
    if args.today:
        # Mai mérkőzések
        logger.info("📅 Mai mérkőzések lekérése...")
        matches = api.get_today_matches()
        
        if not matches:
            print(json.dumps({"error": "Nincsenek mai mérkőzések", "status": "no_data"}))
            return
        
        results = []
        for match in matches[:10]:  # Első 10 mérkőzés
            player_a = match.get('player1', {}).get('name', match.get('home', 'Player A'))
            player_b = match.get('player2', {}).get('name', match.get('away', 'Player B'))
            surface = match.get('surface', 'hard')
            
            pred = predictor.predict_match(player_a, player_b, surface)
            
            results.append({
                'match': f"{player_a} vs {player_b}",
                'surface': surface,
                'tournament': match.get('tournament', 'Unknown'),
                'start_time': match.get('start_time', ''),
                'prediction': {
                    'winner': pred['predicted_winner'],
                    'probability': f"{max(pred['player_a_win_probability'], pred['player_b_win_probability']):.1%}",
                    'confidence': f"{pred['confidence']:.1%}"
                }
            })
        
        # Eredmények mentése
        os.makedirs('results', exist_ok=True)
        output_file = f"results/predictions_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_matches': len(results),
                'predictions': results
            }, f, indent=2, ensure_ascii=False)
        
        print(json.dumps(results, indent=2, ensure_ascii=False))
        logger.info(f"✅ Eredmények mentve: {output_file}")
        
    elif args.player1 and args.player2:
        # Egyéni mérkőzés
        pred = predictor.predict_match(args.player1, args.player2, args.surface)
        
        result = {
            'match': f"{args.player1} vs {args.player2}",
            'surface': args.surface,
            'prediction': {
                'winner': pred['predicted_winner'],
                'probability': f"{max(pred['player_a_win_probability'], pred['player_b_win_probability']):.1%}",
                'confidence': f"{pred['confidence']:.1%}"
            }
        }
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    else:
        # Demo mód
        print(json.dumps({
            "message": "Használat: python main.py --today (mai meccsek) vagy --player1 X --player2 Y",
            "example": "python main.py --player1 \"Novak Djokovic\" --player2 \"Carlos Alcaraz\" --surface hard"
        }, indent=2))

if __name__ == "__main__":
    main()
