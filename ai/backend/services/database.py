from pathlib import Path
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load dari ai/.env (root env bersama), lalu override dengan ai/backend/.env jika ada
_AI_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_AI_ROOT / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_supabase() -> Client:
    return supabase_client
