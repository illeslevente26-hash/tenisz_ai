#!/usr/bin/env python3
"""
Tennis AI Analyst - Valós adatokkal működő verzió
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import argparse

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import joblib

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
# API KONFIGURÁCIÓ
# ============================================================================

# IDE ÍRD BE A RAPIDAPI KULCSODAT!
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', 'a_te_kulcsod_ide')  # Vagy használj környezeti változót
RAPIDAPI_HOST = "tennis-live-data.p.rapidapi.com"

# ============================================================================
# VALÓS TENNIS API KLIENS
# ============================================================================

class TennisAPIClient:
    """Valós tenisz adatok lekérése API-ról"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            'X-RapidAPI-Key': api_key,
            'X-RapidAPI-Host': RAPIDAPI_HOST
        }
        self.base_url = f"https://{RAPIDAPI_HOST}"
    
    def get_today_matches(self) -> List[Dict]:
        """
        Mai mérkőzések lekérése
        """
        try:
            url = f"{self.base_url}/matches/today"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Sikeres API hívás: {len(data.get('matches', []))} mai mérkőzés")
                return data.get('matches', [])
            else:
                logger.error(f"❌ API hiba: {response.status_code}")
                logger.error(f"   Válasz: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"❌ API kivétel: {e}")
            return []
    
    def get_player_stats(self, player_name: str) -> Dict:
        """
        Játékos statisztikák lekérése
        """
        try:
            # Keresés a játékosra
            url = f"{self.base_url}/players/search/{player_name}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('players'):
                    player_id = data['players'][0]['id']
                    
                    # Részletes statisztikák lekérése
                    stats_url = f"{self.base_url}/players/{player_id}/stats"
                    stats_response = requests.get(stats_url, headers=self.headers)
                    
                    if stats_response.status_code == 200:
                        return stats_response.json()
            
            return self._get_default_stats(player_name)
            
        except Exception as e:
            logger.error(f"Hiba a(z) {player_name} statisztikáinál: {e}")
            return self._get_default_stats(player_name)
    
    def get_head_to_head(self, player1: str, player2: str) -> Dict:
        """
        Egymás elleni statisztikák
        """
        try:
            url = f"{self.base_url}/matches/h2h/{player1}/{player2}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                return response.json()
            
            return {'total_matches': 0, 'message': 'Nincs elérhető H2H adat'}
            
        except Exception as e:
            logger.error(f"Hiba a H2H adatoknál: {e}")
            return {'total_matches': 0}
    
    def _get_default_stats(self, player_name: str) -> Dict:
        """Alapértelmezett statisztikák, ha nincs API adat"""
        return {
            'name': player_name,
            'ranking': 100,
            'last_10_win_pct': 50.0,
            'first_serve_pct': 60.0,
            'first_serve_won_pct': 70.0,
            'second_serve_won_pct': 50.0,
            'return_points_won_pct': 40.0,
            'break_points_saved_pct': 60.0,
            'break_points_converted_pct': 40.0,
            'hard_win_pct': 55.0,
            'clay_win_pct': 55.0,
            'grass_win_pct': 55.0,
            'indoor_win_pct': 55.0
        }

# ============================================================================
# FEATURE ENGINEERING (Ugyanaz, mint korábban)
# ============================================================================

class FeatureEngineer:
    """Feature-ök előállítása"""
    
    def create_features(self, stats_a: Dict, stats_b: Dict, match_info: Dict) -> np.ndarray:
        """Feature-ök létrehozása"""
        features = {}
        
        # Alap statisztikák
        features['rank_diff'] = stats_b.get('ranking', 100) - stats_a.get('ranking', 100)
        features['form_diff'] = stats_a.get('last_10_win_pct', 50) - stats_b.get('last_10_win_pct', 50)
        
        # Szerva dominancia
        a_serve = (stats_a.get('first_serve_pct', 60) * stats_a.get('first_serve_won_pct', 70) / 10000)
        b_serve = (stats_b.get('first_serve_pct', 60) * stats_b.get('first_serve_won_pct', 70) / 10000)
        features['serve_diff'] = a_serve - b_serve
        
        # Return
        features['return_diff'] = (
            stats_a.get('return_points_won_pct', 40) - 
            stats_b.get('return_points_won_pct', 40)
        ) / 100
        
        # Borítás
        surface = match_info.get('surface', 'hard').lower()
        features['surface_adv'] = (
            stats_a.get(f'{surface}_win_pct', 55) - 
            stats_b.get(f'{surface}_win_pct', 55)
        ) / 100
        
        return np.array(list(features.values())).reshape(1, -1)

# ============================================================================
# PREDIKCIÓS MODELL (Ugyanaz, mint korábban)
# ============================================================================

class TennisPredictor:
    """Predikciós motor"""
    
    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self._init_models()
    
    def _init_models(self):
        """Modellek inicializálása"""
        self.models = {
            'xgboost': xgb.XGBClassifier(
                n_estimators=500, max_depth=8, learning_rate=0.01,
                objective='binary:logistic', eval_metric='logloss'
            ),
            'random_forest': RandomForestClassifier(
                n_estimators=300, max_depth=10, random_state=42
            )
        }
        
        # Dummy training (élesben itt valós adatokon tanítanánk)
        X = np.random.rand(100, 5)
        y = np.random.randint(0, 2, 100)
        for model in self.models.values():
            model.fit(X, y)
    
    def predict(self, stats_a: Dict, stats_b: Dict, match_info: Dict) -> Dict:
        """Predikció készítése"""
        features = self.feature_engineer.create_features(stats_a, stats_b, match_info)
        
        predictions = {}
        for name, model in self.models.items():
            proba = model.predict_proba(features)[0]
            predictions[name] = proba[1]
        
        # Ensemble
        final_prob = np.mean(list(predictions.values()))
        
        return {
            'player_a_win_pct': final_prob,
            'player_b_win_pct': 1 - final_prob,
            'prediction': 'A' if final_prob > 0.5 else 'B',
            'confidence': 1 - np.std(list(predictions.values())),
            'individual_predictions': predictions
        }

# ============================================================================
# FŐ FUNKCIÓ
# ============================================================================

def main():
    """Fő program"""
    parser = argparse.ArgumentParser(description='Tennis AI Analyst - Éles adatok')
    parser.add_argument('--api-key', type=str, help='RapidAPI kulcs')
    parser.add_argument('--today', action='store_true', help='Mai mérkőzések prediktálása')
    parser.add_argument('--player1', type=str, help='1. játékos neve')
    parser.add_argument('--player2', type=str, help='2. játékos neve')
    parser.add_argument('--surface', type=str, default='hard', help='Borítás')
    parser.add_argument('--output', type=str, default='json', choices=['json', 'text'])
    
    args = parser.parse_args()
    
    # API kulcs beállítása
    api_key = args.api_key or RAPIDAPI_KEY
    
    if api_key == 'a_te_kulcsod_ide':
        logger.error("❌ HIBA: Nem adtál meg API kulcsot!")
        logger.error("Add meg a RAPIDAPI_KEY környezeti változót, vagy használd az --api-key kapcsolót")
        logger.error("Példa: python main.py --api-key az_te_kulcsod --today")
        sys.exit(1)
    
    # API kliens inicializálása
    api_client = TennisAPIClient(api_key)
    predictor = TennisPredictor()
    
    if args.today:
        # Mai mérkőzések prediktálása
        logger.info("📅 Mai mérkőzések lekérése...")
        matches = api_client.get_today_matches()
        
        if not matches:
            logger.warning("⚠️ Nincsenek mai mérkőzések, vagy nem sikerült lekérni az adatokat")
            logger.info("Próbáld meg konkrét játékosokkal: --player1 \"Novak Djokovic\" --player2 \"Carlos Alcaraz\"")
            return
        
        logger.info(f"✅ {len(matches)} mérkőzés található")
        
        predictions = []
        for match in matches[:5]:  # Első 5 mérkőzés
            player_a = match.get('player1', {}).get('name', 'Unknown A')
            player_b = match.get('player2', {}).get('name', 'Unknown B')
            surface = match.get('surface', 'hard')
            
            logger.info(f"\n🎾 Elemzés: {player_a} vs {player_b}")
            
            # Statisztikák lekérése
            stats_a = api_client.get_player_stats(player_a)
            stats_b = api_client.get_player_stats(player_b)
            
            # Predikció
            pred = predictor.predict(stats_a, stats_b, match)
            
            result = {
                'match': f"{player_a} vs {player_b}",
                'surface': surface,
                'tournament': match.get('tournament', 'Unknown'),
                'prediction': {
                    'winner': player_a if pred['player_a_win_pct'] > 0.5 else player_b,
                    'probability': f"{max(pred['player_a_win_pct'], pred['player_b_win_pct']):.1%}",
                    'confidence': f"{pred['confidence']:.1%}"
                }
            }
            predictions.append(result)
            
            # Kiírás
            print(f"  Győztes: {result['prediction']['winner']}")
            print(f"  Esély: {result['prediction']['probability']}")
            print(f"  Konfidencia: {result['prediction']['confidence']}")
        
        # JSON mentés
        output_file = f"results/predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs('results', exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(predictions, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n✅ Eredmények mentve: {output_file}")
        
        # Teljes JSON kiírás
        print("\n" + "="*50)
        print(json.dumps(predictions, indent=2, ensure_ascii=False))
        
    else:
        # Egyéni mérkőzés prediktálása
        player1 = args.player1 or "Novak Djokovic"
        player2 = args.player2 or "Carlos Alcaraz"
        surface = args.surface
        
        logger.info(f"🎾 Predikció: {player1} vs {player2} ({surface})")
        
        # Statisztikák lekérése
        stats_a = api_client.get_player_stats(player1)
        stats_b = api_client.get_player_stats(player2)
        
        # H2H lekérése
        h2h = api_client.get_head_to_head(player1, player2)
        
        # Predikció
        match_info = {'surface': surface}
        pred = predictor.predict(stats_a, stats_b, match_info)
        
        # Eredmény
        result = {
            'match': f"{player1} vs {player2}",
            'surface': surface,
            'datetime': datetime.now().isoformat(),
            'prediction': {
                'winner': player1 if pred['player_a_win_pct'] > 0.5 else player2,
                'player_a_win_probability': f"{pred['player_a_win_pct']:.1%}",
                'player_b_win_probability': f"{pred['player_b_win_pct']:.1%}",
                'confidence': f"{pred['confidence']:.1%}"
            },
            'h2h': h2h
        }
        
        print("\n" + "="*50)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Mentés
        output_file = f"results/prediction_{player1}_{player2}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs('results', exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Eredmény mentve: {output_file}")

if __name__ == "__main__":
    main()
