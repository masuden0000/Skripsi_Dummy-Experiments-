"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

const navItems = [
  {
    label: "Daftar Penugasan",
    href: "/reviewer",
    exact: true,
    icon: (
      <svg className="size-4 flex-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
      </svg>
    ),
  },
  {
    label: "Validasi Dokumen",
    href: "/reviewer/validation",
    exact: false,
    icon: (
      <svg className="size-4 flex-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
]

export default function ReviewerNav() {
  const pathname = usePathname()

  return (
    <nav className="flex-1 px-3 py-4 space-y-0.5">
      <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-widest" style={{ color: "rgba(0,0,0,0.3)" }}>
        Menu
      </p>
      {navItems.map((item) => {
        const isActive = item.exact
          ? pathname === item.href
          : pathname.startsWith(item.href)

        return (
          <Link
            key={item.href}
            href={item.href}
            className={[
              "flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
              isActive
                ? "bg-pkm-50 text-pkm-700 ring-1 ring-pkm-100"
                : "text-gray-500 hover:bg-gray-50 hover:text-gray-700",
            ].join(" ")}
          >
            {item.icon}
            {item.label}
            {isActive && (
              <span className="ml-auto size-1.5 rounded-full bg-pkm-600" />
            )}
          </Link>
        )
      })}
    </nav>
  )
}