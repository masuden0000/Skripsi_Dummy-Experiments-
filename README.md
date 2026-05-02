# Skripsi Dummy Project 1 (AI)

Repository ini berisi pipeline end-to-end untuk:

- ekstraksi PDF menjadi markdown + chunks,
- ingest chunks ke Supabase (dengan embedding),
- ekstraksi metadata dokumen berbasis RAG + LLM,
- schema diff (structured vs free extraction),
- translasi style ke python-docx dan generator DOCX proposal.

## Lokasi Aplikasi

Seluruh source utama ada di folder `app/`.

## Quick Start

1. Buat virtual environment dan aktifkan:

```bash
python -m venv .venv
source .venv/Scripts/activate
```

2. Install dependency:

```bash
cd app
pip install -r requirements.txt
```

3. Siapkan environment di `app/.env` sesuai kebutuhan project (`GROQ_API_KEY`, `GOOGLE_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, dll).

4. Jalankan pipeline utama:

```bash
python manage.py setup
python manage.py extract
python manage.py docx --type proposal
```

## Command CLI

Semua command dijalankan dari folder `app/`:

- `python manage.py setup`
	- Ekstrak PDF -> `output.md` + `output_chunks.json`, lalu ingest ke Supabase.
- `python manage.py setup --skip-ingest`
	- Hanya build chunk lokal tanpa upsert ke Supabase.
- `python manage.py extract`
	- Ekstraksi metadata terstruktur ke `data/output.json` + upsert metadata ke Supabase.
- `python manage.py schema-diff`
	- Jalankan free extraction dan bandingkan dengan `output.json`, hasil diff disimpan ke `data/schema_diff_<timestamp>.json/.md`.
- `python manage.py docx --type proposal`
	- Generate dokumen DOCX proposal dari metadata + chunks.
- `python manage.py docx-style-map`
	- Jalankan pipeline mapping style DOCX (catalog, retrieval, candidate, validasi, apply plan).

## Struktur Ringkas

```text
app/
|-- data/
|   |-- output.md
|   |-- output_chunks.json
|   |-- output.json
|   `-- docx_mapping_*.json
|-- infra/
|-- model_ai/
|   |-- loader/
|   |-- extractor/
|   |-- docx/
|   `-- visualisasi/
|-- testing ekstraksi/
|-- manage.py
`-- requirements.txt
```

## Catatan Perubahan Terbaru

- Prompt extractor sudah dipusatkan ke `model_ai/extractor/prompts/*.md` via registry di `model_ai/extractor/prompts.py`.
- Ditambahkan modul `model_ai/extractor/schema_differ.py` + command `schema-diff`.
- Pipeline DOCX diperkuat dengan:
	- `model_ai/docx/generator.py`,
	- `model_ai/docx/metadata_loader.py`,
	- `model_ai/docx/style_mapping_pipeline.py`,
	- `model_ai/docx/instructional_placeholder_builder.py`.
- Ditambahkan utilitas evaluasi translasi di folder `testing ekstraksi/`.
- Ditambahkan halaman visualisasi pipeline di `model_ai/visualisasi/`.

