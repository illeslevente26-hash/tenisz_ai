#!/usr/bin/env python3
"""
Tennis AI Analyst - Fő belépési pont
Predikciók futtatása és riportok generálása
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import joblib

# Logging konfigurálása
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tennis_ai.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# KONFIGURÁCIÓ
# ============================================================================

class Config:
    """Alap konfiguráció"""
    def __init__(self):
        self.data_dir = Path("data")
        self.models_dir = Path("models")
        self.results_dir = Path("results")
        self.logs_dir = Path("logs")
        
        # Könyvtárak létrehozása
        for dir_path in [self.data_dir, self.models_dir, self.results_dir, self.logs_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # Modell paraméterek
        self.model_params = {
            'xgboost': {
                'n_estimators': 500,
                'max_depth': 8,
                'learning_rate': 0.01
            },
            'random_forest': {
                'n_estimators': 300,
                'max_depth': 10,
                'min_samples_split': 5
            }
        }
        
        # Monte Carlo paraméterek
        self.mc_simulations = 10000
        self.kelly_fraction = 0.25

config = Config()

# ============================================================================
# ADAT GENERÁLÁS (Amíg nincs éles API kapcsolat)
# ============================================================================

class MockDataGenerator:
    """Teszt adatok generálása (éles környezetben API-ról jön)"""
    
    @staticmethod
    def generate_player_stats(player_name: str) -> Dict:
        """Játékos statisztikák generálása"""
        return {
            'name': player_name,
            'ranking': np.random.randint(1, 100),
            'age': np.random.randint(19, 38),
            'height_cm': np.random.randint(170, 211),
            'weight_kg': np.random.randint(65, 100),
            'hand': np.random.choice(['R', 'L']),
            'backhand': np.random.choice(['1H', '2H']),
            
            # Általános statisztikák
            'matches_played_year': np.random.randint(20, 80),
            'win_pct_year': round(np.random.uniform(40, 90), 1),
            'titles_year': np.random.randint(0, 8),
            
            # Forma mutatók
            'last_10_win_pct': round(np.random.uniform(30, 100), 1),
            'current_win_streak': np.random.randint(0, 15),
            'points_defending': np.random.randint(0, 5000),
            
            # Szerva statisztikák
            'aces_per_match': round(np.random.uniform(2, 15), 1),
            'double_faults_per_match': round(np.random.uniform(0.5, 5), 1),
            'first_serve_pct': round(np.random.uniform(55, 75), 1),
            'first_serve_won_pct': round(np.random.uniform(65, 85), 1),
            'second_serve_won_pct': round(np.random.uniform(45, 60), 1),
            'break_points_saved_pct': round(np.random.uniform(50, 75), 1),
            'service_games_won_pct': round(np.random.uniform(70, 95), 1),
            
            # Return statisztikák
            'return_points_won_pct': round(np.random.uniform(35, 45), 1),
            'first_return_won_pct': round(np.random.uniform(25, 40), 1),
            'second_return_won_pct': round(np.random.uniform(45, 60), 1),
            'break_points_converted_pct': round(np.random.uniform(35, 50), 1),
            'return_games_won_pct': round(np.random.uniform(15, 35), 1),
            
            # Borítás specifikus
            'hard_win_pct': round(np.random.uniform(40, 90), 1),
            'clay_win_pct': round(np.random.uniform(40, 90), 1),
            'grass_win_pct': round(np.random.uniform(40, 90), 1),
            'indoor_win_pct': round(np.random.uniform(40, 90), 1),
            
            # Mentális/Kulcspillanat statisztikák
            'tiebreak_win_pct': round(np.random.uniform(30, 70), 1),
            'deciding_set_win_pct': round(np.random.uniform(40, 75), 1),
            'fifth_set_win_pct': round(np.random.uniform(40, 70), 1),
            'vs_top10_win_pct': round(np.random.uniform(20, 60), 1),
            
            # Fizikai állapot
            'hours_played_this_week': round(np.random.uniform(0, 15), 1),
            'rest_days': np.random.randint(0, 7),
            'injury_score': round(np.random.uniform(0, 10), 1)  # 0 = egészséges, 10 = súlyosan sérült
        }
    
    @staticmethod
    def generate_match_context() -> Dict:
        """Mérkőzés környezet generálása"""
        return {
            'tournament': np.random.choice([
                'Australian Open', 'Roland Garros', 'Wimbledon', 'US Open',
                'Indian Wells', 'Miami Open', 'Monte Carlo', 'Madrid Open',
                'Rome Masters', 'Cincinnati', 'Shanghai', 'Paris Masters'
            ]),
            'surface': np.random.choice(['hard', 'clay', 'grass', 'indoor']),
            'round': np.random.choice(['R128', 'R64', 'R32', 'R16', 'QF', 'SF', 'F']),
            'best_of': np.random.choice([3, 5]),
            'indoor': np.random.choice([True, False]),
            'temperature_c': np.random.randint(10, 40),
            'wind_kmh': np.random.randint(0, 40),
            'humidity_pct': np.random.randint(20, 90),
            'altitude_m': np.random.choice([0, 50, 100, 500, 1000]),
            'court_speed': round(np.random.uniform(0.3, 0.9), 2),
            'prize_money': np.random.choice([50000, 100000, 250000, 500000, 1000000, 2000000])
        }

# ============================================================================
# FEATURE ENGINEERING
# ============================================================================

class FeatureEngineer:
    """Feature-ök előállítása a nyers adatokból"""
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.feature_names = []
        
    def create_features(self, player_a_stats: Dict, player_b_stats: Dict, 
                       match_context: Dict) -> np.ndarray:
        """
        Feature-ök létrehozása két játékos és a mérkőzés kontextus alapján
        """
        features = {}
        
        # 1. Ranking különbségek
        features['rank_diff'] = player_b_stats['ranking'] - player_a_stats['ranking']
        features['rank_ratio'] = player_a_stats['ranking'] / max(player_b_stats['ranking'], 1)
        features['age_diff'] = player_a_stats['age'] - player_b_stats['age']
        
        # 2. Forma mutatók
        features['form_diff'] = player_a_stats['last_10_win_pct'] - player_b_stats['last_10_win_pct']
        features['streak_diff'] = player_a_stats['current_win_streak'] - player_b_stats['current_win_streak']
        features['fatigue_diff'] = player_a_stats['hours_played_this_week'] - player_b_stats['hours_played_this_week']
        
        # 3. Szerva dominancia
        a_serve_dominance = (
            player_a_stats['first_serve_pct'] / 100 * player_a_stats['first_serve_won_pct'] / 100 +
            (1 - player_a_stats['first_serve_pct'] / 100) * player_a_stats['second_serve_won_pct'] / 100
        )
        b_serve_dominance = (
            player_b_stats['first_serve_pct'] / 100 * player_b_stats['first_serve_won_pct'] / 100 +
            (1 - player_b_stats['first_serve_pct'] / 100) * player_b_stats['second_serve_won_pct'] / 100
        )
        features['serve_dominance_diff'] = a_serve_dominance - b_serve_dominance
        
        # 4. Return agresszivitás
        a_return_aggression = (
            player_a_stats['first_return_won_pct'] * 0.7 + 
            player_a_stats['second_return_won_pct'] * 0.3
        ) / 100
        b_return_aggression = (
            player_b_stats['first_return_won_pct'] * 0.7 + 
            player_b_stats['second_return_won_pct'] * 0.3
        ) / 100
        features['return_aggression_diff'] = a_return_aggression - b_return_aggression
        
        # 5. Break pont hatékonyság
        features['break_point_diff'] = (
            player_a_stats['break_points_converted_pct'] - 
            player_b_stats['break_points_converted_pct']
        )
        features['break_save_diff'] = (
            player_a_stats['break_points_saved_pct'] - 
            player_b_stats['break_points_saved_pct']
        )
        
        # 6. Borítás specifikus előny
        surface = match_context.get('surface', 'hard')
        surface_key = f"{surface}_win_pct"
        features['surface_advantage'] = (
            player_a_stats.get(surface_key, 50) - 
            player_b_stats.get(surface_key, 50)
        )
        
        # 7. Tapasztalat
        features['experience_diff'] = (
            player_a_stats['matches_played_year'] - 
            player_b_stats['matches_played_year']
        )
        
        # 8. Mentális erő
        features['clutch_diff'] = (
            (player_a_stats['tiebreak_win_pct'] + player_a_stats['deciding_set_win_pct']) / 2 -
            (player_b_stats['tiebreak_win_pct'] + player_b_stats['deciding_set_win_pct']) / 2
        )
        
        # 9. Fizikai állapot
        features['rest_advantage'] = (
            player_a_stats['rest_days'] - player_b_stats['rest_days']
        )
        features['injury_diff'] = (
            player_b_stats['injury_score'] - player_a_stats['injury_score']
        )
        
        # 10. Környezeti faktorok
        features['court_speed_factor'] = match_context.get('court_speed', 0.5)
        features['wind_factor'] = match_context.get('wind_kmh', 0) / 100
        features['temperature_factor'] = abs(match_context.get('temperature_c', 20) - 20) / 50
        features['altitude_factor'] = match_context.get('altitude_m', 0) / 2000
        
        self.feature_names = list(features.keys())
        return np.array(list(features.values())).reshape(1, -1)

# ============================================================================
# ML MODELLEK
# ============================================================================

class TennisPredictionModels:
    """Ensemble predikciós modellek"""
    
    def __init__(self):
        self.models = {}
        self.feature_engineer = FeatureEngineer()
        self._initialize_models()
        
    def _initialize_models(self):
        """Modellek inicializálása"""
        self.models = {
            'xgboost': xgb.XGBClassifier(
                n_estimators=config.model_params['xgboost']['n_estimators'],
                max_depth=config.model_params['xgboost']['max_depth'],
                learning_rate=config.model_params['xgboost']['learning_rate'],
                objective='binary:logistic',
                eval_metric='logloss',
                use_label_encoder=False
            ),
            'random_forest': RandomForestClassifier(
                n_estimators=config.model_params['random_forest']['n_estimators'],
                max_depth=config.model_params['random_forest']['max_depth'],
                min_samples_split=config.model_params['random_forest']['min_samples_split'],
                class_weight='balanced',
                random_state=42
            ),
            'gradient_boosting': GradientBoostingClassifier(
                n_estimators=200,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )
        }
    
    def train(self, X_train: np.ndarray, y_train: np.ndarray):
        """Modellek tanítása"""
        logger.info("Modellek tanításának kezdése...")
        for name, model in self.models.items():
            logger.info(f"  {name} tanítása...")
            model.fit(X_train, y_train)
        logger.info("Modellek tanítása kész!")
    
    def predict(self, features: np.ndarray) -> Dict:
        """
        Ensemble predikció
        """
        predictions = {}
        probabilities = {}
        
        for name, model in self.models.items():
            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(features)[0]
                predictions[name] = 1 if proba[1] > 0.5 else 0
                probabilities[name] = proba[1]
            else:
                predictions[name] = model.predict(features)[0]
                probabilities[name] = float(predictions[name])
        
        # Súlyozott ensemble
        weights = {
            'xgboost': 0.4,
            'random_forest': 0.3,
            'gradient_boosting': 0.3
        }
        
        final_probability = sum(
            probabilities[name] * weights.get(name, 0.33) 
            for name in self.models.keys()
        )
        
        # Konfidencia számítása
        pred_std = np.std(list(probabilities.values()))
        confidence = 1 - pred_std
        
        return {
            'player_a_win_probability': final_probability,
            'prediction': 'A' if final_probability > 0.5 else 'B',
            'confidence': confidence,
            'individual_predictions': probabilities,
            'model_agreement': len(set(predictions.values())) == 1
        }

# ============================================================================
# MONTE CARLO SZIMULÁCIÓ
# ============================================================================

class MonteCarloSimulator:
    """Monte Carlo szimuláció a mérkőzés lefolyására"""
    
    def __init__(self, n_simulations: int = 10000):
        self.n_simulations = n_simulations
        
    def simulate_match(self, player_a_stats: Dict, player_b_stats: Dict, 
                      match_format: str = 'best_of_3') -> Dict:
        """
        Mérkőzés szimulálása Monte Carlo módszerrel
        """
        # Nyerési valószínűségek számítása
        prob_a_wins_point = self._calculate_point_probability(player_a_stats, player_b_stats)
        
        results = {'A': 0, 'B': 0}
        set_scores = []
        game_counts = []
        
        sets_to_win = 2 if match_format == 'best_of_3' else 3
        
        for _ in range(self.n_simulations):
            sets_a = 0
            sets_b = 0
            total_games = 0
            
            while sets_a < sets_to_win and sets_b < sets_to_win:
                # Egy szett szimulálása
                games_a, games_b = self._simulate_set(prob_a_wins_point)
                total_games += games_a + games_b
                
                if games_a > games_b:
                    sets_a += 1
                else:
                    sets_b += 1
            
            winner = 'A' if sets_a > sets_b else 'B'
            results[winner] += 1
            game_counts.append(total_games)
        
        # Eredmények összegzése
        win_probability = results['A'] / self.n_simulations
        
        return {
            'win_probability_a': win_probability,
            'win_probability_b': 1 - win_probability,
            'expected_games': np.mean(game_counts),
            'median_games': np.median(game_counts),
            'over_21_5_games_pct': sum(1 for g in game_counts if g > 21.5) / self.n_simulations,
            'over_38_5_games_pct': sum(1 for g in game_counts if g > 38.5) / self.n_simulations,
            'three_sets_pct': sum(1 for g in game_counts if g > 22) / self.n_simulations,
            'straight_sets_pct': sum(1 for g in game_counts if g <= 22) / self.n_simulations
        }
    
    def _calculate_point_probability(self, stats_a: Dict, stats_b: Dict) -> float:
        """Pontnyerési valószínűség számítása"""
        # Szerva dominancia alapján
        serve_quality_a = (
            stats_a['first_serve_pct'] / 100 * stats_a['first_serve_won_pct'] / 100 +
            (1 - stats_a['first_serve_pct'] / 100) * stats_a['second_serve_won_pct'] / 100
        )
        
        return_quality_b = stats_b['return_points_won_pct'] / 100
        
        # Kombinált valószínűség
        prob_a = (serve_quality_a + return_quality_b) / 2
        
        return np.clip(prob_a, 0.35, 0.65)
    
    def _simulate_set(self, prob_a_wins_point: float) -> Tuple[int, int]:
        """Egy szett szimulálása"""
        games_a = 0
        games_b = 0
        
        while True:
            # Egy játék szimulálása
            if np.random.random() < prob_a_wins_point:
                games_a += 1
            else:
                games_b += 1
            
            # Szett vége ellenőrzése
            if games_a >= 6 and games_a - games_b >= 2:
                break
            elif games_b >= 6 and games_b - games_a >= 2:
                break
            elif games_a == 7 and games_b == 6:
                break
            elif games_b == 7 and games_a == 6:
                break
            elif games_a == 7 and games_b == 5:
                break
            elif games_b == 7 and games_a == 5:
                break
        
        return games_a, games_b

# ============================================================================
# VALUE BETTING KALKULÁTOR
# ============================================================================

class ValueBetFinder:
    """Value fogadások keresése"""
    
    def __init__(self, kelly_fraction: float = 0.25):
        self.kelly_fraction = kelly_fraction
        
    def analyze_odds(self, predicted_probability: float, odds: Dict[str, float]) -> Dict:
        """
        Odds elemzése és value keresése
        """
        analysis = {}
        
        for bet_type, odd in odds.items():
            if odd <= 1:
                continue
                
            implied_prob = 1 / odd
            edge = predicted_probability - implied_prob
            
            # Kelly tét
            if odd > 1:
                kelly = (predicted_probability * odd - 1) / (odd - 1)
                kelly = max(0, kelly * self.kelly_fraction)
            else:
                kelly = 0
            
            # Value minősítés
            if edge > 0.1:
                rating = "⭐⭐⭐ HIGH VALUE"
            elif edge > 0.05:
                rating = "⭐⭐ VALUE"
            elif edge > 0.02:
                rating = "⭐ SLIGHT VALUE"
            elif edge > -0.02:
                rating = "➖ FAIR"
            else:
                rating = "❌ NO VALUE"
            
            analysis[bet_type] = {
                'odds': odd,
                'implied_probability': implied_prob,
                'predicted_probability': predicted_probability,
                'edge': edge,
                'kelly_stake_pct': kelly * 100,
                'rating': rating,
                'recommendation': 'BACK' if edge > 0.02 else 'LAY' if edge < -0.02 else 'PASS'
            }
        
        return analysis

# ============================================================================
# RIPORT GENERÁLÁS
# ============================================================================

class ReportGenerator:
    """Predikciós riportok generálása"""
    
    @staticmethod
    def generate_match_report(
        player_a: str, 
        player_b: str,
        prediction: Dict,
        monte_carlo: Dict,
        value_bets: Dict,
        match_context: Dict
    ) -> str:
        """
        Teljes mérkőzés riport generálása
        """
        report = f"""
{'='*60}
           🎾 TENNIS AI ANALYST PRO 🎾
{'='*60}

📅 Dátum: {datetime.now().strftime('%Y-%m-%d %H:%M')}

⚡ MÉRKŐZÉS: {player_a} vs {player_b}
🏆 Torna: {match_context.get('tournament', 'Unknown')}
🏟️ Borítás: {match_context.get('surface', 'Unknown').upper()}

{'─'*60}
📊 AI PREDIKCIÓ:
{'─'*60}

Győztes: {'⭐ ' + player_a if prediction['player_a_win_probability'] > 0.5 else '⭐ ' + player_b}
Valószínűség: {prediction['player_a_win_probability']:.1%} vs {1-prediction['player_a_win_probability']:.1%}
Konfidencia: {prediction['confidence']:.1%}
Modell egyetértés: {'✅ Teljes' if prediction['model_agreement'] else '⚠️ Megosztott'}

Egyéni modell predikciók:
"""
        for model, prob in prediction['individual_predictions'].items():
            bar = '█' * int(prob * 20)
            report += f"  • {model:20s}: {bar} {prob:.1%}\n"
        
        report += f"""
{'─'*60}
🎲 MONTE CARLO SZIMULÁCIÓ ({config.mc_simulations:,} szimuláció):
{'─'*60}

{player_a} győzelmi esély: {monte_carlo['win_probability_a']:.1%}
{player_b} győzelmi esély: {monte_carlo['win_probability_b']:.1%}
Várható játékok száma: {monte_carlo['expected_games']:.1f}
3 szettes meccs esélye: {monte_carlo['three_sets_pct']:.1%}
Egyenes szettes győzelem: {monte_carlo['straight_sets_pct']:.1%}

Fogadási piacok:
  • Over 21.5 játék: {monte_carlo['over_21_5_games_pct']:.1%} eséllyel
  • Over 38.5 játék: {monte_carlo['over_38_5_games_pct']:.1%} eséllyel

{'─'*60}
💰 VALUE BETTING ELEMZÉS:
{'─'*60}
"""
        for bet_type, analysis in value_bets.items():
            report += f"""
{bet_type}:
  Odds: {analysis['odds']:.2f}
  Érték: {analysis['edge']:.1%}
  Ajánlott tét: {analysis['kelly_stake_pct']:.1f}% (Kelly/{config.kelly_fraction})
  Értékelés: {analysis['rating']}
  Javaslat: {analysis['recommendation']}
"""
        
        report += f"""
{'─'*60}
⚠️ DISCLAIMER:
Ez egy AI által generált elemzés. A sportfogadás kockázatokkal jár.
A múltbeli teljesítmény nem garancia a jövőbeli eredményekre.
Csak olyan összeggel fogadj, amit megengedhetsz magadnak elveszíteni!
{'='*60}
"""
        return report

# ============================================================================
# FŐ FUNKCIÓ
# ============================================================================

def main():
    """Fő belépési pont"""
    parser = argparse.ArgumentParser(description='Tennis AI Analyst Pro')
    parser.add_argument('--player1', type=str, help='Első játékos neve')
    parser.add_argument('--player2', type=str, help='Második játékos neve')
    parser.add_argument('--surface', type=str, default='hard', 
                       choices=['hard', 'clay', 'grass', 'indoor'],
                       help='Borítás típusa')
    parser.add_argument('--tournament', type=str, help='Torna neve')
    parser.add_argument('--output', type=str, default='text',
                       choices=['text', 'json', 'html'],
                       help='Kimenet formátuma')
    
    args = parser.parse_args()
    
    # Ha nincs megadva játékos, használjunk default értékeket
    player1 = args.player1 or "Novak Djokovic"
    player2 = args.player2 or "Carlos Alcaraz"
    surface = args.surface
    tournament = args.tournament or "Wimbledon"
    
    logger.info(f"Predikció készítése: {player1} vs {player2}")
    
    try:
        # 1. Adatok generálása/betöltése
        logger.info("1/6 Játékos statisztikák betöltése...")
        mock_gen = MockDataGenerator()
        stats_a = mock_gen.generate_player_stats(player1)
        stats_b = mock_gen.generate_player_stats(player2)
        context = mock_gen.generate_match_context()
        
        # Felülírjuk a megadott paraméterekkel
        context['surface'] = surface
        context['tournament'] = tournament
        
        # 2. Feature engineering
        logger.info("2/6 Feature-ök előállítása...")
        feature_eng = FeatureEngineer()
        features = feature_eng.create_features(stats_a, stats_b, context)
        
        # 3. Modell predikciók
        logger.info("3/6 Modell predikciók futtatása...")
        models = TennisPredictionModels()
        
        # Betöltjük vagy létrehozzuk a modelleket
        model_path = config.models_dir / "ensemble_model.joblib"
        if model_path.exists():
            models = joblib.load(model_path)
            logger.info("  Meglévő modell betöltve")
        else:
            logger.info("  Új modell inicializálva (teszt adatokkal)")
            # Normál esetben itt tanítanánk be a modelleket
            # Most csak inicializáljuk őket
            X_dummy = np.random.rand(100, len(feature_eng.feature_names))
            y_dummy = np.random.randint(0, 2, 100)
            models.train(X_dummy, y_dummy)
            joblib.dump(models, model_path)
        
        prediction = models.predict(features)
        
        # 4. Monte Carlo szimuláció
        logger.info("4/6 Monte Carlo szimuláció futtatása...")
        mc_sim = MonteCarloSimulator(n_simulations=config.mc_simulations)
        mc_results = mc_sim.simulate_match(stats_a, stats_b)
        
        # 5. Value betting elemzés
        logger.info("5/6 Value betting elemzés...")
        vbf = ValueBetFinder(kelly_fraction=config.kelly_fraction)
        
        # Mock odds generálása
        odds = {
            f"{player1} győzelem": round(1 / prediction['player_a_win_probability'] * 0.95, 2),
            f"{player2} győzelem": round(1 / (1 - prediction['player_a_win_probability']) * 0.95, 2),
            "Over 21.5 játék": 1.85,
            "Over 38.5 játék": 1.90
        }
        
        value_analysis = vbf.analyze_odds(
            prediction['player_a_win_probability'], 
            odds
        )
        
        # 6. Riport generálása
        logger.info("6/6 Riport generálása...")
        reporter = ReportGenerator()
        
        if args.output == 'json':
            # JSON kimenet
            result = {
                'prediction': prediction,
                'monte_carlo': mc_results,
                'value_bets': value_analysis,
                'match_context': context,
                'timestamp': datetime.now().isoformat()
            }
            output = json.dumps(result, indent=2, default=str)
            print(output)
            
            # JSON fájl mentése
            output_file = config.results_dir / f"prediction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                f.write(output)
            logger.info(f"JSON riport mentve: {output_file}")
            
        elif args.output == 'html':
            # HTML kimenet (később implementálható)
            report = reporter.generate_match_report(
                player1, player2, prediction, mc_results, value_analysis, context
            )
            print(report)
            logger.warning("HTML kimenet még nincs implementálva, text formátum használata")
            
        else:
            # Text kimenet
            report = reporter.generate_match_report(
                player1, player2, prediction, mc_results, value_analysis, context
            )
            print(report)
            
            # Szöveges fájl mentése
            output_file = config.results_dir / f"prediction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"Riport mentve: {output_file}")
        
        logger.info("✅ Predikció sikeresen elkészült!")
        
        # Visszatérési érték a GitHub Actions-hez
        return {
            'prediction': prediction,
            'monte_carlo': mc_results,
            'value_bets': value_analysis
        }
        
    except Exception as e:
        logger.error(f"❌ Hiba történt: {str(e)}")
        raise

if __name__ == "__main__":
    main()
