import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.testset import TestsetGenerator

APP_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = APP_DIR / ".env"
CHUNKS_FILE = APP_DIR / "data" / "output_chunks.json"
TESTSET_FILE = APP_DIR / "data" / "eval_testset.json"

load_dotenv(dotenv_path=ENV_FILE)


def _get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"[eval] {name} belum di-set di file .env.")
    return value


def _load_chunks_as_documents() -> list[Document]:
    if not CHUNKS_FILE.exists():
        raise SystemExit(
            f"[eval] File chunks tidak ditemukan: {CHUNKS_FILE}\n"
            "Jalankan `python manage.py setup --skip-ingest` terlebih dahulu."
        )
    with CHUNKS_FILE.open(encoding="utf-8") as f:
        chunks = json.load(f)

    docs = []
    for chunk in chunks:
        content = chunk.get("content", "").strip()
        if not content:
            continue
        docs.append(
            Document(
                page_content=content,
                metadata={
                    "source": chunk.get("chunk_parent", "unknown"),
                    "page_start": chunk.get("page_start", 0),
                    "page_end": chunk.get("page_end", 0),
                },
            )
        )
    return docs


def _build_generator() -> TestsetGenerator:
    api_key = _get_required_env("OPENAI_API_KEY")

    generator_llm = LangchainLLMWrapper(
        ChatOpenAI(model="gpt-4o", openai_api_key=api_key)
    )
    generator_embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(openai_api_key=api_key)
    )
    return TestsetGenerator(
        llm=generator_llm,
        embedding_model=generator_embeddings,
    )


def generate_testset() -> Path:
    _get_required_env("OPENAI_API_KEY")
    testset_size = int(os.getenv("RAGAS_TESTSET_SIZE", "20"))

    print(f"[eval] Memuat chunks dari {CHUNKS_FILE}...")
    docs = _load_chunks_as_documents()
    print(f"[eval] {len(docs)} dokumen siap untuk testset generation.")

    print(f"[eval] Generating {testset_size} synthetic Q&A pairs via gpt-4o...")
    generator = _build_generator()
    testset = generator.generate_with_langchain_docs(docs, testset_size=testset_size)

    rows = testset.to_pandas().to_dict("records")
    TESTSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TESTSET_FILE.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"[eval] Testset disimpan ke {TESTSET_FILE} ({len(rows)} samples).")
    return TESTSET_FILE
