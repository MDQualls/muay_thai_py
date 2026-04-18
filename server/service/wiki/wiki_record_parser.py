import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

import server.constants
import server.exceptions

RECENT_RESULTS_LIMIT = 3
REST_API_BASE = "https://en.wikipedia.org/w/rest.php/v1/page"


class WikiRecordParser:
    """Parses a fighter's Wikipedia page HTML to extract infobox stats and fight record.

    Uses the Wikipedia REST v1 HTML endpoint (Parsoid HTML) rather than the plain-text
    extract, which doesn't capture structured tables.
    """

    def __init__(self, wiki_data: dict[str, Any]) -> None:
        """Args:
            wiki_data: Dict with "title" and "page_id" keys from WikiSearcher.
        """
        self.logger = logging.getLogger(__name__)
        self.title_slug = wiki_data["title"].replace(" ", "_")

    async def parse(self) -> dict[str, Any]:
        """Fetch the page HTML and parse infobox + fight record table.

        Returns:
            Dict with keys: wiki_nickname, wiki_wins, wiki_losses, wiki_draws,
            recent_results (list of up to 3 fight dicts).
        """
        html = await self._fetch_html()
        soup = BeautifulSoup(html, "lxml")

        infobox_data = self._parse_infobox(soup)
        recent_results = self._parse_fight_table(soup)

        self.logger.info(
            "WikiRecordParser: nickname=%s wins=%s losses=%s draws=%s results=%d",
            infobox_data.get("wiki_nickname"),
            infobox_data.get("wiki_wins"),
            infobox_data.get("wiki_losses"),
            infobox_data.get("wiki_draws"),
            len(recent_results),
        )

        return {**infobox_data, "recent_results": recent_results}

    async def _fetch_html(self) -> str:
        """Fetch the Parsoid HTML for the page from the Wikipedia REST API."""
        url = f"{REST_API_BASE}/{self.title_slug}/html"
        params = {"redirect": "no"}

        try:
            async with httpx.AsyncClient(headers=server.constants.WIKIPEDIA_HEADERS) as client:
                response = await client.get(url, params=params)
        except httpx.RequestError as e:
            msg = f"Network error fetching Wikipedia HTML for {self.title_slug}: {e}"
            self.logger.warning(msg)
            raise server.exceptions.FetchError(msg) from e

        if response.status_code != 200:
            msg = f"Wikipedia REST API returned {response.status_code} for {self.title_slug}"
            self.logger.warning(msg)
            raise server.exceptions.FetchError(msg)

        return response.text

    def _parse_infobox(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract nickname, wins, losses, and draws from the infobox table.

        Returns a dict with wiki_nickname, wiki_wins, wiki_losses, wiki_draws.
        Missing fields are returned as None — never raises.
        """
        result: dict[str, Any] = {
            "wiki_nickname": None,
            "wiki_wins": None,
            "wiki_losses": None,
            "wiki_draws": None,
        }

        infobox = soup.find("table", class_=re.compile(r"\binfobox\b"))
        if not infobox:
            self.logger.warning("WikiRecordParser: no infobox found for %s", self.title_slug)
            return result

        for row in infobox.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if not th or not td:
                continue

            label = th.get_text(strip=True).lower()
            value = td.get_text(strip=True)

            if "nickname" in label:
                # Multiple nicknames may be separated by <br> — take only the first
                first = td.get_text(separator="\n", strip=True).split("\n")[0].strip()
                result["wiki_nickname"] = first or None
            elif re.search(r"\bwin", label):
                result["wiki_wins"] = self._parse_int(value, "wins")
            elif re.search(r"\blos", label):
                result["wiki_losses"] = self._parse_int(value, "losses")
            elif re.search(r"\bdraw", label):
                result["wiki_draws"] = self._parse_int(value, "draws")

        return result

    def _parse_fight_table(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract the 3 most recent fight results from the fight record wikitable.

        Scans all rows of each wikitable (not just the first) to find the column header
        row, since many fight tables have a title row before the real headers.

        Returns a list of dicts with keys: date, result, opponent, method, round.
        Returns [] if the table cannot be found — never raises.
        """
        for table in soup.find_all("table", class_=re.compile(r"\bwikitable\b")):
            all_rows = table.find_all("tr")

            # Scan every row until we find one whose <th> cells contain "Res." + "Opponent"
            col: dict[str, int] | None = None
            header_idx = -1
            header_cell_count = 0
            for i, row in enumerate(all_rows):
                ths = row.find_all("th")
                if not ths:
                    continue
                headers = [th.get_text(strip=True).lower() for th in ths]
                col = self._find_column_indices(headers)
                if col is not None:
                    header_idx = i
                    header_cell_count = len(ths)
                    break

            if col is None:
                continue

            # Parse data rows that follow the header row
            results = []
            for row in all_rows[header_idx + 1:]:
                cells = row.find_all(["td", "th"])

                if not cells:
                    continue

                # Skip colspan separator rows (e.g. year headings: <th colspan="8">2024</th>)
                if len(cells) == 1:
                    continue

                # Skip sub-header rows (every cell is a <th>)
                if all(c.name == "th" for c in cells):
                    continue

                # Adjust column indices when rowspan causes missing cells.
                # The "Record" column (typically index 1) is the most common rowspan source.
                # Cells to the right of any missing column shift left by the deficit.
                missing = max(0, header_cell_count - len(cells))

                def _cell(field: str, cells: list = cells, missing: int = missing) -> str:
                    if field not in col:
                        return ""
                    idx = col[field]
                    # Index 0 (result) is never affected by rowspan
                    adjusted = idx - missing if idx > 0 else idx
                    if adjusted < 0 or adjusted >= len(cells):
                        return ""
                    return cells[adjusted].get_text(strip=True)

                result_text = _cell("result")
                if not result_text or result_text.lower() in ("res.", "result"):
                    continue

                results.append({
                    "date": _cell("date"),
                    "result": result_text,
                    "opponent": _cell("opponent"),
                    "method": _cell("method"),
                    "round": _cell("round"),
                })

                if len(results) >= RECENT_RESULTS_LIMIT:
                    break

            if results:
                return results

        self.logger.warning(
            "WikiRecordParser: no fight record table found for %s", self.title_slug
        )
        return []

    def _find_column_indices(self, headers: list[str]) -> dict[str, int] | None:
        """Map field names to column indices from a header row.

        Returns None if the required result + opponent columns are not present.
        """
        col: dict[str, int] = {}

        for i, h in enumerate(headers):
            if re.search(r"\bres\b|\bresult\b", h):
                col["result"] = i
            elif "opponent" in h:
                col["opponent"] = i
            elif re.search(r"\btype\b|\bmethod\b", h):
                col["method"] = i
            elif re.search(r"\brnd\b|\bround\b", h):
                col["round"] = i
            elif "date" in h:
                col["date"] = i

        # Must have at minimum result + opponent to be a valid fight table
        if "result" not in col or "opponent" not in col:
            return None

        return col

    def _parse_int(self, value: str, field: str) -> int | None:
        """Parse a string value to int, handling commas and whitespace.

        Returns None and logs a warning if the value is not numeric.
        """
        cleaned = value.replace(",", "").strip()
        # Take only the first token — some cells have "209 (by KO: 45)" style text
        token = cleaned.split()[0] if cleaned else ""
        try:
            return int(token)
        except ValueError:
            self.logger.warning(
                "WikiRecordParser: could not parse %s value %r as int", field, value
            )
            return None
