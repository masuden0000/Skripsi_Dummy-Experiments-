-- Reset semua RLS policy yang tidak diperlukan secara fungsional.
--
-- Hasil analisis:
--   - Satu-satunya akses browser langsung (anon key) adalah Realtime subscription
--     admin di tabel `projects`. Semua akses lain melalui service_role yang bypass RLS.
--   - RLS policy hanya benar-benar fungsional untuk admin di tabel `projects`.
--   - Policy di tabel lain tidak mempengaruhi fungsionalitas apapun karena semua
--     backend (Express, FastAPI, Next.js API routes) menggunakan service_role key.
--
-- Yang dilakukan migration ini:
--   1. Drop semua policy lama yang terlalu lebar atau tidak diperlukan
--   2. Drop policy reviewer di validation_sessions dan validation_results
--   3. Tambah satu policy yang benar-benar fungsional: admin SELECT di projects

-- ── Drop policy lama di profiles ──────────────────────────────────────────────
drop policy if exists "users read own profile" on public.profiles;

-- ── Drop policy lama di reviewer_profiles ────────────────────────────────────
drop policy if exists "reviewers read own reviewer profile" on public.reviewer_profiles;

-- ── Drop policy lama di pkm_schemas ──────────────────────────────────────────
drop policy if exists "pkm_schemas_select" on public.pkm_schemas;

-- ── Drop policy lama di faculties ────────────────────────────────────────────
drop policy if exists "authenticated users can read faculties" on public.faculties;

-- ── Drop policy lama di pkm_review_periods ───────────────────────────────────
drop policy if exists "authenticated users can read pkm review periods" on public.pkm_review_periods;

-- ── Drop policy lama di assignments ──────────────────────────────────────────
drop policy if exists "authenticated users can read assignments"   on public.assignments;
drop policy if exists "authenticated users can create assignments" on public.assignments;
drop policy if exists "authenticated users can update assignments" on public.assignments;

-- ── Drop policy lama di projects ─────────────────────────────────────────────
drop policy if exists "service role can read projects"   on public.projects;
drop policy if exists "service role can insert projects" on public.projects;
drop policy if exists "service role can update projects" on public.projects;
drop policy if exists "service role can delete projects" on public.projects;

-- ── Drop policy lama di project_logs ─────────────────────────────────────────
drop policy if exists "Service role full access" on public.project_logs;

-- ── Drop policy reviewer di validation_sessions ───────────────────────────────
drop policy if exists "reviewer full access on validation_sessions" on public.validation_sessions;

-- ── Drop policy reviewer di validation_results ────────────────────────────────
drop policy if exists "reviewer full access on validation_results" on public.validation_results;

-- ── Tambah satu policy fungsional: admin SELECT di projects ───────────────────
-- Dibutuhkan agar Realtime subscription (anon key) di halaman proposal admin
-- dapat menerima event UPDATE dari tabel projects.
create policy "admin can read projects"
  on public.projects
  for select
  to authenticated
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid()
        and role = 'admin'
    )
  );
