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

        # Logaritmikus különbség.
        # 1 vs 10 ne legyen 10x erősebb,
        # de legyen jelentős különbség.
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

        ranking_score = self._ranking_score(
            rank1,
            rank2
        )

        form_score = self._form_score(
            form1,
            form2
        )

        surface_score = self._surface_score(
            form1,
            form2
        )

        h2h_score = self._h2h_score(h2h)

        stats_score = self._player_stats_score(
            stats1,
            stats2
        )

        # ----------------------------------------------------
        # DATA QUALITY
        # ----------------------------------------------------

        available_features = 0
        total_features = 5

        for value in [
            ranking_score,
            form_score,
            surface_score,
            h2h_score,
            stats_score
        ]:

            if value != 0:
                available_features += 1

        data_quality = (
            available_features / total_features
        )

        # ----------------------------------------------------
        # WEIGHTS
        # ----------------------------------------------------

        # Ranking
        weighted_score = (
            ranking_score * 0.28
            +
            form_score * 0.27
            +
            surface_score * 0.23
            +
            h2h_score * 0.10
            +
            stats_score * 0.12
        )

        # ----------------------------------------------------
        # PROBABILITY
        # ----------------------------------------------------

        probability = sigmoid(
            weighted_score * 4.2
        )

        probability = clamp(
            probability,
            0.03,
            0.97
        )

        p1_probability = probability
        p2_probability = 1.0 - probability

        if p1_probability >= p2_probability:

            winner = player1
            winner_probability = p1_probability

        else:

            winner = player2
            winner_probability = p2_probability

        # ----------------------------------------------------
        # CONFIDENCE
        # ----------------------------------------------------

        # Nem állítjuk, hogy a confidence a találati esély.
        # Azt mutatja, mennyi használható adat állt rendelkezésre.

        confidence = clamp(
            0.45 + data_quality * 0.50,
            0.45,
            0.95
        )

        if winner_probability >= 0.70:
            level = "ERŐS ELŐNY"

        elif winner_probability >= 0.60:
            level = "ELŐNY"

        elif winner_probability >= 0.55:
            level = "ENYHE ELŐNY"

        else:
            level = "KIEGYENLÍTETT"

        # ----------------------------------------------------
        # FAIR ODDS
        # ----------------------------------------------------

        fair_odds = (
            1.0 / winner_probability
        )

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        return {

            "match": {
                "match_key": match["match_key"],
                "player1": player1,
                "player2": player2,
                "player1_key": player1_key,
                "player2_key": player2_key,
                "tournament": match["tournament"],
                "round": match["round"],
                "surface": surface,
                "date": match["date"],
                "time": match["time"],
                "status": match["status"]
            },

            "prediction": {

                "winner": winner,

                "player1_probability": round(
                    p1_probability * 100,
                    2
                ),

                "player2_probability": round(
                    p2_probability * 100,
                    2
                ),

                "winner_probability": round(
                    winner_probability * 100,
                    2
                ),

                "fair_odds": round(
                    fair_odds,
                    3
                ),

                "level": level,

                "confidence": round(
                    confidence * 100,
                    1
                )
            },

            "features": {

                "ranking": {
                    "player1": rank1,
                    "player2": rank2,
                    "score": round(
                        ranking_score,
                        4
                    )
                },

                "recent_form": {
                    "player1": form1,
                    "player2": form2,
                    "score": round(
                        form_score,
                        4
                    )
                },

                "surface_form": {
                    "surface": surface,
                    "player1": form1.get(
                        "surface_win_pct"
                    ),
                    "player2": form2.get(
                        "surface_win_pct"
                    ),
                    "score": round(
                        surface_score,
                        4
                    )
                },

                "h2h": h2h,

                "statistics": {
                    "player1": stats1,
                    "player2": stats2,
                    "score": round(
                        stats_score,
                        4
                    )
                }
            },

            "data_quality": round(
                data_quality * 100,
                1
            ),

            "generated_at": datetime.now().isoformat()
        }


# ============================================================
# ODDS ANALYSIS
# ============================================================

class OddsAnalyzer:

    @staticmethod
    def find_best_match_winner_odds(
        odds_data: Dict[str, Any]
    ) -> Dict[str, Any]:

        result = {}

        if not isinstance(odds_data, dict):
            return result

        for match_id, markets in odds_data.items():

            if not isinstance(markets, dict):
                continue

            market = markets.get("Home/Away")

            if not isinstance(market, dict):
                continue

            home = market.get("Home", {})
            away = market.get("Away", {})

            if isinstance(home, dict):

                values = []

                for bookmaker, value in home.items():

                    odd = safe_float(value)

                    if odd and odd > 1:
                        values.append(
                            (bookmaker, odd)
                        )

                if values:
                    result["player1"] = max(
                        values,
                        key=lambda x: x[1]
                    )

            if isinstance(away, dict):

                values = []

                for bookmaker, value in away.items():

                    odd = safe_float(value)

                    if odd and odd > 1:
                        values.append(
                            (bookmaker, odd)
                        )

                if values:
                    result["player2"] = max(
                        values,
                        key=lambda x: x[1]
                    )

        return result


# ============================================================
# PRINT
# ============================================================

def print_prediction(result: Dict[str, Any]):

    match = result["match"]
    prediction = result["prediction"]

    print()
    print("=" * 78)
    print("🎾 TENNIS AI ANALYST PRO")
    print("=" * 78)

    print(
        f"\n🏟️ {match['player1']} vs {match['player2']}"
    )

    print(
        f"🏆 {match['tournament']}"
    )

    if match["round"]:
        print(
            f"🔄 Forduló: {match['round']}"
        )

    print(
        f"🎾 Borítás: {match['surface']}"
    )

    print(
        f"📅 {match['date']} {match['time']}"
    )

    print()
    print("🧠 PREDIKCIÓ")
    print("-" * 78)

    print(
        f"🏆 Várható győztes: "
        f"{prediction['winner']}"
    )

    print(
        f"📊 {match['player1']}: "
        f"{prediction['player1_probability']:.2f}%"
    )

    print(
        f"📊 {match['player2']}: "
        f"{prediction['player2_probability']:.2f}%"
    )

    print(
        f"🎯 Modell valószínűség: "
        f"{prediction['winner_probability']:.2f}%"
    )

    print(
        f"💰 Fair odds: "
        f"{prediction['fair_odds']:.3f}"
    )

    print(
        f"📈 Szint: "
        f"{prediction['level']}"
    )

    print(
        f"🔎 Adatminőség: "
        f"{result['data_quality']:.1f}%"
    )

    print(
        f"📌 Modell confidence: "
        f"{prediction['confidence']:.1f}%"
    )

    print()
    print("📋 RÉSZLETES ADATOK")
    print("-" * 78)

    features = result["features"]

    ranking = features["ranking"]

    print(
        f"🌍 Ranking: "
        f"{match['player1']} = "
        f"{ranking['player1'] or 'N/A'} | "
        f"{match['player2']} = "
        f"{ranking['player2'] or 'N/A'}"
    )

    form = features["recent_form"]

    print(
        f"🔥 Forma: "
        f"{form['player1']['wins']}-"
        f"{form['player1']['losses']} | "
        f"{form['player2']['wins']}-"
        f"{form['player2']['losses']}"
    )

    surface = features["surface_form"]

    print(
        f"🎾 {surface['surface']} forma: "
        f"{surface['player1'] if surface['player1'] is not None else 'N/A'}% | "
        f"{surface['player2'] if surface['player2'] is not None else 'N/A'}%"
    )

    h2h = features["h2h"]

    print(
        f"🤝 H2H: "
        f"{h2h['player1_wins']}-"
        f"{h2h['player2_wins']}"
    )

    if h2h["surface_total"]:

        print(
            f"🤝 H2H {surface['surface']}: "
            f"{h2h['surface_player1_wins']}/"
            f"{h2h['surface_total']}"
        )

    print()
    print(
        "⚠️ FONTOS: A százalék modellbecslés, "
        "nem garantált eredmény."
    )

    print("=" * 78)


# ============================================================
# SAVE JSON
# ============================================================

def save_json(
    filename: str,
    data: Any
):

    path = os.path.join(
        RESULTS_DIR,
        filename
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )

    logger.info(
        "💾 Mentve: %s",
        path
    )


# ============================================================
# FIND MATCH
# ============================================================

def find_match(
    matches: List[Dict[str, Any]],
    search: str
) -> Optional[Dict[str, Any]]:

    search_normalized = normalize_name(
        search
    )

    if " vs " in search_normalized:

        p1, p2 = search_normalized.split(
            " vs ",
            1
        )

    elif " - " in search_normalized:

        p1, p2 = search_normalized.split(
            " - ",
            1
        )

    else:

        return None

    for match in matches:

        a = normalize_name(
            match["player1"]
        )

        b = normalize_name(
            match["player2"]
        )

        if (
            (p1 in a and p2 in b)
            or
            (p2 in a and p1 in b)
        ):

            return match

    return None


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="🎾 Tennis AI Analyst PRO"
    )

    parser.add_argument(
        "--today",
        action="store_true",
        help="Mai mérkőzések"
    )

    parser.add_argument(
        "--tomorrow",
        action="store_true",
        help="Holnapi mérkőzések"
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Élő mérkőzések"
    )

    parser.add_argument(
        "--date",
        type=str,
        help="Dátum YYYY-MM-DD"
    )

    parser.add_argument(
        "--match",
        type=str,
        help='Egy mérkőzés: "Player1 vs Player2"'
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum elemzendő meccsek száma"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON eredmény mentése"
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    try:

        api = TennisAPI()

    except RuntimeError as exc:

        print(exc)

        sys.exit(1)

    engine = PredictionEngine(api)

    # --------------------------------------------------------
    # LIVE
    # --------------------------------------------------------

    if args.live:

        logger.info(
            "🔴 Élő mérkőzések lekérése..."
        )

        raw_matches = api.get_livescore()

        matches = [
            MatchNormalizer.normalize(x)
            for x in raw_matches
        ]

        if not matches:

            print(
                "\n❌ Jelenleg nincs elérhető élő mérkőzés."
            )

            sys.exit(0)

        logger.info(
            "✅ %d élő mérkőzés",
            len(matches)
        )

        results = []

        for match in matches[:args.limit]:

            try:

                result = engine.predict(
                    match
                )

                print_prediction(result)

                results.append(result)

            except Exception as exc:

                logger.exception(
                    "❌ Hiba: %s",
                    exc
                )

        if args.json:

            save_json(
                "live_predictions.json",
                results
            )

        return

    # --------------------------------------------------------
    # SINGLE MATCH
    # --------------------------------------------------------

    if args.match:

        # Először mai + holnapi meccsekben keresünk
        today = datetime.now()

        raw_matches = api.get_fixtures(
            today.strftime("%Y-%m-%d"),
            (
                today + timedelta(days=1)
            ).strftime("%Y-%m-%d")
        )

        matches = [
            MatchNormalizer.normalize(x)
            for x in raw_matches
        ]

        match = find_match(
            matches,
            args.match
        )

        if not match:

            print(
                "\n❌ A mérkőzést nem találtam "
                "a mai/holnapi fixture adatok között."
            )

            print(
                "\nPróbáld meg a --date kapcsolót "
                "a mérkőzés dátumával."
            )

            sys.exit(1)

        result = engine.predict(
            match
        )

        print_prediction(result)

        if args.json:

            save_json(
                f"match_{match['match_key']}.json",
                result
            )

        return

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    if args.date:

        target_date = args.date

    elif args.tomorrow:

        target_date = (
            datetime.now() +
            timedelta(days=1)
        ).strftime("%Y-%m-%d")

    else:

        # Alapértelmezés: TODAY
        target_date = (
            datetime.now()
        ).strftime("%Y-%m-%d")

    # --------------------------------------------------------
    # FIXTURES
    # --------------------------------------------------------

    logger.info(
        "📅 Mérkőzések lekérése: %s",
        target_date
    )

    raw_matches = api.get_fixtures(
        target_date,
        target_date
    )

    matches = [
        MatchNormalizer.normalize(x)
        for x in raw_matches
    ]

    if not matches:

        print()
        print(
            f"❌ Nincs mérkőzés vagy az API "
            f"nem adott vissza adatot: {target_date}"
        )

        sys.exit(0)

    logger.info(
        "✅ %d mérkőzés érkezett az API-tól",
        len(matches)
    )

    # --------------------------------------------------------
    # ANALYZE
    # --------------------------------------------------------

    results = []

    for index, match in enumerate(
        matches[:args.limit],
        start=1
    ):

        print(
            f"\n[{index}/{min(len(matches), args.limit)}]"
        )

        try:

            result = engine.predict(
                match
            )

            print_prediction(result)

            results.append(result)

        except KeyboardInterrupt:

            print(
                "\n⛔ Megszakítva."
            )

            break

        except Exception as exc:

            logger.exception(
                "❌ Mérkőzés elemzési hiba: %s",
                exc
            )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    if args.json or results:

        filename = (
            f"predictions_{target_date.replace('-', '')}.json"
        )

        save_json(
            filename,
            results
        )

    print()
    print("=" * 78)
    print(
        f"✅ Kész. Elemzett mérkőzések: "
        f"{len(results)}"
    )
    print("=" * 78)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
