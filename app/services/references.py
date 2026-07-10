"""Reference search via OpenAlex API, citation formatting engine, and BibTeX support."""
import re
import httpx

OPENALEX_URL = "https://api.openalex.org/works"

# ── style metadata ──────────────────────────────────────────────
STYLE_META = {
    "apa":       {"name": "APA 7th",         "type": "author-year"},
    "mla":       {"name": "MLA 9th",         "type": "author-year"},
    "chicago":   {"name": "Chicago",         "type": "author-year"},
    "chicago-nb":{"name": "Chicago (Notes)",  "type": "notes"},
    "gbt":       {"name": "GB/T 7714",       "type": "numeric"},
    "vancouver": {"name": "Vancouver",       "type": "numeric"},
    "harvard":   {"name": "Harvard",         "type": "author-year"},
    "ieee":      {"name": "IEEE",            "type": "numeric"},
    "nature":    {"name": "Nature",          "type": "numeric"},
    "science":   {"name": "Science",         "type": "numeric"},
}

AUTHOR_YEAR_STYLES = {k for k, v in STYLE_META.items() if v["type"] == "author-year"}
NUMERIC_STYLES = {k for k, v in STYLE_META.items() if v["type"] == "numeric"}


# ── OpenAlex search ─────────────────────────────────────────────

async def search_references(query: str, limit: int = 10) -> tuple[list[dict], str]:
    params = {
        "search": query,
        "per_page": min(limit, 25),
        "sort": "cited_by_count:desc",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(OPENALEX_URL, params=params)
            if resp.status_code != 200:
                return [], f"API error ({resp.status_code})"

            data = resp.json()
            results = []
            for paper in data.get("results", []):
                authorship = paper.get("authorships", [])
                author_names = [
                    a.get("author", {}).get("display_name", "")
                    for a in authorship[:5]
                ]
                results.append({
                    "title": paper.get("title", ""),
                    "authors": author_names,
                    "year": paper.get("publication_year", ""),
                    "journal": (paper.get("primary_location", {}).get("source", {}).get("display_name", "")
                                if paper.get("primary_location") else ""),
                    "doi": paper.get("doi", "").replace("https://doi.org/", "") if paper.get("doi") else "",
                    "url": paper.get("doi", "") or paper.get("id", ""),
                    "abstract": "",
                })
            return results, ""
    except Exception as e:
        return [], f"Network error: {str(e)[:100]}"


# ── helper: author name parsing ─────────────────────────────────

def _last_name(name: str) -> str:
    """Extract surname from various name formats."""
    name = name.strip()
    parts = name.split()
    if len(parts) >= 2:
        return parts[-1]
    return name

def _initials(name: str) -> str:
    """Extract initials from name. 'John Smith' → 'J. S.'"""
    name = name.strip()
    parts = name.split()
    initials = []
    for p in parts[:-1] if len(parts) > 1 else parts:
        if p:
            initials.append(p[0].upper() + ".")
    return " ".join(initials)

def _apa_authors(authors: list) -> str:
    """APA format: Smith, J., & Jones, K."""
    if not authors:
        return ""
    if len(authors) == 1:
        return f"{_last_name(authors[0])}, {_initials(authors[0])}"
    if len(authors) == 2:
        return f"{_last_name(authors[0])}, {_initials(authors[0])}, & {_last_name(authors[1])}, {_initials(authors[1])}"
    # 3-20: list all with commas, last with &
    names = [f"{_last_name(a)}, {_initials(a)}" for a in authors]
    return ", ".join(names[:-1]) + f", & {names[-1]}"

def _mla_authors(authors: list) -> str:
    """MLA format: Smith, John, and Kate Jones."""
    if not authors:
        return ""
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]}, and {authors[1]}"
    return f"{authors[0]}, et al."

def _chicago_authors(authors: list) -> str:
    """Chicago author-date: Smith, John, and Kate Jones."""
    if not authors:
        return ""
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} and {authors[1]}"
    if len(authors) <= 10:
        return ", ".join(authors[:-1]) + f", and {authors[-1]}"
    return ", ".join(authors[:7]) + ", et al."

def _gbt_authors(authors: list) -> str:
    """GB/T 7714: all authors separated by commas."""
    if not authors:
        return ""
    return ", ".join(authors)

def _vancouver_authors(authors: list) -> str:
    """Vancouver: Author A, Author B."""
    if not authors:
        return ""
    # Use initials + last name
    names = [f"{_last_name(a)} {_initials(a)}" for a in authors[:6]]
    result = ", ".join(names)
    if len(authors) > 6:
        result += ", et al."
    return result

def _harvard_authors(authors: list) -> str:
    """Harvard: Smith, J. and Jones, K."""
    if not authors:
        return ""
    if len(authors) == 1:
        return f"{_last_name(authors[0])}, {_initials(authors[0])}"
    names = [f"{_last_name(a)}, {_initials(a)}" for a in authors]
    return ", ".join(names[:-1]) + f" and {names[-1]}"

def _ieee_authors(authors: list) -> str:
    """IEEE: A. Smith and B. Jones."""
    if not authors:
        return ""
    if len(authors) == 1:
        return f"{_initials(authors[0])} {_last_name(authors[0])}"
    names = [f"{_initials(a)} {_last_name(a)}" for a in authors]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


# ── inline citation (author-year styles) ────────────────────────

def _apa_cite(authors: list, year) -> str:
    if not authors:
        return f"({year})" if year else "(n.d.)"
    if len(authors) == 1:
        return f"({_last_name(authors[0])}, {year or 'n.d.'})"
    if len(authors) == 2:
        return f"({_last_name(authors[0])} & {_last_name(authors[1])}, {year or 'n.d.'})"
    return f"({_last_name(authors[0])} et al., {year or 'n.d.'})"

def _mla_cite(authors: list, year) -> str:
    if not authors:
        return f"({year or 'n.d.'})"
    if len(authors) == 1:
        return f"({_last_name(authors[0])})"
    if len(authors) == 2:
        return f"({_last_name(authors[0])} and {_last_name(authors[1])})"
    return f"({_last_name(authors[0])} et al.)"

def _chicago_ay_cite(authors: list, year) -> str:
    if not authors:
        return f"({year or 'n.d.'})"
    if len(authors) == 1:
        return f"({_last_name(authors[0])} {year or 'n.d.'})"
    if len(authors) == 2 or len(authors) == 3:
        names = ", ".join(_last_name(a) for a in authors[:-1])
        return f"({names} and {_last_name(authors[-1])} {year or 'n.d.'})"
    return f"({_last_name(authors[0])} et al. {year or 'n.d.'})"

def _harvard_cite(authors: list, year) -> str:
    if not authors:
        return f"({year or 'n.d.'})"
    if len(authors) == 1:
        return f"({_last_name(authors[0])}, {year or 'n.d.'})"
    if len(authors) == 2:
        return f"({_last_name(authors[0])} and {_last_name(authors[1])}, {year or 'n.d.'})"
    return f"({_last_name(authors[0])} et al., {year or 'n.d.'})"


# ── bibliography entry ──────────────────────────────────────────

def _format_apa(ref: dict) -> str:
    """APA 7th: Author. (Year). Title. Journal, Vol(Issue), pp. https://doi.org/xxx"""
    parts = []
    authors = _apa_authors(ref.get("authors", []))
    year = ref.get("year", "")
    title = ref.get("title", "")
    journal = ref.get("journal", "")
    volume = ref.get("volume", "")
    issue = ref.get("issue", "")
    pages = ref.get("pages", "")
    doi = ref.get("doi", "")

    if authors:
        parts.append(authors)
    if year:
        parts.append(f"({year})")
    if title:
        parts.append(f"{title}.")
    source = journal
    if volume:
        source += f", {volume}"
        if issue:
            source += f"({issue})"
    if source:
        if pages:
            source += f", {pages}"
        parts.append(f"{source}.")
    elif pages:
        parts.append(f"{pages}.")
    if doi:
        parts.append(f"https://doi.org/{doi}")
    return " ".join(parts)

def _format_mla(ref: dict) -> str:
    """MLA 9th: Author. "Title." Journal, vol. X, no. Y, Year, pp. xx-xx."""
    parts = []
    authors = _mla_authors(ref.get("authors", []))
    title = ref.get("title", "")
    journal = ref.get("journal", "")
    volume = ref.get("volume", "")
    issue = ref.get("issue", "")
    year = ref.get("year", "")
    pages = ref.get("pages", "")

    if authors:
        parts.append(f'{authors}. "{title}."' if authors else f'"{title}."')
    else:
        parts.append(f'"{title}."')
    if journal:
        journal_part = f"{journal}"
        if volume:
            journal_part += f", vol. {volume}"
        if issue:
            journal_part += f", no. {issue}"
        parts.append(journal_part)
    if year:
        parts[-1] = f"{parts[-1]}, {year}"
    if pages:
        parts.append(f"pp. {pages}.")
    return " ".join(parts) + ("" if parts[-1].endswith(".") else ".")

def _format_chicago_ay(ref: dict) -> str:
    """Chicago author-date: Author. Year. "Title." Journal Vol (Issue): pages."""
    parts = []
    authors = _chicago_authors(ref.get("authors", []))
    year = ref.get("year", "")
    title = ref.get("title", "")
    journal = ref.get("journal", "")
    volume = ref.get("volume", "")
    issue = ref.get("issue", "")
    pages = ref.get("pages", "")

    if authors:
        parts.append(f"{authors}. {year}." if year else f"{authors}.")
    else:
        parts.append(f"{year}." if year else "")
    if title:
        parts.append(f'"{title}."')
    source = journal
    if volume:
        source += f" {volume}"
        if issue:
            source += f", no. {issue}"
    if source:
        parts.append(source)
    if pages:
        parts[-1] = f"{parts[-1]}: {pages}."
    else:
        parts[-1] = f"{parts[-1]}."
    return " ".join(parts)

def _format_chicago_nb(ref: dict) -> str:
    """Chicago notes-bib: Author, "Title," Journal Vol, no. Issue (Year): pages."""
    return _format_chicago_ay(ref)  # simplified, identical in bib section

def _format_gbt(ref: dict) -> str:
    """GB/T 7714: Authors. Title[J]. Journal, Year, Vol(Issue): pages."""
    parts = []
    authors = _gbt_authors(ref.get("authors", []))
    title = ref.get("title", "")
    journal = ref.get("journal", "")
    year = ref.get("year", "")
    volume = ref.get("volume", "")
    issue = ref.get("issue", "")
    pages = ref.get("pages", "")
    doi = ref.get("doi", "")

    pub_type = ref.get("pub_type", "article")
    type_map = {"article": "J", "book": "M", "inproceedings": "C", "phdthesis": "D",
                 "techreport": "R", "preprint": "A"}
    type_tag = type_map.get(pub_type, "J")

    if authors:
        parts.append(f"{authors}.")
    if title:
        parts.append(f"{title}[{type_tag}].")
    if journal:
        parts.append(f"{journal}.")
    date_vol = []
    if year:
        date_vol.append(str(year))
    if volume:
        vol_str = f"{volume}"
        if issue:
            vol_str += f"({issue})"
        date_vol.append(vol_str)
    if date_vol:
        parts.append(f"{', '.join(date_vol)}")
    if pages:
        parts[-1] = f"{parts[-1]}: {pages}."
    else:
        parts[-1] = f"{parts[-1]}."
    if doi:
        parts.append(f"DOI: {doi}.")
    return " ".join(parts)

def _format_vancouver(ref: dict) -> str:
    """Vancouver: Authors. Title. Journal. Year;Vol(Issue):pages."""
    parts = []
    authors = _vancouver_authors(ref.get("authors", []))
    title = ref.get("title", "")
    journal = ref.get("journal", "")
    year = ref.get("year", "")
    volume = ref.get("volume", "")
    issue = ref.get("issue", "")
    pages = ref.get("pages", "")

    if authors:
        parts.append(f"{authors}.")
    if title:
        parts.append(f"{title}.")
    if journal:
        parts.append(f"{journal}.")
    date = str(year) if year else ""
    if volume:
        date += f";{volume}"
        if issue:
            date += f"({issue})"
    if date:
        parts.append(f"{date}")
    if pages:
        parts[-1] = f"{parts[-1]}:{pages}."
    else:
        parts[-1] = f"{parts[-1]}."
    return " ".join(parts)

def _format_harvard(ref: dict) -> str:
    """Harvard: Author. (Year) 'Title', Journal, Vol(Issue), pp. pages."""
    parts = []
    authors = _harvard_authors(ref.get("authors", []))
    year = ref.get("year", "")
    title = ref.get("title", "")
    journal = ref.get("journal", "")
    volume = ref.get("volume", "")
    issue = ref.get("issue", "")
    pages = ref.get("pages", "")

    if authors:
        parts.append(f"{authors}")
    if year:
        parts.append(f"({year})")
    if title:
        parts.append(f"'{title}'")
    source = journal
    if volume:
        source += f", {volume}"
        if issue:
            source += f"({issue})"
    if source:
        parts[-1] = f"{parts[-1]}, {source}"
    if pages:
        parts.append(f"pp. {pages}.")
    else:
        parts.append(".")
    return " ".join(parts)

def _format_ieee(ref: dict) -> str:
    """IEEE: A. Author, "Title," Journal, vol. X, no. Y, pp. zz-zz, Year."""
    parts = []
    authors = _ieee_authors(ref.get("authors", []))
    title = ref.get("title", "")
    journal = ref.get("journal", "")
    volume = ref.get("volume", "")
    issue = ref.get("issue", "")
    pages = ref.get("pages", "")
    year = ref.get("year", "")

    if authors:
        parts.append(f"{authors},")
    if title:
        parts.append(f'"{title},"')
    source = journal
    if volume:
        source += f", vol. {volume}"
    if issue:
        source += f", no. {issue}"
    if source:
        parts.append(f"{source},")
    if pages:
        parts.append(f"pp. {pages},")
    if year:
        parts.append(f"{year}.")
    return " ".join(parts)

def _format_nature(ref: dict) -> str:
    """Nature: Author, A. & Author, B. Title. Journal Volume, pages (Year)."""
    parts = []
    authors = _apa_authors(ref.get("authors", []))  # uses APA initials format
    title = ref.get("title", "")
    journal = ref.get("journal", "")
    volume = ref.get("volume", "")
    pages = ref.get("pages", "")
    year = ref.get("year", "")

    if authors:
        parts.append(f"{authors}")
    if title:
        parts.append(f"{title}.")
    source = journal
    if volume:
        source += f" {volume}"
    if source:
        if pages:
            source += f", {pages}"
        parts.append(f"{source}")
    if year:
        parts.append(f"({year}).")
    return " ".join(parts)

def _format_science(ref: dict) -> str:
    """Science: Author, A., Author, B. (Year). Title. Journal Volume, pages."""
    return _format_nature(ref)  # same format


# ── dispatchers ─────────────────────────────────────────────────

_FORMATTERS = {
    "apa":       _format_apa,
    "mla":       _format_mla,
    "chicago":   _format_chicago_ay,
    "chicago-nb":_format_chicago_nb,
    "gbt":       _format_gbt,
    "vancouver": _format_vancouver,
    "harvard":   _format_harvard,
    "ieee":      _format_ieee,
    "nature":    _format_nature,
    "science":   _format_science,
}

_INLINE_CITERS = {
    "apa":       _apa_cite,
    "mla":       _mla_cite,
    "chicago":   _chicago_ay_cite,
    "chicago-nb":None,
    "gbt":       None,  # numeric
    "vancouver": None,  # numeric
    "harvard":   _harvard_cite,
    "ieee":      None,  # numeric
    "nature":    None,  # numeric
    "science":   None,  # numeric
}


def format_reference(ref: dict, style: str = "apa") -> str:
    """Format a single reference as a bibliography entry."""
    fmt = _FORMATTERS.get(style, _format_apa)
    return fmt(ref)

def format_citation(ref: dict, style: str = "apa") -> str:
    """Format a single reference as an inline citation."""
    citer = _INLINE_CITERS.get(style)
    if citer:
        return citer(ref.get("authors", []), ref.get("year"))
    return ""

def format_reference_list(refs: list[dict], style: str = "apa") -> str:
    """Format a list of references as a numbered reference section."""
    is_numeric = style in NUMERIC_STYLES
    lines = []
    for i, ref in enumerate(refs, 1):
        entry = format_reference(ref, style)
        if is_numeric:
            lines.append(f"[{i}] {entry}")
        else:
            lines.append(entry)
    return "\n\n".join(lines)


# ── BibTeX ──────────────────────────────────────────────────────

def generate_bibtex(ref: dict) -> str:
    """Generate a BibTeX entry from a reference dict."""
    key = ref.get("citation_key", "")
    if not key:
        authors = ref.get("authors", [])
        if authors:
            key = _last_name(authors[0]).lower().replace(" ", "")
        else:
            key = "ref"
        year = ref.get("year", "")
        if year:
            key += str(year)

    pub_type = ref.get("pub_type", "article")
    bt_map = {"article": "article", "book": "book", "inproceedings": "inproceedings",
              "phdthesis": "phdthesis", "techreport": "techreport", "preprint": "article"}
    bt = bt_map.get(pub_type, "article")

    lines = [f"@{bt}{{{key},"]
    if ref.get("title"):
        lines.append(f"  title = {{{ref['title']}}},")
    if ref.get("authors"):
        authors_str = " and ".join(ref["authors"])
        lines.append(f"  author = {{{authors_str}}},")
    if ref.get("year"):
        lines.append(f"  year = {{{ref['year']}}},")
    if ref.get("journal"):
        lines.append(f"  journal = {{{ref['journal']}}},")
    if ref.get("volume"):
        lines.append(f"  volume = {{{ref['volume']}}},")
    if ref.get("issue"):
        lines.append(f"  number = {{{ref['issue']}}},")
    if ref.get("pages"):
        lines.append(f"  pages = {{{ref['pages']}}},")
    if ref.get("publisher"):
        lines.append(f"  publisher = {{{ref['publisher']}}},")
    if ref.get("doi"):
        lines.append(f"  doi = {{{ref['doi']}}},")
    if ref.get("url"):
        lines.append(f"  url = {{{ref['url']}}},")
    if ref.get("abstract"):
        lines.append(f"  abstract = {{{ref['abstract']}}},")

    # remove trailing comma from last line
    lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    return "\n".join(lines)


# ── citation key resolution ─────────────────────────────────────

CITE_PATTERN = re.compile(r'\[@([^\]]+)\]')

def resolve_citations(html: str, refs: list[dict], style: str = "apa") -> str:
    """Replace [@key] markers in HTML with formatted inline citations.
    Builds a key→ref lookup from the refs list.
    For numeric styles, assigns numbers based on first-appearance order."""
    key_map = {}
    for r in refs:
        k = r.get("citation_key", "")
        if k:
            key_map[k] = r

    is_numeric = style in NUMERIC_STYLES
    appearance_order = []
    seen = set()

    def replace_cite(match):
        key = match.group(1)
        ref = key_map.get(key)
        if not ref:
            return match.group(0)  # keep original if not found

        if is_numeric:
            if key not in seen:
                seen.add(key)
                appearance_order.append(key)
            num = appearance_order.index(key) + 1
            return f"[{num}]"
        else:
            return format_citation(ref, style)

    return CITE_PATTERN.sub(replace_cite, html)


def build_bibliography_map(refs: list[dict], style: str = "apa", citation_order: list[str] | None = None) -> dict[str, str]:
    """Build a map of citation_key → formatted bibliography entry.
    If citation_order is provided (numeric styles), entries are sorted by that order."""
    is_numeric = style in NUMERIC_STYLES
    key_map = {r.get("citation_key", ""): r for r in refs}

    if is_numeric and citation_order:
        ordered_keys = [k for k in citation_order if k in key_map]
        # add remaining keys not yet cited
        for k in key_map:
            if k not in ordered_keys:
                ordered_keys.append(k)
    else:
        # author-year: sort by author name, then year
        def sort_key(k):
            r = key_map.get(k, {})
            authors = r.get("authors", [])
            first_author = _last_name(authors[0]) if authors else ""
            return (first_author, r.get("year", 0))
        ordered_keys = sorted(key_map.keys(), key=sort_key)

    result = {}
    for i, k in enumerate(ordered_keys, 1):
        entry = format_reference(key_map[k], style)
        if is_numeric:
            result[k] = f"[{i}] {entry}"
        else:
            result[k] = entry
    return result
