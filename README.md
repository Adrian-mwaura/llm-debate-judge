# LLM Debate and LLM Judge

This is our course final project.
We study multi-agent debate and LLM judges with the DeepSeek API (`deepseek-flash`).
We compare our own method with chain-of-thought and self-consistency baselines at the same API cost.

- Brief: [docs/project_brief.pdf](docs/project_brief.pdf)
- Roles: [docs/ROLES.md](docs/ROLES.md)
- Status, decisions, runs and budget: [docs/NOTES.md](docs/NOTES.md)
- Context for coding agents: [AGENTS.md](AGENTS.md)

## Setup

macOS, Linux or Git Bash:

```bash
python -m venv .venv
source .venv/bin/activate        # Git Bash on Windows: source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env             # then put your DeepSeek key in .env
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Running

Not built yet. The planned commands are `bash scripts/run_baseline.sh`, `bash scripts/run_method.sh`, and `python scripts/make_table.py`.
The last one rebuilds the main results table from the committed logs.
