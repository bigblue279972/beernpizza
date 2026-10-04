import { listResearchLinks } from "@/lib/actions/research";
import { getSports } from "@/lib/actions/sports";
import { ResearchPageClient } from "./ResearchPageClient";

export default async function ResearchPage() {
  const [links, sports] = await Promise.all([
    listResearchLinks(),
    getSports(),
  ]);

  return <ResearchPageClient links={links} sports={sports} />;
}
