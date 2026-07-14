# MediScan+

Prescription photo in → structured medicine info out: corrected drug names, dosage
reference, side effects, generic alternatives, packaging image, and purchase-search
links. Served as a small Flask app with a server-rendered UI.

**Design principle:** this is an information layer, not a decision layer. The app
never gates access to information based on severity, never states a personalized
dose, and never invents safety data — everything side-effect/dosage-related is
pulled from a real source (OpenFDA) and cited.

## Pipeline

```
image
  │
  ▼
[1] ocr_parse         OCR.Space extracts raw text -> LLM structures it into drug candidates
  │                     + legible dosage/timing
  ▼
[2] normalize          RxNorm approximateTerm -> canonical name + RxCUI per drug
  │
  ▼
[3] confidence_check    pure logic — flags low-confidence items, never hides/blocks
  │
  ▼  (fan out: one Send() branch per drug)
[4] enrich_drug × N      per drug, concurrently:
  │                       - general dosage/timing (OpenFDA label)
  │                       - side effects (OpenFDA label, verbatim + cited)
  │                       - generic alternatives (RxNorm related concepts)
  │                       - e-commerce search links (1mg/PharmEasy/Netmeds)
  │                       - packaging image (DailyMed, via RxCUI)
  ▼  (fan back in via operator.add reducer)
[5] synthesizer          assembles the final report + standing disclaimers
```

The fan-out at step [4] uses LangGraph's `Send` API — a 3-medicine prescription
runs 3 parallel enrichment branches, merged back together by the `operator.add`
reducer on `MediScanState.enriched_drugs`.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in GROQ_API_KEY and OCR_SPACE_API_KEY
```

## Run

```bash
python -m app.main
# or, for production-style serving:
gunicorn app.main:app --bind 0.0.0.0:8000
```

Open `http://localhost:8000/` — this is the web UI, not a JSON API root.

### Routes
- `GET /` — upload form.
- `POST /analyze` — accepts the uploaded prescription photo (`multipart/form-data`,
  field name `file`, JPEG/PNG, up to 15MB), runs the pipeline, and renders the
  same page server-side with the resulting medicine cards. There is no separate
  JSON endpoint; `templates/index.html` is rendered directly with the report data.
- `GET /sample` — renders the page with a static sample report, no pipeline run
  and no API keys needed, to preview the UI.
- `GET /health` — liveness check.

### Web UI
Server-rendered with Flask/Jinja (`templates/index.html`, `static/style.css`) —
there's no client-side fetch/JSON layer. Cards are sorted by how complete
their data is (packaging image, summary, label dosage, side effects,
generics, purchase links — most complete first), and side effects are shown
as a short, cited list rather than the raw FDA label paragraph: an LLM
extracts only the effects explicitly named in the label text (still sourced
and cited), falling back to the trimmed raw text if extraction fails.

## Deploying to Render
This repo ships a `render.yaml` blueprint plus a `Procfile` fallback.

1. Push the repo to GitHub/GitLab.
2. In Render, **New > Blueprint**, point it at the repo — it picks up `render.yaml`.
3. Set the secret env vars it leaves blank (`GROQ_API_KEY`, `OCR_SPACE_API_KEY`)
   in the Render dashboard.
4. Deploy. Render runs `pip install -r requirements.txt` then
   `gunicorn app.main:app --bind 0.0.0.0:$PORT`.

No code changes are needed for the port — `app.main` reads `$PORT` when run
directly, and the gunicorn start command binds to it explicitly either way.

## Project layout

```
app/
├── main.py                        # Flask app: /, /analyze, /sample, /health
├── sample_report.py                # Static report used by /sample
├── config.py                       # env vars + thresholds
├── graph/
│   ├── state.py                     # MediScanState (+ operator.add reducer for enrichment fan-in)
│   ├── builder.py                    # StateGraph wiring, Send()-based fan-out
│   └── nodes/
│       ├── ocr_parse.py               # [1]
│       ├── normalize.py               # [2]
│       ├── confidence_check.py        # [3]
│       ├── enrich_drug.py             # [4] — Send() target, runs 5 sub-lookups concurrently
│       ├── enrichment/
│       │   ├── dosage.py               # [4a]
│       │   ├── side_effects.py         # [4b]
│       │   ├── generics.py             # [4c]
│       │   └── ecommerce_links.py      # [4d]
│       └── synthesizer.py             # [5]
├── clients/                        # one file per external API
│   ├── vision_client.py               # OCR.Space
│   ├── llm_client.py                  # Groq / OpenAI / Anthropic, provider-agnostic
│   ├── rxnorm_client.py               # RxNorm approximate match + related concepts
│   ├── openfda_client.py              # FDA label data (dosage, side effects)
│   └── openmed.py                     # DailyMed packaging image lookup
└── schemas/                        # Pydantic models per pipeline stage
    ├── ocr.py
    ├── normalization.py
    ├── enrichment.py
    └── report.py
templates/
└── index.html                      # Jinja template — upload form + result cards
static/
└── style.css
render.yaml                          # Render blueprint (build/start commands, env vars)
Procfile                             # fallback start command for platforms that read it
```

## Known things to check on your machine

- **OCR.Space, RxNorm, OpenFDA, and DailyMed calls all need outbound network
  access** — all free/no-key-required except OCR.Space (needs `OCR_SPACE_API_KEY`)
  and Groq (needs `GROQ_API_KEY`).
- **RxNorm/OpenFDA/DailyMed are US-centric sources** — Indian brand names (e.g.
  "Dolo 650") often won't resolve. Matching the underlying generic salt name
  (e.g. "Paracetamol") works fine, since that's universal. An Indian brand→salt
  lookup as an additional normalization tier is the natural next step.
- **`.env` is gitignored on purpose** — never commit real API keys. If a key has
  ever been hardcoded or shared, rotate it.
