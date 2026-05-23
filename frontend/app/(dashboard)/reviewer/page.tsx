"use client"

import { AssignmentsList } from "@/components/reviewer/AssignmentsList"
import { ReviewerPageHeader } from "@/components/reviewer/shared"

export default function ReviewerAssignmentsPage() {
  return (
    <div className="px-8 py-8">
      <ReviewerPageHeader
        title="Daftar Penugasan"
        description="Daftar periode review yang telah ditugaskan kepada Anda"
      />
      <AssignmentsList />
    </div>
  )
}
