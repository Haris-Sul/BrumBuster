# BrumBuster Backend

## Setup

### Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in the repo root:

```bash
SERPAPI_API_KEY=
FLASK_ENV=development
FLASK_DEBUG=1
REQUEST_TIMEOUT_SECONDS=12
```

### Run the API

```bash
python backend/run.py
```
