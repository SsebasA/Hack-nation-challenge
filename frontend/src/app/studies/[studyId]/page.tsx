import { STUDIES } from "@/lib/mock/studies"
import { StudyRoute } from "@/components/spark/study-route"

// The scripted study is prerendered; studies created through the API render on demand
// (dynamicParams stays on) and resolve their metadata in the browser.
export function generateStaticParams() {
  return STUDIES.filter((s) => s.interactive).map((s) => ({ studyId: s.id }))
}

export default async function StudyPage({ params }: { params: Promise<{ studyId: string }> }) {
  const { studyId } = await params
  return <StudyRoute studyId={studyId} />
}
