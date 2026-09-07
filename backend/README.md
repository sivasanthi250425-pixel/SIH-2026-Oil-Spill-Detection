# Oil Spill Detection Backend

SIH 2026 MVP backend (PS SIH26143).

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
cd backend
uvicorn main:app --reload
```

## Docs

Open http://localhost:8000/docs for Swagger UI.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/detect-spill` | Detect oil spill from SAR image |
| POST | `/analyze-spill` | Analyze spill volume, drift, severity |
| GET | `/vessels` | Get AIS vessel candidates near spill |
| POST | `/attribute` | Rank vessels by attribution score |
