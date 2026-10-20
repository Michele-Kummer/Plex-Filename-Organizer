"""Download a season's episode guide from TVmaze (https://www.tvmaze.com, free, no API key)."""

import json
import urllib.parse
import urllib.request

API = "https://api.tvmaze.com"


def _get(path: str):
    with urllib.request.urlopen(API + path, timeout=30) as response:
        return json.load(response)


def pick_show(results: list[dict], name: str, year: int | None) -> dict | None:
    """Pick the TVmaze search result for the show, preferring the one that premiered in `year`."""
    shows = [r["show"] for r in results]
    if year:
        for show in shows:
            if (show.get("premiered") or "")[:4] == str(year):
                return show
    exact = [s for s in shows if s["name"].lower() == name.lower()]
    return (exact or shows or [None])[0]


def season_guide(episodes: list[dict], season: int) -> list[dict]:
    """The season's regular episodes as guide entries: episode, title, air_date."""
    return [{"episode": e["number"], "title": e["name"], "air_date": e.get("airdate") or None}
            for e in episodes if e.get("season") == season and e.get("number")]


def fetch_guide(show: str, season: int, year: int | None = None) -> tuple[str, list[dict]]:
    """Return (TVmaze show name and year, guide entries) for one season."""
    found = pick_show(_get("/search/shows?q=" + urllib.parse.quote(show)), show, year)
    if not found:
        raise LookupError(f'TVmaze has no show called "{show}"')
    label = f"{found['name']} ({(found.get('premiered') or '?')[:4]})"
    guide = season_guide(_get(f"/shows/{found['id']}/episodes"), season)
    if not guide:
        raise LookupError(f"TVmaze has no season {season} for {label}")
    return label, guide
