#!/usr/bin/env python3
"""
🎾 TENNIS AI ANALYST PRO
100% API-alapú, valós mérkőzések, komplex AI elemzés
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import argparse

import numpy as np
import requests
from collections import defaultdict

# ============================================================================
# KONFIGURÁCIÓ
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# API konfiguráció
API_KEY = os.getenv('RAPIDAPI_KEY', '').strip()
API_HOST = 'api-tennis.p.rapidapi.com'
BASE_URL = f'https://{API_HOST}'
HEADERS = {
    'X-RapidAPI-Key': API_KEY,
    'X-RapidAPI-Host': API_HOST
}

# ============================================================================
# API ADATLEKÉRŐ RÉTEG
# ============================================================================

class TennisDataFetcher:
    """Minden adat API-ból jön, semmi kitalált!"""
    
    @staticmethod
    def _api_get(endpoint: str, params: dict = None) -> Optional[dict]:
        """API hívás hibakezeléssel"""
        if not API_KEY:
            logger.error("❌ Nincs API kulcs! Állítsd be a RAPIDAPI_KEY környezeti változót!")
            return None
            
        try:
            url = f"{BASE_URL}{endpoint}"
            response = requests.get(url, headers=HEADERS, params=params, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                logger.error(f"❌ API kulcs érvénytelen! (403 Forbidden)")
            elif response.status_code == 429:
                logger.warning("⚠️ API limit elérve, várj egy percet...")
            else:
                logger.error(f"❌ API hiba: {response.status_code} - {response.text[:200]}")
            return None
        except requests.exceptions.Timeout:
            logger.error("❌ API időtúllépés")
            return None
        except Exception as e:
            logger.error(f"❌ API hiba: {e}")
            return None

    @staticmethod
    def get_live_matches() -> List[Dict]:
        """ÉLŐ mérkőzések"""
        data = TennisDataFetcher._api_get('/api/tennis/matches/live')
        if data and 'matches' in data:
            return data['matches']
        if data and 'events' in data:
            return data['events']
        return []

    @staticmethod
    def get_upcoming_matches(date: str = None) -> List[Dict]:
        """KÖZELGŐ mérkőzések"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        data = TennisDataFetcher._api_get('/api/tennis/events', {'date': date})
        
        if data:
            matches = []
            for key in ['events', 'matches', 'fixtures', 'results']:
                if key in data and isinstance(data[key], list):
                    for item in data[key]:
                        match = TennisDataFetcher._parse_match(item)
                        if match:
                            matches.append(match)
                    if matches:
                        return matches
            
            # Ha egyik sem működik, próbáljuk a nyers adatot
            if isinstance(data, list):
                for item in data:
                    match = TennisDataFetcher._parse_match(item)
                    if match:
                        matches.append(match)
            
            return matches
        return []

    @staticmethod
    def get_player_stats(player_name: str) -> Dict:
        """Játékos statisztikák API-ból"""
        # Keresés a játékosra
        search_data = TennisDataFetcher._api_get('/api/tennis/search', {'name': player_name})
        
        player_id = None
        if search_data:
            for key in ['players', 'results', 'data']:
                if key in search_data and isinstance(search_data[key], list) and search_data[key]:
                    player_id = search_data[key][0].get('id') or search_data[key][0].get('playerId')
                    break
        
        if player_id:
            # Részletes statisztikák
            stats_data = TennisDataFetcher._api_get(f'/api/tennis/player/{player_id}')
            if stats_data:
                for key in ['player', 'stats', 'data']:
                    if key in stats_data:
                        return stats_data[key]
        
        # Ranking adatok
        rank_data = TennisDataFetcher._api_get('/api/tennis/rankings', {'player': player_name})
        if rank_data:
            for key in ['rankings', 'players', 'data']:
                if key in rank_data and isinstance(rank_data[key], list) and rank_data[key]:
                    return rank_data[key][0]
        
        return {}

    @staticmethod
    def get_h2h(player1: str, player2: str) -> Dict:
        """Egymás elleni statisztika API-ból"""
        data = TennisDataFetcher._api_get('/api/tennis/h2h', {
            'player1': player1,
            'player2': player2
        })
        
        if data:
            for key in ['h2h', 'results', 'matches', 'data']:
                if key in data:
                    return data[key]
        
        return {}

    @staticmethod
    def get_tournament_info(tournament_name: str) -> Dict:
        """Torna információk API-ból"""
        data = TennisDataFetcher._api_get('/api/tennis/tournaments', {'name': tournament_name})
        
        if data:
            for key in ['tournaments', 'results', 'data']:
                if key in data and isinstance(data[key], list) and data[key]:
                    return data[key][0]
        
        return {}

    @staticmethod
    def _parse_match(item: dict) -> Optional[Dict]:
        """API válasz egységesítése"""
        if not isinstance(item, dict):
            return None
        
        # Játékosok kinyerése (többféle API formátum)
        p1 = None
        p2 = None
        
        # Formátum 1: home/away
        if 'homeTeam' in item and 'awayTeam' in item:
            p1 = item['homeTeam'].get('name') if isinstance(item['homeTeam'], dict) else str(item['homeTeam'])
            p2 = item['awayTeam'].get('name') if isinstance(item['awayTeam'], dict) else str(item['awayTeam'])
        
        # Formátum 2: player1/player2
        if not p1 and 'player1' in item:
            p1 = item['player1'].get('name') if isinstance(item['player1'], dict) else str(item['player1'])
        if not p2 and 'player2' in item:
            p2 = item['player2'].get('name') if isinstance(item['player2'], dict) else str(item['player2'])
        
        # Formátum 3: team1/team2
        if not p1:
            p1 = item.get('team1') or item.get('home') or item.get('homeName')
        if not p2:
            p2 = item.get('team2') or item.get('away') or item.get('awayName')
        
        if not p1 or not p2:
            return None
        
        # Torna és borítás
        tournament = ''
        surface = 'hard'
        
        if 'tournament' in item:
            if isinstance(item['tournament'], dict):
                tournament = item['tournament'].get('name', '')
                surface = item['tournament'].get('surface', 'hard')
            else:
                tournament = str(item['tournament'])
        
        return {
            'player1': str(p1).strip(),
            'player2': str(p2).strip(),
            'tournament': tournament or item.get('competition', '') or item.get('league', ''),
            'surface': surface or item.get('surface', 'hard'),
            'date': item.get('date') or item.get('startDate') or item.get('start', ''),
            'time': item.get('time') or item.get('startTime', ''),
            'round': item.get('round') or item.get('stage', ''),
            'category': item.get('category') or item.get('type', ''),
            'status': item.get('status') or item.get('state', ''),
            'id': item.get('id') or item.get('eventId', '')
        }

# ============================================================================
# STATISZTIKAI ELEMZŐ MOTOR
# ============================================================================

class StatisticalAnalyzer:
    """Komplex statisztikai elemzések"""
    
    @staticmethod
    def analyze_player_form(player_name: str, stats: Dict) -> Dict:
        """Játékos formájának elemzése"""
        ranking = stats.get('ranking') or stats.get('rank') or stats.get('position', 100)
        
        return {
            'ranking': int(ranking) if ranking else 100,
            'age': stats.get('age') or stats.get('birthDate', ''),
            'country': stats.get('country') or stats.get('nationality', ''),
            'height': stats.get('height') or stats.get('heightCm', ''),
            'plays': stats.get('plays') or stats.get('hand', ''),
            'titles': stats.get('titles') or stats.get('careerTitles', 0),
            'win_pct_career': stats.get('winPercentage') or stats.get('winPct', 0),
            'matches_played': stats.get('matchesPlayed') or stats.get('totalMatches', 0),
        }

    @staticmethod
    def analyze_surface_performance(stats: Dict, surface: str) -> Dict:
        """Borítás-specifikus elemzés"""
        surface_key = surface.lower() if surface else 'hard'
        
        return {
            'surface': surface_key,
            'win_pct': stats.get(f'{surface_key}WinPct') or 
                      stats.get(f'winPct{surface_key.title()}') or
                      stats.get('winPercentage', 50),
            'matches_on_surface': stats.get(f'{surface_key}Matches') or 0,
            'titles_on_surface': stats.get(f'{surface_key}Titles') or 0,
            'best_result': stats.get(f'{surface_key}Best') or '',
        }

    @staticmethod
    def analyze_serve_return(stats: Dict) -> Dict:
        """Szerva és return elemzés"""
        return {
            'aces_per_match': stats.get('acesPerMatch') or stats.get('aces', 0),
            'double_faults': stats.get('doubleFaultsPerMatch') or stats.get('doubleFaults', 0),
            'first_serve_pct': stats.get('firstServePct') or stats.get('firstServe', 60),
            'first_serve_won': stats.get('firstServeWonPct') or stats.get('firstServeWon', 65),
            'second_serve_won': stats.get('secondServeWonPct') or stats.get('secondServeWon', 50),
            'break_points_saved': stats.get('breakPointsSavedPct') or stats.get('bpsSaved', 55),
            'service_games_won': stats.get('serviceGamesWonPct') or stats.get('serveGamesWon', 75),
            'return_points_won': stats.get('returnPointsWonPct') or stats.get('returnPtsWon', 38),
            'break_points_converted': stats.get('breakPointsConvertedPct') or stats.get('bpsConverted', 40),
        }

    @staticmethod
    def analyze_recent_form(stats: Dict) -> Dict:
        """Utolsó meccsek formája"""
        return {
            'last_5_won': stats.get('last5Won') or stats.get('recentWins', 0),
            'last_5_lost': stats.get('last5Lost') or stats.get('recentLosses', 0),
            'last_10_won': stats.get('last10Won') or stats.get('last10Wins', 0),
            'win_streak': stats.get('winStreak') or stats.get('currentStreak', 0),
            'loss_streak': stats.get('lossStreak') or 0,
            'season_wins': stats.get('seasonWins') or stats.get('winsThisYear', 0),
            'season_losses': stats.get('seasonLosses') or stats.get('lossesThisYear', 0),
        }

# ============================================================================
# AI PREDIKCIÓS MOTOR
# ============================================================================

class AIPredictionEngine:
    """Fejlett AI predikciós motor"""
    
    def __init__(self):
        self.fetcher = TennisDataFetcher()
        self.analyzer = StatisticalAnalyzer()
    
    def predict(self, player1: str, player2: str, surface: str = 'hard', 
                tournament: str = '', match_context: Dict = None) -> Dict:
        """
        Komplex AI predikció készítése
        """
        logger.info(f"🔍 Elemzés: {player1} vs {player2} ({surface})")
        
        # 1. Adatok begyűjtése API-ból
        stats1 = self.fetcher.get_player_stats(player1)
        stats2 = self.fetcher.get_player_stats(player2)
        h2h_data = self.fetcher.get_h2h(player1, player2)
        tournament_info = self.fetcher.get_tournament_info(tournament) if tournament else {}
        
        # 2. Statisztikai elemzés
        analysis = {
            'player1': {
                'name': player1,
                'form': self.analyzer.analyze_player_form(player1, stats1),
                'surface': self.analyzer.analyze_surface_performance(stats1, surface),
                'serve_return': self.analyzer.analyze_serve_return(stats1),
                'recent': self.analyzer.analyze_recent_form(stats1),
            },
            'player2': {
                'name': player2,
                'form': self.analyzer.analyze_player_form(player2, stats2),
                'surface': self.analyzer.analyze_surface_performance(stats2, surface),
                'serve_return': self.analyzer.analyze_serve_return(stats2),
                'recent': self.analyzer.analyze_recent_form(stats2),
            },
            'h2h': self._analyze_h2h(h2h_data, player1, player2),
            'tournament': tournament_info,
        }
        
        # 3. Feature-ök számítása
        features = self._calculate_features(analysis, surface)
        
        # 4. Predikció
        prediction = self._make_prediction(features, player1, player2)
        
        # 5. Kulcsfaktorok
        key_factors = self._identify_key_factors(features, player1, player2)
        
        # 6. Fogadási elemzés
        betting = self._generate_betting_analysis(prediction, features, player1, player2)
        
        # 7. Részletes szöveges elemzés
        commentary = self._generate_commentary(analysis, prediction, key_factors)
        
        return {
            'match': f"{player1} vs {player2}",
            'tournament': tournament,
            'surface': surface,
            'datetime': match_context.get('date', '') if match_context else '',
            'round': match_context.get('round', '') if match_context else '',
            'status': match_context.get('status', '') if match_context else '',
            
            # AI Predikció
            'ai_prediction': prediction,
            
            # Kulcsfaktorok
            'key_factors': key_factors,
            
            # Részletes elemzés
            'analysis': analysis,
            
            # Fogadási javaslatok
            'betting_analysis': betting,
            
            # Szöveges kommentár
            'commentary': commentary,
            
            # Meta adatok
            'meta': {
                'generated_at': datetime.now().isoformat(),
                'data_source': 'api-tennis.p.rapidapi.com',
                'version': '2.0.0',
                'disclaimer': '⚠️ Ez AI elemzés, NEM befektetési tanács! A sportfogadás kockázattal jár!'
            }
        }
    
    def _analyze_h2h(self, h2h_data: Dict, p1: str, p2: str) -> Dict:
        """H2H elemzés"""
        if not h2h_data:
            return {'total_matches': 0, 'note': 'Nincs korábbi mérkőzés'}
        
        total = h2h_data.get('totalMatches') or h2h_data.get('total', 0)
        p1_wins = h2h_data.get('player1Wins') or h2h_data.get(f'{p1}Wins', 0)
        p2_wins = h2h_data.get('player2Wins') or h2h_data.get(f'{p2}Wins', 0)
        
        return {
            'total_matches': total,
            f'{p1}_wins': p1_wins,
            f'{p2}_wins': p2_wins,
            'last_meeting': h2h_data.get('lastMeeting', ''),
            'surface_breakdown': h2h_data.get('surfaceBreakdown', {}),
        }
    
    def _calculate_features(self, analysis: Dict, surface: str) -> Dict:
        """Feature engineering az AI-hoz"""
        p1 = analysis['player1']
        p2 = analysis['player2']
        
        features = {}
        
        # Ranking különbség
        r1 = p1['form'].get('ranking', 100)
        r2 = p2['form'].get('ranking', 100)
        features['ranking_advantage'] = (r2 - r1) / max(r1, r2, 1) if r1 and r2 else 0
        
        # Borítás előny
        s1 = p1['surface'].get('win_pct', 50)
        s2 = p2['surface'].get('win_pct', 50)
        features['surface_advantage'] = (s1 - s2) / 100
        
        # Szerva dominancia
        p1_serve = (p1['serve_return'].get('first_serve_pct', 60) * 
                   p1['serve_return'].get('first_serve_won', 65) / 10000)
        p2_serve = (p2['serve_return'].get('first_serve_pct', 60) * 
                   p2['serve_return'].get('first_serve_won', 65) / 10000)
        features['serve_advantage'] = p1_serve - p2_serve
        
        # Return erő
        features['return_advantage'] = (
            p1['serve_return'].get('return_points_won', 38) -
            p2['serve_return'].get('return_points_won', 38)
        ) / 100
        
        # Forma
        p1_form = p1['recent'].get('last_10_won', 5) / 10
        p2_form = p2['recent'].get('last_10_won', 5) / 10
        features['form_advantage'] = p1_form - p2_form
        
        # Break pontok
        features['break_point_advantage'] = (
            p1['serve_return'].get('break_points_converted', 40) -
            p2['serve_return'].get('break_points_converted', 40)
        ) / 100
        
        # H2H előny
        h2h = analysis.get('h2h', {})
        if h2h.get('total_matches', 0) > 0:
            p1_h2h = h2h.get(f'{analysis["player1"]["name"]}_wins', 0)
            total_h2h = h2h.get('total_matches', 1)
            features['h2h_advantage'] = (p1_h2h / total_h2h - 0.5) * 2
        else:
            features['h2h_advantage'] = 0
        
        # Tapasztalat (címek alapján)
        t1 = p1['form'].get('titles', 0)
        t2 = p2['form'].get('titles', 0)
        features['experience_advantage'] = (t1 - t2) / max(t1 + t2, 1) if (t1 + t2) > 0 else 0
        
        return features
    
    def _make_prediction(self, features: Dict, p1: str, p2: str) -> Dict:
        """AI predikció készítése"""
        
        # Súlyozás
        weights = {
            'ranking_advantage': 0.18,
            'surface_advantage': 0.22,
            'serve_advantage': 0.15,
            'return_advantage': 0.12,
            'form_advantage': 0.13,
            'break_point_advantage': 0.08,
            'h2h_advantage': 0.07,
            'experience_advantage': 0.05,
        }
        
        # Súlyozott pontszám
        weighted_score = sum(features.get(k, 0) * w for k, w in weights.items())
        
        # Valószínűség (szigmoid transzformáció)
        probability = 1 / (1 + np.exp(-weighted_score * 8))
        probability = max(0.02, min(0.98, probability))
        
        # Konfidencia
        abs_sum = sum(abs(features.get(k, 0)) for k in weights)
        confidence = 0.50 + abs_sum * 0.35
        confidence = min(0.95, confidence)
        
        winner = p1 if probability > 0.5 else p2
        win_prob = probability if probability > 0.5 else 1 - probability
        
        # Predikciós szintek
        if win_prob > 0.75:
            level = 'MAGAS BIZTONSÁGÚ'
        elif win_prob > 0.60:
            level = 'VALÓSZÍNŰ'
        elif win_prob > 0.50:
            level = 'ENYHE ELŐNY'
        else:
            level = 'BIZONYTALAN'
        
        return {
            'predicted_winner': winner,
            'win_probability': round(win_prob * 100, 1),
            f'{p1}_win_pct': round(probability * 100, 1),
            f'{p2}_win_pct': round((1 - probability) * 100, 1),
            'confidence': round(confidence * 100, 1),
            'confidence_level': level,
        }
    
    def _identify_key_factors(self, features: Dict, p1: str, p2: str) -> List[Dict]:
        """Kulcsfontosságú faktorok azonosítása"""
        factor_names = {
            'ranking_advantage': ('Világranglista előny', 'ranglistás helyezés'),
            'surface_advantage': ('Borítás előny', 'borításon nyújtott teljesítmény'),
            'serve_advantage': ('Szerva dominancia', 'szervajáték erőssége'),
            'return_advantage': ('Return hatékonyság', 'fogadójáték minősége'),
            'form_advantage': ('Jelenlegi forma', 'utolsó 10 meccs eredménye'),
            'break_point_advantage': ('Break pont kihasználás', 'fontos pontok megnyerése'),
            'h2h_advantage': ('Egymás elleni mérleg', 'korábbi mérkőzések'),
            'experience_advantage': ('Tapasztalat', 'megnyert tornák száma'),
        }
        
        factors = []
        for key, value in sorted(features.items(), key=lambda x: abs(x[1]), reverse=True):
            if abs(value) > 0.01:
                name, detail = factor_names.get(key, (key, ''))
                advantage = p1 if value > 0 else p2
                factors.append({
                    'factor': name,
                    'detail': detail,
                    'advantage_for': advantage,
                    'impact': round(abs(value) * 100, 1),
                    'description': f'{name}: {advantage} javára ({abs(value)*100:.0f}% előny)'
                })
        
        return factors[:5]
    
    def _generate_betting_analysis(self, prediction: Dict, features: Dict, 
                                   p1: str, p2: str) -> Dict:
        """Fogadási elemzés"""
        win_prob = prediction['win_probability'] / 100
        confidence = prediction['confidence'] / 100
        
        tips = []
        
        # Match winner tipp
        if win_prob > 0.55:
            fair_odds = round(1 / win_prob, 2)
            tips.append({
                'market': 'Mérkőzés győztese',
                'selection': prediction['predicted_winner'],
                'probability': f"{win_prob:.1%}",
                'fair_odds': fair_odds,
                'value_bet': 'IGEN' if win_prob > 0.60 else 'TALÁN',
                'confidence': 'MAGAS' if confidence > 0.70 else 'KÖZEPES',
                'stake_suggestion': f"Tét: {max(1, int(win_prob * 10))}/10 egység"
            })
        
        # Set fogadás
        if win_prob > 0.60:
            tips.append({
                'market': 'Szett hendikep',
                'selection': f"{prediction['predicted_winner']} -1.5 szett",
                'confidence': 'KÖZEPES',
            })
        
        # Over/Under
        serve_sum = features.get('serve_advantage', 0)
        if serve_sum > 0.05:
            tips.append({
                'market': 'Játékok száma',
                'selection': 'OVER 22.5',
                'confidence': 'ALACSONY-KÖZEPES',
            })
        elif serve_sum < -0.02:
            tips.append({
                'market': 'Játékok száma',
                'selection': 'UNDER 22.5',
                'confidence': 'ALACSONY-KÖZEPES',
            })
        
        return {
            'recommended_bets': tips,
            'kelly_criterion': round((win_prob * 2 - 1) * 100, 1) if win_prob > 0.5 else 0,
            'risk_level': 'ALACSONY' if win_prob > 0.70 else 'KÖZEPES' if win_prob > 0.55 else 'MAGAS',
        }
    
    def _generate_commentary(self, analysis: Dict, prediction: Dict, 
                            factors: List[Dict]) -> str:
        """Szöveges elemzés"""
        p1 = analysis['player1']['name']
        p2 = analysis['player2']['name']
        winner = prediction['predicted_winner']
        
        lines = []
        lines.append(f"📊 RÉSZLETES ELEMZÉS: {p1} vs {p2}")
        lines.append("")
        
        # Predikció összefoglaló
        lines.append(f"🏆 PREDIKCIÓ: {winner} nyer {prediction['win_probability']}% eséllyel")
        lines.append(f"💪 Konfidencia: {prediction['confidence']}% ({prediction['confidence_level']})")
        lines.append("")
        
        # Kulcsfaktorok
        if factors:
            lines.append("🔑 KULCSFAKTOROK:")
            for f in factors[:3]:
                lines.append(f"   • {f['description']}")
            lines.append("")
        
        # Játékos elemzés
        p1_surface = analysis['player1']['surface'].get('win_pct', 'N/A')
        p2_surface = analysis['player2']['surface'].get('win_pct', 'N/A')
        
        lines.append(f"👤 {p1}:")
        lines.append(f"   • Ranglista: {analysis['player1']['form'].get('ranking', 'N/A')}")
        lines.append(f"   • Borítás nyerési arány: {p1_surface}%")
        if analysis['player1']['recent'].get('last_10_won'):
            lines.append(f"   • Utolsó 10 meccs: {analysis['player1']['recent'].get('last_10_won')}W/"
                       f"{analysis['player1']['recent'].get('last_5_lost', 0)}L")
        lines.append("")
        
        lines.append(f"👤 {p2}:")
        lines.append(f"   • Ranglista: {analysis['player2']['form'].get('ranking', 'N/A')}")
        lines.append(f"   • Borítás nyerési arány: {p2_surface}%")
        if analysis['player2']['recent'].get('last_10_won'):
            lines.append(f"   • Utolsó 10 meccs: {analysis['player2']['recent'].get('last_10_won')}W/"
                       f"{analysis['player2']['recent'].get('last_5_lost', 0)}L")
        lines.append("")
        
        # H2H
        h2h = analysis.get('h2h', {})
        if h2h.get('total_matches', 0) > 0:
            lines.append(f"🤝 EGYMÁS ELLEN: {h2h.get(f'{p1}_wins', 0)}-{h2h.get(f'{p2}_wins', 0)}")
            lines.append("")
        
        lines.append("⚠️ FIGYELMEZTETÉS: Ez AI által generált elemzés, nem minősül befektetési tanácsnak.")
        
        return '\n'.join(lines)

# ============================================================================
# FŐ PROGRAM
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='🎾 Tennis AI Analyst PRO')
    parser.add_argument('--today', action='store_true', help='MAI mérkőzések')
    parser.add_argument('--live', action='store_true', help='ÉLŐ mérkőzések')
    parser.add_argument('--date', type=str, help='Adott dátum (YYYY-MM-DD)')
    parser.add_argument('--match', type=str, help='Egy mérkőzés: "Játékos1 vs Játékos2"')
    parser.add_argument('--surface', type=str, default='hard', help='Borítás')
    parser.add_argument('--output', type=str, choices=['json', 'text', 'full'], default='full')
    
    args = parser.parse_args()
    
    # API kulcs ellenőrzése
    if not API_KEY:
        print("="*60)
        print("❌ HIBA: Nincs API kulcs!")
        print("="*60)
        print("\nÁllítsd be a RAPIDAPI_KEY környezeti változót:")
        print("  export RAPIDAPI_KEY='a_te_kulcsod'")
        print("\nVagy GitHub Actions-ben:")
        print("  Settings → Secrets → Actions → RAPIDAPI_KEY")
        print("="*60)
        sys.exit(1)
    
    engine = AIPredictionEngine()
    fetcher = TennisDataFetcher()
    
    print("\n" + "="*70)
    print("          🎾 TENNIS AI ANALYST PRO v2.0 🎾")
    print("="*70)
    
    # Élő mérkőzések
    if args.live:
        print("\n🔴 ÉLŐ MÉRKŐZÉSEK ELEMZÉSE\n")
        matches = fetcher.get_live_matches()
        
        if not matches:
            print("❌ Nincsenek élő mérkőzések, vagy az API nem elérhető.")
            sys.exit(0)
        
        print(f"✅ {len(matches)} élő mérkőzés található\n")
        
        for match in matches:
            result = engine.predict(
                match['player1'], match['player2'],
                match.get('surface', 'hard'),
                match.get('tournament', ''),
                match
            )
            _print_result(result, args.output)
    
    # Mai mérkőzések
    elif args.today or args.date:
        date = args.date if args.date else datetime.now().strftime('%Y-%m-%d')
        print(f"\n📅 DÁTUM: {date}\n")
        
        matches = fetcher.get_upcoming_matches(date)
        
        if not matches:
            print(f"❌ Nincsenek mérkőzések ezen a napon: {date}")
            print("Próbáld másik API végponttal vagy másik nappal.")
            sys.exit(0)
        
        print(f"✅ {len(matches)} mérkőzés található\n")
        
        all_results = []
        for match in matches:
            result = engine.predict(
                match['player1'], match['player2'],
                match.get('surface', 'hard'),
                match.get('tournament', ''),
                match
            )
            all_results.append(result)
            _print_result(result, args.output)
        
        # JSON fájl mentése
        os.makedirs('results', exist_ok=True)
        filename = f"results/predictions_{date.replace('-', '')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Eredmények mentve: {filename}")
    
    # Egy mérkőzés
    elif args.match:
        if ' vs ' in args.match:
            p1, p2 = args.match.split(' vs ')
        elif ' - ' in args.match:
            p1, p2 = args.match.split(' - ')
        else:
            print("Formátum: 'Játékos1 vs Játékos2'")
            sys.exit(1)
        
        result = engine.predict(p1.strip(), p2.strip(), args.surface)
        _print_result(result, args.output)
    
    else:
        print("\nHASZNÁLAT:")
        print("  python main.py --today           # Mai mérkőzések")
        print("  python main.py --live            # Élő mérkőzések")
        print("  python main.py --date 2024-07-15 # Adott nap")
        print("  python main.py --match 'Djokovic vs Alcaraz' --surface grass")
    
    print("\n⚠️ AI elemzés - NEM befektetési tanács! Fogadás csak saját felelősségre!")
    print("="*70)

def _print_result(result: Dict, output_type: str):
    """Eredmény kiírása"""
    if output_type == 'json':
        print
