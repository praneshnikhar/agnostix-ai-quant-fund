import { ProviderDetail } from "@/components/providers/provider-detail";

export default function ProviderDetailPage({ params }: { params: { provider: string } }) {
  return <ProviderDetail providerId={params.provider} />;
}
