"""Auto-migration: add missing columns to existing tables on startup."""
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy import inspect

EXPECTED = {
    "user_settings": {
        "system_font": "VARCHAR(100) NOT NULL DEFAULT ''",
        "editor_font": "VARCHAR(100) NOT NULL DEFAULT ''",
    },
    "projects": {
        "context": "TEXT NOT NULL DEFAULT ('{}')",
        "word_count": "INTEGER NOT NULL DEFAULT 0",
        "deadline": "VARCHAR(30) NULL",
        "tags": "TEXT NOT NULL DEFAULT ('[]')",
        "template_name": "VARCHAR(100) NOT NULL DEFAULT ''",
        "journal_style": "VARCHAR(50) NOT NULL DEFAULT ''",
        "conversation_summary": "TEXT NOT NULL DEFAULT ''",
    },
    "chapters": {
        "parent_id": "VARCHAR(32) NULL",
        "chapter_number": "VARCHAR(20) NOT NULL DEFAULT ''",
        "level": "INTEGER NOT NULL DEFAULT 1",
    },
    "experiments": {
        "version": "INTEGER NOT NULL DEFAULT 1",
    },
    "figures": {
        "figure_number": "INTEGER NOT NULL DEFAULT 0",
        "width": "VARCHAR(20) NOT NULL DEFAULT '0.8'",
        "alt_text": "TEXT NOT NULL DEFAULT ''",
    },
    "references": {
        "pub_type": "VARCHAR(30) NOT NULL DEFAULT 'article'",
        "volume": "VARCHAR(100) NOT NULL DEFAULT ''",
        "issue": "VARCHAR(100) NOT NULL DEFAULT ''",
        "pages": "VARCHAR(100) NOT NULL DEFAULT ''",
        "publisher": "VARCHAR(100) NOT NULL DEFAULT ''",
        "raw_bibtex": "TEXT NOT NULL DEFAULT ''",
    },
}


def _migrate_sync(conn: Connection):
    inspector = inspect(conn)
    for table_name, columns in EXPECTED.items():
        try:
            existing = {col["name"] for col in inspector.get_columns(table_name)}
        except Exception:
            continue

        for col_name, col_def in columns.items():
            if col_name not in existing:
                sql = f'ALTER TABLE "{table_name}" ADD COLUMN {col_name} {col_def}'
                conn.execute(text(sql))


async def auto_migrate(engine):
    async with engine.begin() as conn:
        await conn.run_sync(_migrate_sync)
