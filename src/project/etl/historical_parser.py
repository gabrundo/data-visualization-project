"""Parse Fantacalcio matchday HTML without network or database access."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

PROVIDER = "Redazione Fantacalcio"
EVENTS = {
    "scoredGoals": "goals", "concededGoals": "goals_conceded",
    "ownGoals": "own_goals", "scoredPenalties": "penalties_scored",
    "missedPenalties": "penalties_missed", "savedPenalties": "penalties_saved",
    "assists": "assists",
}
# The publisher's grades.page.min.css renders 55 as a placeholder 6 (no FV)
# and 56 as a dash. Neither is a numeric match rating.
UNRATED = {"55", "56", "sv", "s.v.", "s.v", "s/v"}
MISSING = {"", "-", "—"}


class ParseError(ValueError):
    """The page cannot safely be associated with the requested matchday."""


@dataclass
class Matchday:
    season: int
    matchday: int
    fixtures: list[dict] = field(default_factory=list)
    performances: list[dict] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def complete(self):
        return not self.issues


def required(node, selector):
    found = node.select_one(selector)
    if found is None:
        raise ParseError(f"Missing HTML element: {selector}")
    return found


def number(token, *, integer=False, rating=False):
    if token is None or token.strip().lower() in MISSING or (not integer and token.strip().lower() in UNRATED):
        return None
    try:
        value = Decimal(token.strip().replace(",", "."))
    except InvalidOperation as exc:
        raise ParseError(f"Invalid number: {token!r}") from exc
    if not value.is_finite() or (integer and (value < 0 or value != int(value))):
        raise ParseError(f"Invalid count: {token!r}")
    if rating and not 0 <= value <= 10:
        raise ParseError(f"Invalid rating: {token!r}")
    if integer and value > 32767:
        raise ParseError(f"Count out of database range: {token!r}")
    return int(value) if integer else value


def parse_matchday(content: bytes, season: int, matchday: int) -> Matchday:
    if not content.strip():
        raise ParseError("Empty matchday HTML")
    soup = BeautifulSoup(content, "html.parser", from_encoding="utf-8")
    selected_season = required(soup, "#season option[selected]").get("value")
    selected_day = required(soup, "#matchweek option[selected]").get("value")
    if selected_season != f"{season}/{(season + 1) % 100:02}" or selected_day != str(matchday):
        raise ParseError(f"Requested {season}/{matchday}, returned {selected_season}/{selected_day}")
    result = Matchday(season, matchday)
    teams = {}
    fixture_keys = set()
    source_ids = set()
    for item in soup.select("li.match"):
        external = item.get("id", "").removeprefix("match-")
        if not external.isdecimal() or external in source_ids:
            raise ParseError("Missing or duplicate fixture source ID")
        source_ids.add(external)
        day = required(item, ".matchweek").get_text(strip=True)
        if day != str(matchday):
            raise ParseError(f"Fixture {external} has unexpected matchday {day}")
        fixture = {"external_id": external, "season": season, "matchday": matchday}
        for side in ("home", "away"):
            label = required(item, f".team-{side}")
            key = label.get("for")
            name = required(label, 'meta[itemprop="name"]').get("content")
            if not key or not name or key in teams:
                raise ParseError("Missing or repeated fixture team")
            teams[key] = (external, name)
            fixture[f"{side}_team"] = name
            fixture[f"{side}_goals"] = number(required(item, f".score-{side}").get_text(strip=True), integer=True)
        pair = (fixture["home_team"], fixture["away_team"])
        if pair[0] == pair[1] or pair in fixture_keys:
            raise ParseError("Invalid or duplicate home/away pairing")
        fixture_keys.add(pair)
        status = required(item, "[data-match-status]")["data-match-status"]
        fixture["status"] = "completed" if status == "4" else "unknown"
        fixture["played_at"] = None
        date = item.select_one('meta[itemprop="startDate"]')
        hours = item.select_one(".match-date .hours")
        if date and hours:
            try:
                fixture["played_at"] = datetime.fromisoformat(
                    f"{date['content']}T{hours.get_text(strip=True)}"
                ).replace(tzinfo=ZoneInfo("Europe/Rome"))
            except (ValueError, KeyError):
                result.issues.append(f"Fixture {external}: invalid source date")
        if fixture["status"] != "completed" or any(fixture[f"{s}_goals"] is None for s in ("home", "away")):
            result.issues.append(f"Fixture {external}: not completed or missing score")
        result.fixtures.append(fixture)
    if len(result.fixtures) != 10:
        result.issues.append(f"Expected 10 fixtures, found {len(result.fixtures)}")

    seen_tables = set()
    seen_players = set()
    for table in soup.select(".grades-table"):
        parent = table.find_parent("li", class_="team-table")
        team_key = parent.get("id") if parent else None
        if team_key not in teams or team_key in seen_tables:
            raise ParseError(f"Unknown or duplicated performance team: {team_key}")
        seen_tables.add(team_key)
        fixture_id, team = teams[team_key]
        table_team = required(table, "thead .team-name").get_text(strip=True)
        if table_team != team:
            raise ParseError(f"Table team {table_team} does not match fixture team {team}")
        providers = [img.get("title") for img in table.select("thead tr:nth-of-type(2) th:first-child .group img")]
        if providers.count(PROVIDER) != 1:
            raise ParseError("Cannot identify Redazione Fantacalcio rating column")
        provider_index = providers.index(PROVIDER)
        bonus_provider = required(table, "thead tr:nth-of-type(2) th:last-child img").get("title")
        if bonus_provider != PROVIDER:
            raise ParseError("Unexpected event provider")
        event_keys = [x["data-key"] for x in table.select("thead [data-key]")]
        if len(event_keys) != len(set(event_keys)) or not set(EVENTS) <= set(event_keys):
            raise ParseError("Missing or duplicated event headers")
        player_count = 0
        rated_count = 0
        for row in table.select("tbody tr"):
            role = required(row, ".role").get("data-value")
            if role == "all":
                continue
            link = required(row, "a.player-link")
            path = urlparse(link.get("href", "")).path
            match = re.fullmatch(r"/serie-a/squadre/[^/]+/[^/]+/([1-9][0-9]*)(?:/(\d{4}-\d{2}))?/?", path)
            if not match or (match[2] and match[2] != f"{season}-{(season+1)%100:02}"):
                raise ParseError(f"Invalid player link: {path}")
            external_id = str(int(match[1]))
            if external_id in seen_players:
                raise ParseError(f"Duplicate player in matchday: {external_id}")
            seen_players.add(external_id)
            grades = row.select(".player-grade")
            fantasy = row.select(".player-fanta-grade")
            if len(grades) != len(providers) or len(fantasy) != len(providers):
                raise ParseError(f"Player {external_id}: unexpected rating columns")
            grade = grades[provider_index]
            grade_token = grade.get("data-value")
            fv_token = fantasy[provider_index].get("data-value")
            if grade_token is None or fv_token is None:
                raise ParseError(f"Player {external_id}: missing rating attributes")
            tokens = [x.get("data-value") for x in row.select(".player-bonus")]
            if len(tokens) != len(event_keys):
                raise ParseError(f"Player {external_id}: unexpected event columns")
            events = dict(zip(event_keys, tokens))
            issues = []

            def parsed(token, field_name, **kwargs):
                try:
                    return number(token, **kwargs)
                except ParseError as exc:
                    issues.append(f"{field_name}: {exc}")
                    return None

            rating = parsed(grade_token, "match_rating", rating=True)
            unrated = grade_token is not None and grade_token.strip().lower() in UNRATED
            fv = None if unrated else parsed(fv_token, "fanta_voto")
            if fv is not None and not -9999 < fv < 10000:
                issues.append("fanta_voto out of database range")
                fv = None
            classes = grade.get("class", [])
            observation = {
                "external_id": external_id, "name": link.get_text(strip=True),
                "fixture_external_id": fixture_id, "team": team,
                "match_rating": rating, "fanta_voto": fv,
                "rating_status": "unrated" if unrated else "rated" if rating is not None else "unknown",
                "appeared": None, "started": None, "minutes": None,
                "yellow_cards": int("yellow-card" in classes),
                "red_cards": int("red-card" in classes),
                "raw_values": {"name": link.get_text(strip=True), "profile_url": link["href"],
                               "role": role, "match_rating": grade_token, "fanta_voto": fv_token,
                               "grade_classes": classes, "events": events,
                               "icons": [x.get("title") for x in row.select(".player-item img")]},
                "validation_issues": issues,
            }
            for source_key, field_name in EVENTS.items():
                observation[field_name] = parsed(events[source_key], field_name, integer=True)
            if not observation["name"]:
                raise ParseError(f"Player {external_id}: missing name")
            if issues:
                result.issues.append(f"Player {external_id}: {'; '.join(issues)}")
            result.performances.append(observation)
            player_count += 1
            rated_count += rating is not None
        if player_count < 11:
            result.issues.append(f"Team {team}: only {player_count} player rows")
        if not rated_count:
            result.issues.append(f"Team {team}: no published numeric ratings")
    for key in teams.keys() - seen_tables:
        result.issues.append(f"Missing rating table for {teams[key][1]}")
    return result
