import { createServerClient } from "@supabase/ssr"
import { NextResponse, type NextRequest } from "next/server"

export async function proxy(request: NextRequest) {
  const response = NextResponse.next({ request })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          )
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  const {
    data: { user },
  } = await supabase.auth.getUser()

  const { pathname } = request.nextUrl

  // User sudah login dan buka /login → redirect ke dashboard sesuai role
  if (pathname === "/login" && user) {
    const role = user.user_metadata?.role as string | undefined
    const dest = role === "admin" ? "/admin" : "/reviewer"
    return NextResponse.redirect(new URL(dest, request.url))
  }

  // /admin hanya untuk role admin
  if (pathname.startsWith("/admin")) {
    if (!user) {
      return NextResponse.redirect(new URL("/login", request.url))
    }
    if (user.user_metadata?.role !== "admin") {
      return NextResponse.redirect(new URL("/login", request.url))
    }
  }

  // /reviewer hanya untuk role reviewer
  if (pathname.startsWith("/reviewer")) {
    if (!user) {
      return NextResponse.redirect(new URL("/login", request.url))
    }
    if (user.user_metadata?.role !== "reviewer") {
      return NextResponse.redirect(new URL("/login", request.url))
    }
  }

  return response
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
}
