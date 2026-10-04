import { notFound } from "next/navigation"
import { STUDIES } from "@/lib/mock/studies"
import { Workspace } from "@/components/spark/workspace"

export function generateStaticParams() {
  return STUDIES.filter((s) => s.interactive).map((s) => ({ studyId: s.id }))
}

export default async function StudyPage({ params }: { params: Promise<{ studyId: string }> }) {
  const { studyId } = await params
  const study = STUDIES.find((s) => s.id === studyId && s.interactive)
  if (!study) notFound()
  return <Workspace study={study} />
}
