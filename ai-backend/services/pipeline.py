import subprocess
import os
from .database import get_supabase

BUCKET_SOURCE = "ai-source-files"
BUCKET_OUTPUT = "ai-output-files"

# Root directory of this project (parent of ai-backend/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
# AI directory (where manage.py lives)
AI_DIR = os.path.join(PROJECT_ROOT, "ai")


def log_console(step: str, message: str):
    """Print log message to console."""
    print(f"[{step.upper()}] {message}")


async def download_source_file(source_url: str, project_id: str) -> str:
    """
    Download the source file from Supabase Storage to local project directory.
    Returns the local file path.
    """
    from .storage import download_file

    # Create project directory in ai/data/
    project_dir = os.path.join(AI_DIR, "data", project_id)
    os.makedirs(project_dir, exist_ok=True)

    # Extract file path from URL
    # URL format: https://xxx.supabase.co/storage/v1/object/public/bucket/path
    local_path = os.path.join(project_dir, "source.pdf")

    # Download the file
    log_console("download", f"Mendownload file dari storage: {source_url}")
    file_content = await download_file(BUCKET_SOURCE, f"{project_id}/source.pdf")
    with open(local_path, "wb") as f:
        f.write(file_content)

    log_console("download", f"File disimpan ke: {local_path}")
    return local_path


async def run_setup(project_id: str) -> bool:
    """
    Run the setup pipeline (extract chunks + ingest to Supabase).
    """
    log_console("setup", "Memulai setup pipeline...")

    try:
        supabase = get_supabase()
        supabase.table("projects").update({"status": "uploading"}).eq("id", project_id).execute()
    except Exception as e:
        log_console("setup", f"Warning: Gagal update status: {e}")

    try:
        log_console("setup", f"Menjalankan: python manage.py setup --project-id {project_id}")
        result = subprocess.run(
            [
                "python", "manage.py",
                "setup",
                "--project-id", project_id,
            ],
            cwd=AI_DIR,  # Run from ai/ directory so imports work
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        # Print all output to console
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    print(f"  [setup] {line}")
        if result.stderr:
            for line in result.stderr.strip().split("\n"):
                if line.strip():
                    print(f"  [setup:stderr] {line}")

        if result.returncode != 0:
            log_console("setup", f"ERROR: Setup gagal dengan exit code {result.returncode}")
            try:
                supabase = get_supabase()
                supabase.table("projects").update({
                    "status": "failed",
                    "error_message": f"Setup failed: {result.stderr[:200]}"
                }).eq("id", project_id).execute()
            except Exception:
                pass
            return False

        log_console("setup", "Setup selesai.")
        return True
    except subprocess.TimeoutExpired:
        log_console("setup", "ERROR: Setup timeout (>5 menit)")
        try:
            supabase = get_supabase()
            supabase.table("projects").update({
                "status": "failed",
                "error_message": "Setup timeout"
            }).eq("id", project_id).execute()
        except Exception:
            pass
        return False
    except Exception as e:
        log_console("setup", f"ERROR: Exception: {str(e)}")
        try:
            supabase = get_supabase()
            supabase.table("projects").update({
                "status": "failed",
                "error_message": str(e)
            }).eq("id", project_id).execute()
        except Exception:
            pass
        return False


async def run_extraction(project_id: str, source_url: str):
    """
    Run the AI extraction pipeline (extract metadata from chunks).
    """
    log_console("extraction", "Memulai ekstraksi metadata...")

    try:
        supabase = get_supabase()
        supabase.table("projects").update({"status": "extracting"}).eq("id", project_id).execute()
    except Exception as e:
        log_console("extraction", f"Warning: Gagal update status: {e}")

    try:
        log_console("extraction", f"Menjalankan: python manage.py extract --project-id {project_id}")
        result = subprocess.run(
            [
                "python", "manage.py",
                "extract",
                "--project-id", project_id,
            ],
            cwd=AI_DIR,  # Run from ai/ directory so imports work
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        # Print all output to console
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    print(f"  [extract] {line}")
        if result.stderr:
            for line in result.stderr.strip().split("\n"):
                if line.strip():
                    print(f"  [extract:stderr] {line}")

        if result.returncode != 0:
            log_console("extraction", f"ERROR: Ekstraksi gagal dengan exit code {result.returncode}")
            try:
                supabase = get_supabase()
                supabase.table("projects").update({
                    "status": "failed",
                    "error_message": f"Extraction failed: {result.stderr[:200]}"
                }).eq("id", project_id).execute()
            except Exception:
                pass
            return False

        log_console("extraction", "Ekstraksi selesai.")
        return True
    except subprocess.TimeoutExpired:
        log_console("extraction", "ERROR: Ekstraksi timeout (>10 menit)")
        try:
            supabase = get_supabase()
            supabase.table("projects").update({
                "status": "failed",
                "error_message": "Extraction timeout"
            }).eq("id", project_id).execute()
        except Exception:
            pass
        return False
    except Exception as e:
        log_console("extraction", f"ERROR: Exception: {str(e)}")
        try:
            supabase = get_supabase()
            supabase.table("projects").update({
                "status": "failed",
                "error_message": str(e)
            }).eq("id", project_id).execute()
        except Exception:
            pass
        return False


async def run_docx_generation(project_id: str):
    """
    Run the DOCX generation pipeline.
    """
    log_console("docx", "Memulai generate DOCX...")

    try:
        supabase = get_supabase()
        supabase.table("projects").update({"status": "generating"}).eq("id", project_id).execute()
    except Exception as e:
        log_console("docx", f"Warning: Gagal update status: {e}")

    try:
        log_console("docx", f"Menjalankan: python manage.py docx --type proposal --project-id {project_id}")
        result = subprocess.run(
            [
                "python", "manage.py",
                "docx",
                "--type", "proposal",
                "--project-id", project_id
            ],
            cwd=AI_DIR,  # Run from ai/ directory so imports work
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        # Print all output to console
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    print(f"  [docx] {line}")
        if result.stderr:
            for line in result.stderr.strip().split("\n"):
                if line.strip():
                    print(f"  [docx:stderr] {line}")

        if result.returncode != 0:
            log_console("docx", f"ERROR: DOCX generation gagal dengan exit code {result.returncode}")
            try:
                supabase = get_supabase()
                supabase.table("projects").update({
                    "status": "failed",
                    "error_message": f"DOCX generation failed: {result.stderr[:200]}"
                }).eq("id", project_id).execute()
            except Exception:
                pass
            return False

        log_console("docx", "DOCX generation selesai.")

        # Update status to completed
        result_url = f"ai-output-files/{project_id}/proposal_output.docx"
        log_console("docx", f"Output: {result_url}")

        try:
            supabase = get_supabase()
            supabase.table("projects").update({
                "status": "completed",
                "result_url": result_url
            }).eq("id", project_id).execute()
        except Exception:
            pass

        return True
    except subprocess.TimeoutExpired:
        log_console("docx", "ERROR: DOCX generation timeout (>10 menit)")
        try:
            supabase = get_supabase()
            supabase.table("projects").update({
                "status": "failed",
                "error_message": "DOCX generation timeout"
            }).eq("id", project_id).execute()
        except Exception:
            pass
        return False
    except Exception as e:
        log_console("docx", f"ERROR: Exception: {str(e)}")
        try:
            supabase = get_supabase()
            supabase.table("projects").update({
                "status": "failed",
                "error_message": str(e)
            }).eq("id", project_id).execute()
        except Exception:
            pass
        return False


async def run_pipeline(project_id: str, source_url: str):
    """
    Run the complete pipeline: download -> setup -> extraction -> DOCX generation.
    """
    log_console("pipeline", "=" * 60)
    log_console("pipeline", f"MULAI PIPELINE untuk project: {project_id}")
    log_console("pipeline", "=" * 60)

    # Step 1: Download source file from storage
    try:
        log_console("pipeline", "Step 1/4: Download file dari Supabase Storage...")
        await download_source_file(source_url, project_id)
        log_console("pipeline", "Step 1/4: Download selesai.")
    except Exception as e:
        log_console("pipeline", f"ERROR Step 1: Download gagal - {str(e)}")
        try:
            supabase = get_supabase()
            supabase.table("projects").update({
                "status": "failed",
                "error_message": f"Download failed: {str(e)}"
            }).eq("id", project_id).execute()
        except Exception:
            pass
        return False

    # Step 2: Run setup (extract chunks + ingest)
    log_console("pipeline", "Step 2/4: Setup (chunk extraction + ingest)...")
    setup_success = await run_setup(project_id)
    if not setup_success:
        log_console("pipeline", "Pipeline berhenti karena setup gagal.")
        return False
    log_console("pipeline", "Step 2/4: Setup selesai.")

    # Step 3: Run extraction
    log_console("pipeline", "Step 3/4: Ekstraksi metadata (RAG + LLM)...")
    extraction_success = await run_extraction(project_id, source_url)
    if not extraction_success:
        log_console("pipeline", "Pipeline berhenti karena ekstraksi gagal.")
        return False
    log_console("pipeline", "Step 3/4: Ekstraksi selesai.")

    # Update status to extracted
    try:
        supabase = get_supabase()
        supabase.table("projects").update({"status": "extracted"}).eq("id", project_id).execute()
    except Exception:
        pass

    # Step 4: Run DOCX generation
    log_console("pipeline", "Step 4/4: Generate DOCX...")
    docx_success = await run_docx_generation(project_id)
    if docx_success:
        log_console("pipeline", "=" * 60)
        log_console("pipeline", "PIPELINE SELESAI BERHASIL!")
        log_console("pipeline", "=" * 60)
    else:
        log_console("pipeline", "Pipeline berhenti karena DOCX generation gagal.")

    return docx_success
