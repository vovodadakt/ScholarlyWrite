# ScholarlyWrite

AI-powered academic writing platform built with FastAPI.

## Features

- **AI-Assisted Writing** — Generate outlines and draft chapters with Claude (Anthropic) or OpenAI
- **Reference Management** — DOI lookup and journal-style formatting
- **Data & Charts** — Process experimental data and generate figures (matplotlib)
- **Export** — Export to Word (DOCX), PDF, LaTeX, and Excel formats
- **Project Management** — Organize writing projects with chapters, outlines, and experiments
- **Streaming** — Real-time streaming AI responses for interactive writing

## Tech Stack

- **Backend**: FastAPI + Uvicorn
- **Database**: SQLAlchemy (SQLite / MySQL) with Alembic migrations
- **Auth**: JWT (python-jose + bcrypt)
- **AI**: Anthropic Claude SDK + OpenAI SDK
- **Export**: python-docx, fpdf2, openpyxl, matplotlib

## Quick Start

```bash
# Clone the repo
git clone git@github.com:vovodadakt/ScholarlyWrite.git
cd ScholarlyWrite

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and settings

# Run the server
uvicorn app.main:app --reload
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./writing_platform.db` |
| `JWT_SECRET` | Secret key for JWT tokens | (auto-generated in debug mode) |
| `ANTHROPIC_API_KEY` | Anthropic API key | — |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `DEFAULT_AI_PROVIDER` | Default AI provider (`claude` or `openai`) | `claude` |
| `DEBUG` | Debug mode | `true` |

## License

MIT
