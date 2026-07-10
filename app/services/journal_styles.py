"""Journal-specific formatting rules for export."""
from dataclasses import dataclass, field


@dataclass
class JournalStyle:
    key: str
    name: str
    citation_style: str      # maps to reference formatting engine style
    columns: int = 1
    heading_numbering: bool = True
    abstract_required: bool = False
    word_limit: int | None = None
    reference_section_title: str = "References"
    title_font_size: int = 14
    body_font_size: int = 12
    heading_font_size: int = 14
    margin_inches: float = 1.0
    line_spacing: float = 1.5


JOURNAL_STYLES: dict[str, JournalStyle] = {
    "nature": JournalStyle(
        key="nature", name="Nature",
        citation_style="nature", columns=2,
        heading_numbering=False, abstract_required=True,
        word_limit=3000, reference_section_title="References",
        title_font_size=14, body_font_size=10, heading_font_size=12,
        margin_inches=0.8, line_spacing=1.5,
    ),
    "science": JournalStyle(
        key="science", name="Science",
        citation_style="science", columns=2,
        heading_numbering=False, abstract_required=True,
        word_limit=3000, reference_section_title="References and Notes",
        title_font_size=14, body_font_size=10, heading_font_size=12,
        margin_inches=0.8, line_spacing=1.5,
    ),
    "ieee": JournalStyle(
        key="ieee", name="IEEE",
        citation_style="ieee", columns=2,
        heading_numbering=True, abstract_required=True,
        word_limit=None, reference_section_title="References",
        title_font_size=24, body_font_size=10, heading_font_size=12,
        margin_inches=0.75, line_spacing=1.0,
    ),
    "apa": JournalStyle(
        key="apa", name="APA 7th",
        citation_style="apa", columns=1,
        heading_numbering=True, abstract_required=True,
        word_limit=None, reference_section_title="References",
        title_font_size=12, body_font_size=12, heading_font_size=12,
        margin_inches=1.0, line_spacing=2.0,
    ),
    "gbt": JournalStyle(
        key="gbt", name="GB/T 7714",
        citation_style="gbt", columns=1,
        heading_numbering=True, abstract_required=True,
        word_limit=None, reference_section_title="参考文献",
        title_font_size=16, body_font_size=12, heading_font_size=14,
        margin_inches=1.0, line_spacing=1.5,
    ),
    "mla": JournalStyle(
        key="mla", name="MLA 9th",
        citation_style="mla", columns=1,
        heading_numbering=False, abstract_required=False,
        word_limit=None, reference_section_title="Works Cited",
        title_font_size=12, body_font_size=12, heading_font_size=12,
        margin_inches=1.0, line_spacing=2.0,
    ),
    "chicago": JournalStyle(
        key="chicago", name="Chicago",
        citation_style="chicago", columns=1,
        heading_numbering=False, abstract_required=False,
        word_limit=None, reference_section_title="Bibliography",
        title_font_size=12, body_font_size=12, heading_font_size=12,
        margin_inches=1.0, line_spacing=2.0,
    ),
    "vancouver": JournalStyle(
        key="vancouver", name="Vancouver",
        citation_style="vancouver", columns=1,
        heading_numbering=True, abstract_required=True,
        word_limit=None, reference_section_title="References",
        title_font_size=14, body_font_size=12, heading_font_size=13,
        margin_inches=1.0, line_spacing=1.5,
    ),
    "harvard": JournalStyle(
        key="harvard", name="Harvard",
        citation_style="harvard", columns=1,
        heading_numbering=False, abstract_required=False,
        word_limit=None, reference_section_title="References",
        title_font_size=14, body_font_size=12, heading_font_size=13,
        margin_inches=1.0, line_spacing=1.5,
    ),
    "general": JournalStyle(
        key="general", name="通用学术",
        citation_style="apa", columns=1,
        heading_numbering=True, abstract_required=False,
        word_limit=None, reference_section_title="参考文献",
        title_font_size=16, body_font_size=12, heading_font_size=14,
        margin_inches=1.0, line_spacing=1.5,
    ),
}


def get_journal_style(key: str) -> JournalStyle:
    """Get journal style by key, falling back to general."""
    return JOURNAL_STYLES.get(key, JOURNAL_STYLES["general"])


def list_journal_styles() -> list[dict]:
    """Return all journal styles as a list of dicts."""
    return [
        {
            "key": s.key,
            "name": s.name,
            "citation_style": s.citation_style,
            "columns": s.columns,
            "abstract_required": s.abstract_required,
            "word_limit": s.word_limit,
        }
        for s in JOURNAL_STYLES.values()
    ]
