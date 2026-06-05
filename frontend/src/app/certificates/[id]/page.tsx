"use client";

import { AppLayout } from "@/components/layout/AppLayout";
import { CertificateDetail } from "@/components/certificates/CertificateDetail";

export default function CertificateDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return (
    <AppLayout
      title="Certificate Detail"
      subtitle="Full verification results and document analysis"
    >
      <CertificateDetail certId={params.id} />
    </AppLayout>
  );
}
