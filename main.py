#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
🎾 TENNIS AI ANALYST PRO
API Tennis alapú teniszelemző
============================================================

API:
    https://api.api-tennis.com/tennis/

API kulcs:
    RAPIDAPI_KEY helyett API_TENNIS_KEY

GitHub Actions Secret:
    API_TENNIS_KEY

Használat:
    python main.py --today
    python main.py --tomorrow
    python main.py --live
    python main.py --date 2026-08-10
    python main.py --match "Carlos Alcaraz vs Novak Djokovic"
    python main.py --match "Carlos Alcaraz vs Novak Djokovic" --surface hard
"""

import os
import sys
import json
import math
import time
import logging
import argparse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests


# ============================================================
# KONFIGURÁCIÓ
# ============================================================

API_KEY = os.getenv("API_TENNIS_KEY", "").strip()

BASE_URL = "https://api.api-tennis.com/tennis/"

TIMEZONE = "Europe/Budapest"

REQUEST_TIMEOUT = 30

# Mennyi historikus meccset használjunk játékosforma számításához
FORM_MATCH_LIMIT = 20

# Cache
CACHE_DIR = "cache"
RESULTS_DIR = "results"

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("tennis-ai")


# ============================================================
# SEGÉDFÜGGVÉNYEK
# ============================================================

def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Biztonságos float konverzió."""

    if value is None:
        return default

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    if not text:
        return default

    text = text.replace("%", "").replace(",", ".")

    try:
        return float(text)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """Biztonságos integer konverzió."""

    if value is None:
        return default

    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return default


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def normalize_name(name: str) -> str:
    """Játékosnév összehasonlításhoz."""

    return " ".join(
        str(name).lower().replace(".", "").split()
    )


def parse_date(value: str) -> Optional[datetime]:
    """Dátum/idő felismerése."""

    if not value:
        return None

    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


def sigmoid(x: float) -> float:
    """Numerikusan stabil sigmoid."""

    if x < -50:
        return 0.0

    if x > 50:
        return 1.0

    return 1.0 / (1.0 + math.exp(-x))


# ============================================================
# API CLIENT
# ============================================================

class TennisAPI:

    def __init__(self):
        if not API_KEY:
            raise RuntimeError(
                "\n"
                "❌ NINCS API KULCS!\n\n"
                "Állítsd be ezt a környezeti változót:\n"
                "API_TENNIS_KEY\n\n"
                "GitHub Actions esetén:\n"
                "Settings → Secrets and variables → Actions\n"
                "→ New repository secret\n"
                "Name: API_TENNIS_KEY\n"
            )

        self.session = requests.Session()

    # --------------------------------------------------------
    # ALAP API REQUEST
    # --------------------------------------------------------

    def request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:

        query = {
            "method": method,
            "APIkey": API_KEY
        }

        if params:
            for key, value in params.items():
                if value is not None and value != "":
                    query[key] = value

        try:

            response = self.session.get(
                BASE_URL,
                params=query,
                timeout=REQUEST_TIMEOUT
            )

        except requests.exceptions.Timeout:
            logger.error("❌ API timeout: %s", method)
            return None

        except requests.exceptions.RequestException as exc:
            logger.error("❌ API kapcsolat hiba: %s", exc)
            return None

        if response.status_code != 200:

            logger.error(
                "❌ HTTP %s: %s",
                response.status_code,
                response.text[:300]
            )

            return None

        try:
            data = response.json()
        except ValueError:
            logger.error("❌ Az API nem JSON választ adott.")
            return None

        if not isinstance(data, dict):
            logger.error("❌ Érvénytelen API válasz.")
            return None

        if data.get("success") != 1:

            logger.error(
                "❌ API hiba: %s",
                data.get("error") or data.get("message") or data
            )

            return None

        return data

    # --------------------------------------------------------
    # FIXTURES
    # --------------------------------------------------------

    def get_fixtures(
        self,
        date_start: str,
        date_stop: Optional[str] = None,
        match_key: Optional[str] = None,
        player_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:

        if date_stop is None:
            date_stop = date_start

        data = self.request(
            "get_fixtures",
            {
                "date_start": date_start,
                "date_stop": date_stop,
                "match_key": match_key,
                "player_key": player_key,
                "timezone": TIMEZONE
            }
        )

        if not data:
            return []

        result = data.get("result", [])

        if isinstance(result, list):
            return result

        return []

    # --------------------------------------------------------
    # LIVE
    # --------------------------------------------------------

    def get_livescore(self) -> List[Dict[str, Any]]:

        data = self.request(
            "get_livescore",
            {
                "timezone": TIMEZONE
            }
        )

        if not data:
            return []

        result = data.get("result", [])

        return result if isinstance(result, list) else []

    # --------------------------------------------------------
    # H2H
    # --------------------------------------------------------

    def get_h2h(
        self,
        player1_key: str,
        player2_key: str
    ) -> Dict[str, Any]:

        data = self.request(
            "get_H2H",
            {
                "first_player_key": player1_key,
                "second_player_key": player2_key
            }
        )

        if not data:
            return {}

        result = data.get("result", {})

        return result if isinstance(result, dict) else {}

    # --------------------------------------------------------
    # PLAYER
    # --------------------------------------------------------

    def get_player(
        self,
        player_key: str
    ) -> Optional[Dict[str, Any]]:

        data = self.request(
            "get_players",
            {
                "player_key": player_key
            }
        )

        if not data:
            return None

        result = data.get("result", [])

        if isinstance(result, list) and result:
            return result[0]

        return None

    # --------------------------------------------------------
    # STANDINGS
    # --------------------------------------------------------

    def get_standings(
        self,
        tour: str
    ) -> List[Dict[str, Any]]:

        data = self.request(
            "get_standings",
            {
                "event_type": tour.upper()
            }
        )

        if not data:
            return []

        result = data.get("result", [])

        return result if isinstance(result, list) else []

    # --------------------------------------------------------
    # ODDS
    # --------------------------------------------------------

    def get_odds(
        self,
        match_key: str
    ) -> Dict[str, Any]:

        data = self.request(
            "get_odds",
            {
                "match_key": match_key
            }
        )

        if not data:
            return {}

        result = data.get("result", {})

        return result if isinstance(result, dict) else {}

    # --------------------------------------------------------
    # EVENTS
    # --------------------------------------------------------

    def get_events(self) -> List[Dict[str, Any]]:

        data = self.request("get_events")

        if not data:
            return []

        result = data.get("result", [])

        return result if isinstance(result, list) else []

    # --------------------------------------------------------
    # TOURNAMENTS
    # --------------------------------------------------------

    def get_tournaments(self) -> List[Dict[str, Any]]:

        data = self.request("get_tournaments")

        if not data:
            return []

        result = data.get("result", [])

        return result if isinstance(result, list) else []


# ============================================================
# MATCH NORMALIZER
# ============================================================

class MatchNormalizer:

    @staticmethod
    def normalize(match: Dict[str, Any]) -> Dict[str, Any]:

        return {
            "match_key": str(
                match.get("event_key", "")
            ),

            "player1": str(
                match.get("event_first_player", "")
            ).strip(),

            "player1_key": str(
                match.get("first_player_key", "")
            ),

            "player2": str(
                match.get("event_second_player", "")
            ).strip(),

            "player2_key": str(
                match.get("second_player_key", "")
            ),

            "date": match.get("event_date", ""),

            "time": match.get("event_time", ""),

            "status": match.get("event_status", ""),

            "winner": match.get("event_winner"),

            "final_result": match.get(
                "event_final_result",
                ""
            ),

            "game_result": match.get(
                "event_game_result",
                ""
            ),

            "live": str(
                match.get("event_live", "0")
            ) == "1",

            "tournament": match.get(
                "tournament_name",
                ""
            ),

            "tournament_key": str(
                match.get("tournament_key", "")
            ),

            "round": match.get(
                "tournament_round",
                ""
            ),

            "season": match.get(
                "tournament_season",
                ""
            ),

            "event_type": match.get(
                "event_type_type",
                ""
            ),

            "scores": match.get(
                "scores",
                []
            ) or [],

            "statistics": match.get(
                "statistics",
                []
            ) or [],

            "pointbypoint": match.get(
                "pointbypoint",
                []
            ) or []
        }

    # --------------------------------------------------------

    @staticmethod
    def surface_from_tournament(
        tournament: str
    ) -> str:

        text = tournament.lower()

        if "clay" in text:
            return "clay"

        if "grass" in text:
            return "grass"

        return "hard"


# ============================================================
# STATISTICS PARSER
# ============================================================

class StatisticsParser:

    @staticmethod
    def parse(
        match: Dict[str, Any]
    ) -> Dict[str, Dict[str, float]]:

        result = {
            "player1": {},
            "player2": {}
        }

        p1_key = str(match.get("player1_key"))
        p2_key = str(match.get("player2_key"))

        stats = match.get("statistics", [])

        if not isinstance(stats, list):
            return result

        for stat in stats:

            if not isinstance(stat, dict):
                continue

            player_key = str(
                stat.get("player_key", "")
            )

            if player_key == p1_key:
                target = result["player1"]

            elif player_key == p2_key:
                target = result["player2"]

            else:
                continue

            name = str(
                stat.get("stat_name", "")
            ).lower().strip()

            value = safe_float(
                stat.get("stat_value")
            )

            if value is None:
                continue

            if "ace" in name:
                target["aces"] = value

            elif "double fault" in name:
                target["double_faults"] = value

            elif "1st serve points won" in name:
                target["first_serve_points_won"] = value

            elif "2nd serve points won" in name:
                target["second_serve_points_won"] = value

            elif "break points won" in name:
                target["break_points_won"] = value

            elif "break points converted" in name:
                target["break_points_converted"] = value

            elif "service games won" in name:
                target["service_games_won"] = value

            elif "return points won" in name:
                target["return_points_won"] = value

            elif "1st serve" in name and "%" in name:
                target["first_serve_pct"] = value

        return result


# ============================================================
# HISTORIKUS FORMA
# ============================================================

class FormAnalyzer:

    def __init__(self, api: TennisAPI):
        self.api = api

    # --------------------------------------------------------

    def get_recent_matches(
        self,
        player_key: str,
        days: int = 120
    ) -> List[Dict[str, Any]]:

        end = datetime.now()
        start = end - timedelta(days=days)

        fixtures = self.api.get_fixtures(
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
            player_key=player_key
        )

        finished = []

        for raw in fixtures:

            match = MatchNormalizer.normalize(raw)

            if match["status"].lower() != "finished":
                continue

            if not match["winner"]:
                continue

            finished.append(match)

        finished.sort(
            key=lambda x: (
                x["date"],
                x["time"]
            ),
            reverse=True
        )

        return finished[:FORM_MATCH_LIMIT]

    # --------------------------------------------------------

    def analyze(
        self,
        player_key: str,
        player_name: str,
        surface: str
    ) -> Dict[str, Any]:

        matches = self.get_recent_matches(player_key)

        total = len(matches)
        wins = 0
        losses = 0

        surface_total = 0
        surface_wins = 0

        sets_won = 0
        sets_lost = 0

        recent_opponents = []

        for match in matches:

            is_player1 = (
                str(match["player1_key"]) == str(player_key)
            )

            winner = match["winner"]

            won = (
                (is_player1 and winner == "First Player")
                or
                (not is_player1 and winner == "Second Player")
            )

            if won:
                wins += 1
            else:
                losses += 1

            opponent = (
                match["player2"]
                if is_player1
                else match["player1"]
            )

            recent_opponents.append(opponent)

            match_surface = MatchNormalizer.surface_from_tournament(
                match["tournament"]
            )

            if match_surface == surface:
                surface_total += 1

                if won:
                    surface_wins += 1

            # Szettek
            for score in match["scores"]:

                if not isinstance(score, dict):
                    continue

                s1 = safe_int(
                    score.get("score_first")
                )

                s2 = safe_int(
                    score.get("score_second")
                )

                if s1 is None or s2 is None:
                    continue

                if is_player1:

                    if s1 > s2:
                        sets_won += 1
                    elif s2 > s1:
                        sets_lost += 1

                else:

                    if s2 > s1:
                        sets_won += 1
                    elif s1 > s2:
                        sets_lost += 1

        win_pct = (
            wins / total * 100
            if total
            else None
        )

        surface_pct = (
            surface_wins / surface_total * 100
            if surface_total
            else None
        )

        return {
            "player": player_name,
            "player_key": str(player_key),
            "matches": total,
            "wins": wins,
            "losses": losses,
            "win_pct": win_pct,
            "surface_matches": surface_total,
            "surface_wins": surface_wins,
            "surface_win_pct": surface_pct,
            "sets_won": sets_won,
            "sets_lost": sets_lost,
            "recent_opponents": recent_opponents
        }


# ============================================================
# RANKING
# ============================================================

class RankingAnalyzer:

    def __init__(self, api: TennisAPI):
        self.api = api

    def find_player_rank(
        self,
        player_key: str,
        tour: str
    ) -> Optional[int]:

        standings = self.api.get_standings(tour)

        for item in standings:

            if str(item.get("player_key")) == str(player_key):

                return safe_int(
                    item.get("place")
                )

        return None


# ============================================================
# H2H ANALYZER
# ============================================================

class H2HAnalyzer:

    @staticmethod
    def analyze(
        h2h: Dict[str, Any],
        player1_key: str,
        player2_key: str,
        surface: str
    ) -> Dict[str, Any]:

        meetings = h2h.get("H2H", [])

        if not isinstance(meetings, list):
            meetings = []

        p1_wins = 0
        p2_wins = 0

        surface_meetings = 0
        surface_p1_wins = 0

        for match in meetings:

            winner = match.get("event_winner")

            first_key = str(
                match.get("first_player_key", "")
            )

            second_key = str(
                match.get("second_player_key", "")
            )

            if winner == "First Player":
                winner_key = first_key

            elif winner == "Second Player":
                winner_key = second_key

            else:
                continue

            if winner_key == str(player1_key):
                p1_wins += 1

            elif winner_key == str(player2_key):
                p2_wins += 1

            tournament = str(
                match.get("tournament_name", "")
            )

            match_surface = MatchNormalizer.surface_from_tournament(
                tournament
            )

            if match_surface == surface:

                surface_meetings += 1

                if winner_key == str(player1_key):
                    surface_p1_wins += 1

        total = p1_wins + p2_wins

        return {
            "total": total,
            "player1_wins": p1_wins,
            "player2_wins": p2_wins,
            "surface_total": surface_meetings,
            "surface_player1_wins": surface_p1_wins
        }


# ============================================================
# PREDICTION ENGINE
# ============================================================

class PredictionEngine:

    def __init__(self, api: TennisAPI):

        self.api = api

        self.form = FormAnalyzer(api)

        self.rankings = RankingAnalyzer(api)

    # --------------------------------------------------------

    def _ranking_score(
        self,
        rank1: Optional[int],
        rank2: Optional[int]
    ) -> float:

        if rank1 is None or rank2 is None:
            return 0.0

        value = math.log(rank2 + 1) - math.log(rank1 + 1)

        return clamp(value / 3.0, -1.0, 1.0)

    # --------------------------------------------------------

    def _form_score(
        self,
        form1: Dict[str, Any],
        form2: Dict[str, Any]
    ) -> float:

        w1 = form1.get("win_pct")
        w2 = form2.get("win_pct")

        if w1 is None or w2 is None:
            return 0.0

        return clamp(
            (w1 - w2) / 100.0,
            -1.0,
            1.0
        )

    # --------------------------------------------------------

    def _surface_score(
        self,
        form1: Dict[str, Any],
        form2: Dict[str, Any]
    ) -> float:

        s1 = form1.get("surface_win_pct")
        s2 = form2.get("surface_win_pct")

        if s1 is None or s2 is None:
            return 0.0

        return clamp(
            (s1 - s2) / 100.0,
            -1.0,
            1.0
        )

    # --------------------------------------------------------

    def _h2h_score(
        self,
        h2h: Dict[str, Any]
    ) -> float:

        total = h2h.get("total", 0)

        if total <= 0:
            return 0.0

        return clamp(
            (
                h2h["player1_wins"] / total
            ) - 0.5,
            -0.5,
            0.5
        ) * 2

    # --------------------------------------------------------

    def _player_stats_score(
        self,
        stats1: Dict[str, float],
        stats2: Dict[str, float]
    ) -> float:

        components = []

        keys = [
            "aces",
            "first_serve_points_won",
            "second_serve_points_won",
            "return_points_won",
            "break_points_converted",
            "service_games_won"
        ]

        for key in keys:

            v1 = stats1.get(key)
            v2 = stats2.get(key)

            if v1 is None or v2 is None:
                continue

            difference = (
                v1 - v2
            ) / 100.0

            components.append(difference)

        if not components:
            return 0.0

        return clamp(
            sum(components) / len(components),
            -1.0,
            1.0
        )

    # --------------------------------------------------------
    # SET PREDICTION
    # --------------------------------------------------------

    def predict_sets(
        self,
        match: Dict[str, Any],
        win_probability: float
    ) -> Dict[str, Any]:
        """
        Szett eredmény predikció
        """

        tournament = match.get("tournament", "")

        is_best_of_5 = (
            "Grand Slam" in tournament
            or "Davis Cup" in tournament
            or "Olympics" in tournament
        )

        p1_win_set = win_probability ** 0.85

        if is_best_of_5:

            straight_3 = p1_win_set ** 3
            four_sets = 3 * (p1_win_set ** 3) * (1 - p1_win_set)
            five_sets = 6 * (p1_win_set ** 3) * ((1 - p1_win_set) ** 2)

            p1_win_match = straight_3 + four_sets + five_sets

            if p1_win_match > 0:
                straight_3_prob = straight_3 / p1_win_match * win_probability
                four_sets_prob = four_sets / p1_win_match * win_probability
                five_sets_prob = five_sets / p1_win_match * win_probability
            else:
                straight_3_prob = four_sets_prob = five_sets_prob = 0

            p2_win_set = 1 - p1_win_set

            p2_straight = (p2_win_set ** 3) * (1 - win_probability)
            p2_four = (3 * (p2_win_set ** 3) * p1_win_set) * (1 - win_probability)
            p2_five = (6 * (p2_win_set ** 3) * (p1_win_set ** 2)) * (1 - win_probability)

            scenarios = [
                {"score": f"3-0 ({match['player1']})", "probability": round(straight_3_prob * 100, 2)},
                {"score": f"3-1 ({match['player1']})", "probability": round(four_sets_prob * 100, 2)},
                {"score": f"3-2 ({match['player1']})", "probability": round(five_sets_prob * 100, 2)},
                {"score": f"0-3 ({match['player2']})", "probability": round(p2_straight * 100, 2)},
                {"score": f"1-3 ({match['player2']})", "probability": round(p2_four * 100, 2)},
                {"score": f"2-3 ({match['player2']})", "probability": round(p2_five * 100, 2)}
            ]

            sets_3 = sum(s["probability"] for s in scenarios if "3-0" in s["score"] or "0-3" in s["score"])
            sets_4 = sum(s["probability"] for s in scenarios if "3-1" in s["score"] or "1-3" in s["score"])
            sets_5 = sum(s["probability"] for s in scenarios if "3-2" in s["score"] or "2-3" in s["score"])

            sets_distribution = {
                "3_szettes": round(sets_3, 2),
                "4_szettes": round(sets_4, 2),
                "5_szettes": round(sets_5, 2)
            }

            if sets_3 >= sets_4 and sets_3 >= sets_5:
                expected_sets = "3"
            elif sets_4 >= sets_5:
                expected_sets = "4"
            else:
                expected_sets = "5"

        else:

            straight_2 = p1_win_set ** 2
            three_sets = 2 * (p1_win_set ** 2) * (1 - p1_win_set)

            p1_win_match = straight_2 + three_sets

            if p1_win_match > 0:
                straight_2_prob = straight_2 / p1_win_match * win_probability
                three_sets_p1_prob = three_sets / p1_win_match * win_probability
            else:
                straight_2_prob = three_sets_p1_prob = 0

            p2_win_set = 1 - p1_win_set

            p2_straight = (p2_win_set ** 2) * (1 - win_probability)
            p2_three = (2 * (p2_win_set ** 2) * p1_win_set) * (1 - win_probability)

            scenarios = [
                {"score": f"2-0 ({match['player1']})", "probability": round(straight_2_prob * 100, 2)},
                {"score": f"2-1 ({match['player1']})", "probability": round(three_sets_p1_prob * 100, 2)},
                {"score": f"0-2 ({match['player2']})", "probability": round(p2_straight * 100, 2)},
                {"score": f"1-2 ({match['player2']})", "probability": round(p2_three * 100, 2)}
            ]

            sets_2 = sum(s["probability"] for s in scenarios if "2-0" in s["score"] or "0-2" in s["score"])
            sets_3 = sum(s["probability"] for s in scenarios if "2-1" in s["score"] or "1-2" in s["score"])

            sets_distribution = {
                "2_szettes": round(sets_2, 2),
                "3_szettes": round(sets_3, 2)
            }

            expected_sets = "2" if sets_2 > sets_3 else "3"

        best_scenario = max(scenarios, key=lambda x: x["probability"])

        return {
            "format": "Best of 5" if is_best_of_5 else "Best of 3",
            "scenarios": scenarios,
            "most_likely": best_scenario,
            "sets_distribution": sets_distribution,
            "expected_sets": expected_sets,
            "three_sets_probability": sets_distribution.get("3_szettes", 0),
            "five_sets_probability": sets_distribution.get("5_szettes", 0) if is_best_of_5 else 0
        }

    # --------------------------------------------------------
    # TOTAL GAMES PREDICTION
    # --------------------------------------------------------

    def predict_total_games(
        self,
        match: Dict[str, Any],
        stats1: Dict[str, float],
        stats2: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Összes játék számának predikciója
        """

        p1_serve = stats1.get("service_games_won")
        if p1_serve is None:
            p1_serve = stats1.get("first_serve_points_won", 70)

        p2_serve = stats2.get("service_games_won")
        if p2_serve is None:
            p2_serve = stats2.get("first_serve_points_won", 70)

        p1_hold = clamp(p1_serve / 100.0, 0.50, 0.95)
        p2_hold = clamp(p2_serve / 100.0, 0.50, 0.95)

        p1_break = 1 - p2_hold
        p2_break = 1 - p1_hold

        expected_games_set = 6 / p1_hold + 6 / p2_hold
        tight_set_prob = p1_break * p2_break * 2
        expected_games_set += tight_set_prob * 3

        tournament = match.get("tournament", "")
        is_best_of_5 = (
            "Grand Slam" in tournament
            or "Davis Cup" in tournament
            or "Olympics" in tournament
        )

        if is_best_of_5:
            avg_sets = 3.8
            expected_total = expected_games_set * avg_sets
            min_games = expected_games_set * 2.5
            max_games = expected_games_set * 5.5
        else:
            avg_sets = 2.3
            expected_total = expected_games_set * avg_sets
            min_games = expected_games_set * 1.8
            max_games = expected_games_set * 3.5

        expected_total = round(expected_total, 1)
        min_games = round(min_games, 1)
        max_games = round(max_games, 1)

        ou_tips = []
        thresholds = [17.5, 18.5, 19.5, 20.5, 21.5, 22.5, 23.5,
                      33.5, 34.5, 35.5, 36.5, 37.5, 38.5, 39.5]

        for threshold in thresholds:
            if is_best_of_5 and threshold < 30:
                continue
            if not is_best_of_5 and threshold > 26:
                continue

            if expected_total > threshold:
                diff = expected_total - threshold
                if diff > 3:
                    confidence = "MAGAS"
                elif diff > 1.5:
                    confidence = "KÖZEPES"
                else:
                    confidence = "ALACSONY"

                ou_tips.append({
                    "line": f"OVER {threshold}",
                    "confidence": confidence,
                    "expected": expected_total,
                    "difference": round(diff, 1)
                })
            else:
                diff = threshold - expected_total
                if diff > 3:
                    confidence = "MAGAS"
                elif diff > 1.5:
                    confidence = "KÖZEPES"
                else:
                    confidence = "ALACSONY"

                ou_tips.append({
                    "line": f"UNDER {threshold}",
                    "confidence": confidence,
                    "expected": expected_total,
                    "difference": round(diff, 1)
                })

        return {
            "expected_total_games": expected_total,
            "range": {"min": min_games, "max": max_games},
            "expected_games_per_set": round(expected_games_set, 1),
            "tight_set_probability": round(tight_set_prob * 100, 1),
            "best_over_under": ou_tips[:5],
            "format": "Best of 5" if is_best_of_5 else "Best of 3"
        }

    # --------------------------------------------------------

    def predict(
        self,
        match: Dict[str, Any]
    ) -> Dict[str, Any]:

        player1 = match["player1"]
        player2 = match["player2"]

        player1_key = match["player1_key"]
        player2_key = match["player2_key"]

        surface = MatchNormalizer.surface_from_tournament(
            match["tournament"]
        )

        logger.info(
            "🔎 %s vs %s | %s | %s",
            player1,
            player2,
            match["tournament"],
            surface
        )

        # ----------------------------------------------------
        # FORMA
        # ----------------------------------------------------

        form1 = self.form.analyze(
            player1_key,
            player1,
            surface
        )

        form2 = self.form.analyze(
            player2_key,
            player2,
            surface
        )

        # ----------------------------------------------------
        # RANKING
        # ----------------------------------------------------

        tour = (
            "WTA"
            if "Women" in match["event_type"]
            else "ATP"
        )

        rank1 = self.rankings.find_player_rank(
            player1_key,
            tour
        )

        rank2 = self.rankings.find_player_rank(
            player2_key,
            tour
        )

        # ----------------------------------------------------
        # H2H
        # ----------------------------------------------------

        h2h_raw = self.api.get_h2h(
            player1_key,
            player2_key
        )

        h2h = H2HAnalyzer.analyze(
            h2h_raw,
            player1_key,
            player2_key,
            surface
        )

        # ----------------------------------------------------
        # CURRENT MATCH STATISTICS
        # ----------------------------------------------------

        current_stats = StatisticsParser.parse(match)

        stats1 = current_stats["player1"]
        stats2 = current_stats["player2"]

        # ----------------------------------------------------
        # FEATURES
        # ----------------------------------------------------

        ranking_score = self._ranking_score(rank1, rank2)
        form_score = self._form_score(form1, form2)
        surface_score = self._surface_score(form1, form2)
        h2h_score = self._h2h_score(h2h)
        stats_score = self._player_stats_score(stats1, stats2)

        # ----------------------------------------------------
        # DATA QUALITY
        # ----------------------------------------------------

        available_features = 0
        total_features = 5

        for value in [ranking_score, form_score, surface_score, h2h_score, stats_score]:
            if value != 0:
                available_features += 1

        data_quality = available_features / total_features

        # -------------------------------------------------
