# TAco — AI-assisted homework review

TAco is a web service that helps course staff review student homework. It
prepares a structured draft review, but keeps the final decision with a human
reviewer.

The system combines file parsing, rubric-based grading, line-level comments,
cross-checking between submissions, AI-generated-text signals, and reviewer
assignment in one workflow.

## Contents
- [What the project does](#what-the-project-does)
- [Requirements](#requirements)
- [Quick local start](#quick-local-start)
- [Configuration](#configuration)
- [Review workflow](#review-workflow)
- [Supported formats](#supported-formats)

## What the project does

TAco is designed for TAs and other course staff who need to review many
assignments consistently. A reviewer can open a submission and see:

- the assignment statement and rubric
- a preliminary status and score for each criterion
- evidence and source line ranges from the submission
- cross-check matches with other submissions
- a local AI-generated-text signal
- draft comments that can be edited, reused, and sent.

The product follows a human-in-the-loop model. AI results are stored as
preliminary recommendations, while the reviewer confirms the final grade and
controls which comments are sent.

## Requirements

- Python 3.14+
- `uv`
- Node.js and npm
- Docker and Docker Compose, for the recommended setup
- An OpenAI-compatible LLM endpoint for automatic rubric grading (optional)
- Local GigaCheck model weights for AI-generated-text detection (optional)

## Quick local start

### Backend with Docker

```bash
cp .env.example .env
docker compose up --build
```

The API is available at <http://localhost:8000/docs>. The worker and
PostgreSQL start automatically. For LLM grading, set `LLM_MODEL` and
`LLM_API_KEY` in `.env`.

### Frontend

In a second terminal:

```bash
cd frontend && npm install && npm run dev
```

Open the Vite URL, usually <http://localhost:5173>.

For local backend development without Docker, set `POSTGRES_HOST=localhost`,
then run `uv sync`, `uv run uvicorn app.main:app --reload`, and
`uv run python -m app.worker` in separate terminals.

## Configuration

`.env.example` contains the full list of settings. The main groups are:

| Group | Important settings | Purpose |
| --- | --- | --- |
| Database | `POSTGRES_*` | PostgreSQL connection |
| LLM grader | `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | Critic and rubric grading |
| Cross-check | `CROSSCHECK_*` | Similarity thresholds and matching rules |
| AI-check | `AICHECK_MODEL_DIR`, `AICHECK_DEVICE` | Local GigaCheck detector |
| Authentication | `SECRET_KEY`, `JWT_*` | Access token configuration |

The grader can run without an LLM configuration, but criteria remain
unmarked. The AI-check job reports `unavailable` when model weights are not
configured, so the rest of the submission pipeline can continue.

To enable the local GigaCheck detector, download the model snapshot once:

```bash
uv run python -c "from huggingface_hub import snapshot_download; print(snapshot_download('iitolstykh/GigaCheck-Classifier-Multi'))"
```

## Review workflow

```text
Create assignment and rubric
		  |
Upload submission -> parse text -> enqueue jobs
		  |
heuristics | grader | cross-check | AI-check | comment reuse
		  |
Reviewer reads evidence, edits comments, and confirms final grade
```


## Supported formats

The parser detects formats from file contents rather than trusting the file
name. The current supported inputs are:
- plain text, Markdown files
- PDF files 
- DOCX

Scanned PDFs without a text layer require OCR and are rejected for now.

