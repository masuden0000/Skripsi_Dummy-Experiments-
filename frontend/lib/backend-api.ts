import { NextResponse } from "next/server"

const DEFAULT_BACKEND_URL = "http://127.0.0.1:4000"

export function getBackendBaseUrl() {
  return process.env.NEXT_PUBLIC_BACKEND_URL || DEFAULT_BACKEND_URL
}

type ProxyOptions = Omit<RequestInit, "cache" | "headers"> & {
  headers?: Record<string, string>
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

  const headers: Record<string, string> = { ...(extraHeaders ?? {}) }
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
        "content-type": backendResponse.headers.get("content-type") ?? "application/octet-stream",
      },
    })

    if (forwardSetCookie) {
      for (const cookie of backendResponse.headers.getSetCookie()) {
        response.headers.append("set-cookie", cookie)
      }
    }

    return response
  } catch {
    return NextResponse.json(
      { error: "Tidak dapat menjangkau server backend." },
      { status: 503 }
    )
  }
}
