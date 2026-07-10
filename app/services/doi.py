"""DOI metadata fetching via Crossref API and simple BibTeX parser."""
import re
import httpx

CROSSREF_URL = "https://api.crossref.org/works/{doi}"


async def fetch_doi_metadata(doi: str) -> tuple[dict | None, str]:
    """Fetch full metadata for a DOI from Crossref. Returns (ref_data, error)."""
    clean_doi = doi.strip().replace("https://doi.org/", "")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                CROSSREF_URL.format(doi=clean_doi),
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                return None, f"DOI not found (HTTP {resp.status_code})"

            data = resp.json()
            msg = data.get("message", {})

            # authors
            authors = []
            for a in msg.get("author", [])[:10]:
                given = a.get("given", "")
                family = a.get("family", "")
                if given or family:
                    authors.append(f"{family} {given}".strip() if family else given)

            # journal / container
            container = msg.get("container-title", [])
            journal = container[0] if container else ""

            # publication type
            pub_type = "article"
            pub_type_map = {
                "journal-article": "article",
                "book": "book",
                "book-chapter": "inproceedings",
                "proceedings-article": "inproceedings",
                "dissertation": "phdthesis",
                "report": "techreport",
                "posted-content": "preprint",
            }
            msg_type = msg.get("type", "journal-article")
            pub_type = pub_type_map.get(msg_type, "article")

            # pages
            page = msg.get("page", "")
            article_number = msg.get("article-number", "")

            ref_data = {
                "title": (msg.get("title", [""]) or [""])[0],
                "authors": authors,
                "year": msg.get("published-print", {}).get("date-parts", [[None]])[0][0]
                         or msg.get("created", {}).get("date-parts", [[None]])[0][0],
                "journal": journal,
                "doi": clean_doi,
                "url": f"https://doi.org/{clean_doi}",
                "abstract": msg.get("abstract", ""),
                "pub_type": pub_type,
                "volume": msg.get("volume", ""),
                "issue": msg.get("issue", ""),
                "pages": page or article_number or "",
                "publisher": msg.get("publisher", ""),
            }
            return ref_data, ""

    except Exception as e:
        return None, f"Network error: {str(e)[:100]}"


# ── simple BibTeX parser ────────────────────────────────────────

BIENTRY_RE = re.compile(
    r'@(\w+)\s*\{\s*([^,}]+)\s*,\s*(.*?)\}\s*$',
    re.DOTALL | re.MULTILINE,
)
FIELD_RE = re.compile(r'(\w+)\s*=\s*[\{"]([^"}]+)["\}]\s*,?')


def parse_bibtex(text: str) -> tuple[list[dict], str]:
    """Parse BibTeX text into a list of reference dicts. Returns (refs, error)."""
    results = []
    text = text.strip()

    # find all entries
    entries = []
    depth = 0
    start = 0
    in_entry = False
    for i, ch in enumerate(text):
        if ch == "@" and depth == 0:
            if in_entry:
                entries.append(text[start:i].strip())
            start = i
            in_entry = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and in_entry:
                entries.append(text[start:i + 1].strip())
                in_entry = False

    if in_entry:
        entries.append(text[start:].strip())

    type_map = {
        "article": "article", "book": "book", "inproceedings": "inproceedings",
        "conference": "inproceedings", "phdthesis": "phdthesis",
        "mastersthesis": "phdthesis", "techreport": "techreport",
        "misc": "article", "unpublished": "preprint",
    }

    for entry_text in entries:
        match = BIENTRY_RE.match(entry_text)
        if not match:
            continue

        bt_type = match.group(1).lower()
        key = match.group(2).strip()
        fields_str = match.group(3)

        fields = {}
        for fm in FIELD_RE.finditer(fields_str):
            fname = fm.group(1).lower().strip()
            fval = fm.group(2).strip()
            fields[fname] = fval

        authors = []
        if "author" in fields:
            authors = [a.strip() for a in fields["author"].split(" and ")]

        ref = {
            "title": fields.get("title", ""),
            "authors": authors,
            "year": _extract_year(fields.get("year", "")),
            "journal": fields.get("journal", "") or fields.get("booktitle", ""),
            "doi": fields.get("doi", ""),
            "url": fields.get("url", ""),
            "abstract": fields.get("abstract", ""),
            "pub_type": type_map.get(bt_type, "article"),
            "volume": fields.get("volume", ""),
            "issue": fields.get("number", ""),
            "pages": fields.get("pages", ""),
            "publisher": fields.get("publisher", ""),
            "citation_key": key,
            "raw_bibtex": entry_text,
        }
        results.append(ref)

    return results, ""


def _extract_year(year_str: str) -> int | None:
    """Extract a 4-digit year from a string."""
    match = re.search(r'(\d{4})', str(year_str))
    if match:
        return int(match.group(1))
    return None
