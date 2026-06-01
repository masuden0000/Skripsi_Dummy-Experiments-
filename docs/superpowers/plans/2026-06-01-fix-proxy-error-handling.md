# Fix Proxy Error Handling & Auth Client Singleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tambahkan error handling pada semua 22 frontend API route yang mem-proxy ke backend, dan ubah `createAuthClient()` menjadi singleton agar warmup koneksi efektif.

**Architecture:** Satu helper `proxyToBackend()` ditambahkan ke `frontend/lib/backend-api.ts` yang membungkus `fetch()` dengan try/catch dan mengembalikan HTTP 503 jika backend tidak terjangkau. Semua route menggunakan helper ini. Di sisi backend, factory `createAuthClient()` diubah menjadi exported singleton `authClient` agar instance yang sama digunakan oleh warmup dan setiap login request.

**Tech Stack:** Next.js 16 App Router (TypeScript), Node.js/Express backend (ESM)

---

## File Structure

**Dibuat:**
- _(tidak ada file baru)_

**Dimodifikasi — Frontend:**
- `frontend/lib/backend-api.ts` — tambah `proxyToBackend()` helper
- `frontend/app/api/auth/login/route.ts` — pakai `proxyToBackend` + `forwardSetCookie`
- `frontend/app/api/auth/logout/route.ts` — pakai `proxyToBackend` + `forwardSetCookie`
- `frontend/app/api/auth/session/route.ts` — pakai `proxyToBackend`
- `frontend/app/api/assignments/route.ts` — pakai `proxyToBackend`
- `frontend/app/api/assignments/[id]/route.ts` — pakai `proxyToBackend`
- `frontend/app/api/reviewer-assignments/route.ts` — pakai `proxyToBackend`
- `frontend/app/api/reviewer-assignments/active/route.ts` — pakai `proxyToBackend`
- `frontend/app/api/faculties/route.ts` — pakai `proxyToBackend`
- `frontend/app/api/faculties/[id]/route.ts` — pakai `proxyToBackend`
- `frontend/app/api/faculties/[id]/reviewers/route.ts` — pakai `proxyToBackend`
- `frontend/app/api/reviewers/route.ts` — pakai `proxyToBackend`
- `frontend/app/api/reviewers/[id]/route.ts` — pakai `proxyToBackend`
- `frontend/app/api/review-periods/route.ts` — pakai `proxyToBackend`
- `frontend/app/api/review-periods/[id]/route.ts` — pakai `proxyToBackend`
- `frontend/app/api/pkm/schemas/route.ts` — pakai `proxyToBackend`
- `frontend/app/api/pkm/validation/run/route.ts` — pakai `proxyToBackend`
- `frontend/app/api/projects/route.ts` — pakai `proxyToBackend`, hapus local `BACKEND_URL`
- `frontend/app/api/projects/[id]/route.ts` — pakai `proxyToBackend`, hapus local `BACKEND_URL`
- `frontend/app/api/projects/[id]/generate/route.ts` — pakai `proxyToBackend`, hapus local `BACKEND_URL`
- `frontend/app/api/projects/[id]/placeholders/route.ts` — pakai `proxyToBackend`, hapus local `BACKEND_URL`
- `frontend/app/api/projects/confirm-upload/route.ts` — pakai `proxyToBackend`, hapus local `BACKEND_URL`
- `frontend/app/api/projects/[id]/logs/route.ts` — wrap SSE path dengan try/catch manual, hapus local `BACKEND_URL`

**Tidak disentuh (bukan backend proxy):**
- `frontend/app/api/projects/[id]/metadata/route.ts` — akses Supabase langsung, sudah ada error handling
- `frontend/app/api/projects/history/route.ts` — akses Supabase langsung, sudah ada error handling

**Dimodifikasi — Backend:**
- `backend/src/config/supabase.js` — ubah `createAuthClient` factory → `authClient` singleton
- `backend/src/services/auth.service.js` — pakai singleton `authClient`
- `backend/src/server.js` — import `authClient` singleton

---

## Task 1: Tambah `proxyToBackend` helper

**Files:**
- Modify: `frontend/lib/backend-api.ts`

- [ ] **Step 1: Ganti isi `frontend/lib/backend-api.ts` dengan versi yang sudah ada helper**

```typescript
import { NextResponse } from "next/server"

const DEFAULT_BACKEND_URL = "http://127.0.0.1:4000"

export function getBackendBaseUrl() {
  return process.env.NEXT_PUBLIC_BACKEND_URL || DEFAULT_BACKEND_URL
}

type ProxyOptions = Omit<RequestInit, "cache"> & {
  /** Cookie header yang diteruskan ke backend (isi dengan request.headers.get("cookie")) */
  cookie?: string | null
  /** Jika true, header set-cookie dari backend diteruskan kembali ke browser */
  forwardSetCookie?: boolean
}

/**
 * Proxy request ke backend dengan error handling.
 * Jika backend tidak terjangkau (network error), mengembalikan HTTP 503.
 */
export async function proxyToBackend(
  path: string,
  options: ProxyOptions = {}
): Promise<NextResponse> {
  const { cookie, forwardSetCookie, headers: extraHeaders, ...fetchOptions } = options

  const headers: Record<string, string> = {
    ...(extraHeaders as Record<string, string> ?? {}),
  }
  if (cookie) {
    headers["cookie"] = cookie
  }

  try {
    const backendResponse = await fetch(`${getBackendBaseUrl()}${path}`, {
      ...fetchOptions,
      headers,
      cache: "no-store",
    })

    const responseText = await backendResponse.text()
    const response = new NextResponse(responseText, {
      status: backendResponse.status,
      headers: {
        "content-type": backendResponse.headers.get("content-type") ?? "application/json",
      },
    })

    if (forwardSetCookie) {
      const setCookie = backendResponse.headers.get("set-cookie")
      if (setCookie) response.headers.set("set-cookie", setCookie)
    }

    return response
  } catch {
    return NextResponse.json(
      { error: "Tidak dapat menjangkau server backend." },
      { status: 503 }
    )
  }
}
```

- [ ] **Step 2: Pastikan TypeScript tidak ada error**

```
cd frontend && npx tsc --noEmit
```

Expected: tidak ada error terkait `backend-api.ts`.

- [ ] **Step 3: Commit**

```
git add frontend/lib/backend-api.ts
git commit -m "feat(frontend): tambah proxyToBackend helper dengan error handling 503"
```

---

## Task 2: Update auth routes

**Files:**
- Modify: `frontend/app/api/auth/login/route.ts`
- Modify: `frontend/app/api/auth/logout/route.ts`
- Modify: `frontend/app/api/auth/session/route.ts`

- [ ] **Step 1: Update `frontend/app/api/auth/login/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

export async function POST(request: Request) {
  const body = await request.text()
  return proxyToBackend("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    cookie: request.headers.get("cookie"),
    forwardSetCookie: true,
  })
}
```

- [ ] **Step 2: Update `frontend/app/api/auth/logout/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

export async function POST(request: Request) {
  return proxyToBackend("/api/auth/logout", {
    method: "POST",
    cookie: request.headers.get("cookie"),
    forwardSetCookie: true,
  })
}
```

- [ ] **Step 3: Update `frontend/app/api/auth/session/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

export async function GET(request: Request) {
  return proxyToBackend("/api/auth/session", {
    method: "GET",
    cookie: request.headers.get("cookie"),
  })
}
```

- [ ] **Step 4: Pastikan TypeScript tidak ada error**

```
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Test manual — login saat backend mati**

Matikan backend → buka halaman login → submit form → seharusnya muncul pesan error di form (bukan halaman error Next.js), karena `apiFetch` di `client.ts` menangkap 503 dan mengembalikan `{ error: "..." }`.

- [ ] **Step 6: Commit**

```
git add frontend/app/api/auth/login/route.ts frontend/app/api/auth/logout/route.ts frontend/app/api/auth/session/route.ts
git commit -m "fix(frontend): auth routes pakai proxyToBackend, handle error backend tidak aktif"
```

---

## Task 3: Update standard proxy routes

**Files:** assignments, reviewer-assignments, faculties, reviewers, review-periods, pkm/schemas, pkm/validation (10 file)

- [ ] **Step 1: Update `frontend/app/api/assignments/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

export async function GET(request: Request) {
  return proxyToBackend("/api/assignments", {
    method: "GET",
    cookie: request.headers.get("cookie"),
  })
}

export async function POST(request: Request) {
  const body = await request.text()
  return proxyToBackend("/api/assignments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    cookie: request.headers.get("cookie"),
  })
}
```

- [ ] **Step 2: Update `frontend/app/api/assignments/[id]/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

type RouteContext = {
  params: Promise<{ id: string }>
}

export async function PUT(request: Request, context: RouteContext) {
  const { id } = await context.params
  const body = await request.text()
  return proxyToBackend(`/api/assignments/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body,
    cookie: request.headers.get("cookie"),
  })
}

export async function DELETE(request: Request, context: RouteContext) {
  const { id } = await context.params
  return proxyToBackend(`/api/assignments/${id}`, {
    method: "DELETE",
    cookie: request.headers.get("cookie"),
  })
}
```

- [ ] **Step 3: Update `frontend/app/api/reviewer-assignments/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

export async function GET(request: Request) {
  return proxyToBackend("/api/reviewer-assignments", {
    method: "GET",
    cookie: request.headers.get("cookie"),
  })
}
```

- [ ] **Step 4: Update `frontend/app/api/reviewer-assignments/active/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

export async function GET(request: Request) {
  return proxyToBackend("/api/reviewer-assignments/active", {
    method: "GET",
    cookie: request.headers.get("cookie"),
  })
}
```

- [ ] **Step 5: Update `frontend/app/api/faculties/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

export async function GET(request: Request) {
  return proxyToBackend("/api/faculties", {
    method: "GET",
    cookie: request.headers.get("cookie"),
  })
}

export async function POST(request: Request) {
  const body = await request.text()
  return proxyToBackend("/api/faculties", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    cookie: request.headers.get("cookie"),
  })
}
```

- [ ] **Step 6: Update `frontend/app/api/faculties/[id]/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

type RouteContext = {
  params: Promise<{ id: string }>
}

export async function GET(request: Request, context: RouteContext) {
  const { id } = await context.params
  return proxyToBackend(`/api/faculties/${id}`, {
    method: "GET",
    cookie: request.headers.get("cookie"),
  })
}

export async function PUT(request: Request, context: RouteContext) {
  const { id } = await context.params
  const body = await request.text()
  return proxyToBackend(`/api/faculties/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body,
    cookie: request.headers.get("cookie"),
  })
}

export async function DELETE(request: Request, context: RouteContext) {
  const { id } = await context.params
  return proxyToBackend(`/api/faculties/${id}`, {
    method: "DELETE",
    cookie: request.headers.get("cookie"),
  })
}
```

- [ ] **Step 7: Update `frontend/app/api/faculties/[id]/reviewers/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

export async function GET(
  request: Request,
  context: { params: Promise<{ id: string }> }
) {
  const { id } = await context.params
  return proxyToBackend(`/api/faculties/${id}/reviewers`, {
    method: "GET",
    cookie: request.headers.get("cookie"),
  })
}
```

- [ ] **Step 8: Update `frontend/app/api/reviewers/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

export async function GET(request: Request) {
  return proxyToBackend("/api/reviewers", {
    method: "GET",
    cookie: request.headers.get("cookie"),
  })
}

export async function POST(request: Request) {
  const body = await request.text()
  return proxyToBackend("/api/reviewers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    cookie: request.headers.get("cookie"),
  })
}
```

- [ ] **Step 9: Update `frontend/app/api/reviewers/[id]/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

type RouteContext = {
  params: Promise<{ id: string }>
}

export async function PUT(request: Request, context: RouteContext) {
  const { id } = await context.params
  const body = await request.text()
  return proxyToBackend(`/api/reviewers/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body,
    cookie: request.headers.get("cookie"),
  })
}

export async function DELETE(request: Request, context: RouteContext) {
  const { id } = await context.params
  return proxyToBackend(`/api/reviewers/${id}`, {
    method: "DELETE",
    cookie: request.headers.get("cookie"),
  })
}
```

- [ ] **Step 10: Update `frontend/app/api/review-periods/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

export async function GET(request: Request) {
  return proxyToBackend("/api/review-periods", {
    method: "GET",
    cookie: request.headers.get("cookie"),
  })
}

export async function POST(request: Request) {
  const body = await request.text()
  return proxyToBackend("/api/review-periods", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    cookie: request.headers.get("cookie"),
  })
}
```

- [ ] **Step 11: Update `frontend/app/api/review-periods/[id]/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

type RouteContext = {
  params: Promise<{ id: string }>
}

export async function GET(request: Request, context: RouteContext) {
  const { id } = await context.params
  return proxyToBackend(`/api/review-periods/${id}`, {
    method: "GET",
    cookie: request.headers.get("cookie"),
  })
}

export async function PUT(request: Request, context: RouteContext) {
  const { id } = await context.params
  const body = await request.text()
  return proxyToBackend(`/api/review-periods/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body,
    cookie: request.headers.get("cookie"),
  })
}

export async function DELETE(request: Request, context: RouteContext) {
  const { id } = await context.params
  return proxyToBackend(`/api/review-periods/${id}`, {
    method: "DELETE",
    cookie: request.headers.get("cookie"),
  })
}
```

- [ ] **Step 12: Update `frontend/app/api/pkm/schemas/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

export async function GET() {
  return proxyToBackend("/api/pkm/schemas", {
    method: "GET",
  })
}
```

- [ ] **Step 13: Update `frontend/app/api/pkm/validation/run/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

export async function POST(request: Request) {
  const formData = await request.formData()
  return proxyToBackend("/api/pkm/validation/run", {
    method: "POST",
    body: formData,
  })
}
```

- [ ] **Step 14: Pastikan TypeScript tidak ada error**

```
cd frontend && npx tsc --noEmit
```

- [ ] **Step 15: Commit**

```
git add frontend/app/api/assignments frontend/app/api/reviewer-assignments frontend/app/api/faculties frontend/app/api/reviewers frontend/app/api/review-periods frontend/app/api/pkm
git commit -m "fix(frontend): standard proxy routes pakai proxyToBackend, handle error 503"
```

---

## Task 4: Update projects routes (hapus local BACKEND_URL)

**Files:** 5 file projects yang memakai `const BACKEND_URL = ...` lokal

**Konteks:** Rute projects memakai `const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:4000"` secara lokal — berbeda dengan `getBackendBaseUrl()` yang default-nya `http://127.0.0.1:4000`. Semua harus dikonsistensikan ke `getBackendBaseUrl()` via `proxyToBackend`.

- [ ] **Step 1: Update `frontend/app/api/projects/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

export async function GET() {
  return proxyToBackend("/api/projects", {
    method: "GET",
  })
}

export async function POST(request: Request) {
  const formData = await request.formData()
  return proxyToBackend("/api/projects", {
    method: "POST",
    body: formData,
  })
}

export async function PUT(request: Request) {
  const contentType = request.headers.get("content-type") ?? ""
  let formData: FormData

  if (contentType.includes("multipart/form-data")) {
    formData = await request.formData()
  } else {
    const payload = await request.json()
    formData = new FormData()
    formData.append("skema", payload.skema ?? "")
    formData.append("tahun", payload.tahun ?? "")
    formData.append("file_name", payload.file_name ?? payload.fileName ?? "")
  }

  return proxyToBackend("/api/projects/upload-url", {
    method: "POST",
    body: formData,
  })
}
```

- [ ] **Step 2: Update `frontend/app/api/projects/[id]/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

type RouteContext = {
  params: Promise<{ id: string }>
}

export async function GET(_request: Request, context: RouteContext) {
  const { id } = await context.params
  return proxyToBackend(`/api/projects/${id}`, {
    method: "GET",
  })
}

export async function DELETE(_request: Request, context: RouteContext) {
  const { id } = await context.params
  return proxyToBackend(`/api/projects/${id}`, {
    method: "DELETE",
  })
}
```

- [ ] **Step 3: Update `frontend/app/api/projects/[id]/generate/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

type RouteContext = {
  params: Promise<{ id: string }>
}

export async function POST(_request: Request, context: RouteContext) {
  const { id } = await context.params
  return proxyToBackend(`/api/projects/${id}/generate`, {
    method: "POST",
  })
}
```

- [ ] **Step 4: Update `frontend/app/api/projects/[id]/placeholders/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

type RouteContext = {
  params: Promise<{ id: string }>
}

export async function GET(_req: Request, context: RouteContext) {
  const { id } = await context.params
  return proxyToBackend(`/api/projects/${id}/placeholders`, {
    method: "GET",
  })
}
```

- [ ] **Step 5: Update `frontend/app/api/projects/confirm-upload/route.ts`**

```typescript
import { proxyToBackend } from "@/lib/backend-api"

export async function POST(request: Request) {
  const formData = await request.formData()
  return proxyToBackend("/api/projects/confirm-upload", {
    method: "POST",
    body: formData,
  })
}
```

- [ ] **Step 6: Pastikan TypeScript tidak ada error**

```
cd frontend && npx tsc --noEmit
```

- [ ] **Step 7: Commit**

```
git add frontend/app/api/projects/route.ts "frontend/app/api/projects/[id]/route.ts" "frontend/app/api/projects/[id]/generate/route.ts" "frontend/app/api/projects/[id]/placeholders/route.ts" frontend/app/api/projects/confirm-upload/route.ts
git commit -m "fix(frontend): projects routes pakai proxyToBackend, hapus inkonsistensi BACKEND_URL lokal"
```

---

## Task 5: Update projects logs route (SSE streaming — try/catch manual)

**Files:**
- Modify: `frontend/app/api/projects/[id]/logs/route.ts`

**Konteks:** Route ini memiliki dua code path: JSON snapshot dan SSE streaming. Path SSE tidak bisa menggunakan `proxyToBackend` karena response body perlu di-stream, bukan dibaca sebagai text. Try/catch ditambahkan manual di kedua path.

- [ ] **Step 1: Update `frontend/app/api/projects/[id]/logs/route.ts`**

```typescript
import { NextResponse } from "next/server"
import { getBackendBaseUrl } from "@/lib/backend-api"

type RouteContext = {
  params: Promise<{ id: string }>
}

export async function GET(request: Request, context: RouteContext) {
  const { id } = await context.params
  const acceptsSSE = request.headers.get("accept")?.includes("text/event-stream")
  const sinceId = new URL(request.url).searchParams.get("since_id") || "0"
  const sinceParam = sinceId !== "0" ? `?since_id=${sinceId}` : ""
  const backendUrl = getBackendBaseUrl()

  if (!acceptsSSE) {
    try {
      const response = await fetch(`${backendUrl}/api/projects/${id}/logs${sinceParam}`, {
        headers: { accept: "application/json" },
        cache: "no-store",
      })
      const data = await response.json()
      return NextResponse.json(data, { status: response.status })
    } catch {
      return NextResponse.json(
        { error: "Tidak dapat menjangkau server backend." },
        { status: 503 }
      )
    }
  }

  try {
    const response = await fetch(`${backendUrl}/api/projects/${id}/logs${sinceParam}`, {
      headers: {
        accept: "text/event-stream",
        "cache-control": "no-cache",
      },
    })

    if (!response.ok) {
      return new NextResponse("Failed to connect to log stream", { status: 502 })
    }

    const stream = response.body
    if (!stream) {
      return new NextResponse("No stream available", { status: 500 })
    }

    return new NextResponse(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
      },
    })
  } catch {
    return NextResponse.json(
      { error: "Tidak dapat menjangkau server backend." },
      { status: 503 }
    )
  }
}
```

- [ ] **Step 2: Pastikan TypeScript tidak ada error**

```
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```
git add "frontend/app/api/projects/[id]/logs/route.ts"
git commit -m "fix(frontend): logs route tambah try/catch untuk JSON dan SSE path"
```

---

## Task 6: Backend — ubah authClient menjadi singleton (Root Cause C)

**Files:**
- Modify: `backend/src/config/supabase.js`
- Modify: `backend/src/services/auth.service.js`
- Modify: `backend/src/server.js`

**Konteks:** `createAuthClient()` sekarang adalah factory yang membuat instance baru setiap dipanggil. Di `auth.service.js`, instance baru dibuat pada setiap request login. Di `server.js`, instance warmup langsung di-discard setelah warmup selesai. Dengan mengekspor singleton `authClient`, instance yang sama digunakan oleh warmup dan setiap request login — mengurangi overhead inisialisasi dan memastikan connection pool yang sama digunakan.

- [ ] **Step 1: Update `backend/src/config/supabase.js`**

Ganti `createAuthClient` factory dengan exported singleton `authClient`:

```javascript
import { createClient } from "@supabase/supabase-js"
import ws from "ws"
import { env } from "./env.js"

export const authClient = createClient(env.SUPABASE_URL, env.SUPABASE_ANON_KEY, {
  auth: {
    autoRefreshToken: false,
    persistSession: false,
  },
  realtime: {
    transport: ws,
  },
})

export const adminClient = createClient(env.SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY, {
  auth: {
    autoRefreshToken: false,
    persistSession: false,
  },
  realtime: {
    transport: ws,
  },
})
```

- [ ] **Step 2: Update `backend/src/services/auth.service.js`**

Ganti `import { createAuthClient }` dengan `import { authClient }`, dan hapus pembuatan instance per-call:

```javascript
import { authClient } from "../config/supabase.js"
import { ROLE_ROUTES, VALID_ROLES } from "../constants/roles.js"
import { AppError } from "../utils/app-error.js"
import { getProfileByUserId } from "./profile.service.js"
import { getReviewerAccessByUserId } from "./reviewer.service.js"
import { createSessionToken } from "./session.service.js"

export async function loginWithPassword({ email, password, role }) {
  if (!email || !password || !role) {
    throw new AppError("Semua field wajib diisi.", 400)
  }

  if (!VALID_ROLES.includes(role)) {
    throw new AppError("Role yang dipilih tidak valid.", 400)
  }

  const { data, error } = await authClient.auth.signInWithPassword({
    email,
    password,
  })

  if (error || !data.user) {
    throw new AppError("Password Anda salah.", 401)
  }

  const profile = await getProfileByUserId(data.user.id)

  if (profile.role !== role) {
    throw new AppError(
      `Akun ini terdaftar sebagai ${profile.role}, bukan ${role}. Pilih role yang sesuai.`,
      403
    )
  }

  if (profile.role === "reviewer") {
    await getReviewerAccessByUserId(data.user.id)
  }

  const destination = ROLE_ROUTES[profile.role]
  if (!destination) {
    throw new AppError("Role tidak dikenal. Hubungi administrator.", 500)
  }

  const sessionToken = createSessionToken({
    userId: data.user.id,
    email: data.user.email ?? "",
    role: profile.role,
  })

  return {
    sessionToken,
    destination,
    user: {
      id: data.user.id,
      email: data.user.email ?? "",
      role: profile.role,
    },
  }
}
```

- [ ] **Step 3: Update `backend/src/server.js`**

Ganti import `createAuthClient` dengan `authClient`:

```javascript
import app from "./app.js"
import { env } from "./config/env.js"
import { adminClient, authClient } from "./config/supabase.js"

app.listen(env.PORT, async () => {
  console.log(`Backend server listening on http://127.0.0.1:${env.PORT}`)

  // Warm up PostgREST connection (database queries)
  try {
    await adminClient.from("profiles").select("id").limit(1)
    console.log("Supabase PostgREST connection warmed up.")
  } catch (err) {
    console.warn("Supabase PostgREST warmup failed (non-fatal):", err.message)
  }

  // Warm up auth API connection — login menggunakan endpoint /auth/v1/ yang berbeda
  // dari PostgREST, sehingga perlu warmup terpisah agar tidak ECONNRESET pada login pertama
  try {
    await authClient.auth.getSession()
    console.log("Supabase auth connection warmed up.")
  } catch (err) {
    console.warn("Supabase auth warmup failed (non-fatal):", err.message)
  }
})
```

- [ ] **Step 4: Restart backend, pastikan startup messages masih muncul**

```
cd backend && npm run dev
```

Expected output:
```
Backend server listening on http://127.0.0.1:4000
Supabase PostgREST connection warmed up.
Supabase auth connection warmed up.
```

- [ ] **Step 5: Test manual — login berhasil**

Dengan backend running, lakukan login → harus berhasil seperti biasa.

- [ ] **Step 6: Commit**

```
git add backend/src/config/supabase.js backend/src/services/auth.service.js backend/src/server.js
git commit -m "fix(backend): authClient singleton menggantikan createAuthClient factory, kurangi overhead inisialisasi per-login"
```
