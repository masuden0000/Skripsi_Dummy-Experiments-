"use server"

import { createClient } from "@/lib/supabase/server"
import { redirect } from "next/navigation"

type LoginResult = { error: string } | undefined

export async function login(formData: FormData): Promise<LoginResult> {
  const email    = formData.get("email")    as string
  const password = formData.get("password") as string
  const role     = formData.get("role")     as string

  if (!email || !password || !role) {
    return { error: "Semua field wajib diisi." }
  }

  const supabase = await createClient()

  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  })

  if (error) {
    return { error: "Email atau password salah. Periksa kembali." }
  }

  const userRole = data.user.user_metadata?.role as string | undefined

  if (!userRole) {
    return { error: "Akun ini belum memiliki role yang ditetapkan." }
  }

  if (userRole !== role) {
    return {
      error: `Akun ini tidak memiliki akses sebagai ${
        role === "admin" ? "Admin" : "Reviewer"
      }.`,
    }
  }

  redirect(role === "admin" ? "/admin" : "/reviewer")
}
