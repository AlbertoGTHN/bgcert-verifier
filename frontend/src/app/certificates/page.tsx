"use client";

import { AppLayout } from "@/components/layout/AppLayout";
import { ResultsTable } from "@/components/certificates/ResultsTable";

export default function CertificatesPage() {
  return (
    <AppLayout
      title="Certificates"
      subtitle="Manage and review all submitted background check certificates"
    >
      <ResultsTable />
    </AppLayout>
  );
}
