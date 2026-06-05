import { proxyToBackend } from "@/lib/backend-api"

export async function POST(request: Request) {
  const { project_id, file_name } = await request.json()
  const formData = new FormData()
  formData.append("project_id", project_id)
  formData.append("file_name", file_name)
  return proxyToBackend("/api/projects/confirm-upload", {
    method: "POST",
    body: formData,
  })
}
