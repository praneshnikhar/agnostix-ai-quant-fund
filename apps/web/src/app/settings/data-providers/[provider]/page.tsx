import { DataProviderDetail } from "@/components/data-providers/data-provider-detail";

export default function Page({ params }: { params: { provider: string } }) {
  return <DataProviderDetail providerId={params.provider} />;
}

