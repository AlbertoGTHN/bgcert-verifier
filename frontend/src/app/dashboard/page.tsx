"use client";

import { AppLayout } from "@/components/layout/AppLayout";
import { StatsCards } from "@/components/dashboard/StatsCards";
import { UploadZone } from "@/components/dashboard/UploadZone";
import { ResultsTable } from "@/components/certificates/ResultsTable";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import type { ValidationSummary } from "@/lib/types";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";

const CHART_COLORS = {
  verified_authentic: "#16a34a",
  failed_fraudulent: "#dc2626",
  technical_issue: "#d97706",
  pending: "#6b7280",
  processing: "#2563eb",
};

function ValidationChart() {
  const { data } = useQuery<ValidationSummary>({
    queryKey: ["summary"],
    queryFn: () => api.getSummary(),
    refetchInterval: 15000,
  });

  if (!data || data.total === 0) return null;

  const chartData = [
    { name: "Verified", value: data.verified_authentic, key: "verified_authentic" },
    { name: "Failed", value: data.failed_fraudulent, key: "failed_fraudulent" },
    { name: "Technical", value: data.technical_issue, key: "technical_issue" },
    { name: "Pending", value: data.pending + data.processing, key: "pending" },
  ].filter((d) => d.value > 0);

  return (
    <div className="card p-5">
      <h3 className="font-semibold text-gray-900 dark:text-white mb-4">Validation Overview</h3>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={80}
            paddingAngle={3}
            dataKey="value"
          >
            {chartData.map((entry) => (
              <Cell
                key={entry.key}
                fill={CHART_COLORS[entry.key as keyof typeof CHART_COLORS]}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "0.5rem",
              color: "#f9fafb",
              fontSize: "12px",
            }}
          />
          <Legend iconSize={10} iconType="circle" wrapperStyle={{ fontSize: "12px" }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function CountriesPanel() {
  const { data } = useQuery<ValidationSummary>({
    queryKey: ["summary"],
    queryFn: () => api.getSummary(),
  });

  if (!data?.countries?.length) return null;

  return (
    <div className="card p-5">
      <h3 className="font-semibold text-gray-900 dark:text-white mb-3">Countries Detected</h3>
      <div className="flex flex-wrap gap-2">
        {data.countries.map((country) => (
          <span
            key={country}
            className="badge bg-brand-50 text-brand-700 dark:bg-brand-900/20 dark:text-brand-300 border border-brand-200 dark:border-brand-800"
          >
            🌍 {country}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <AppLayout
      title="Dashboard"
      subtitle="Certificate validation overview"
    >
      <div className="space-y-6">
        {/* Stats */}
        <StatsCards />

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Upload + Queue */}
          <div className="xl:col-span-2 space-y-5">
            <UploadZone />
          </div>

          {/* Charts */}
          <div className="space-y-5">
            <ValidationChart />
            <CountriesPanel />
          </div>
        </div>

        {/* Recent Certificates Table */}
        <div>
          <h2 className="text-base font-semibold text-gray-900 dark:text-white mb-3">
            Recent Certificates
          </h2>
          <ResultsTable />
        </div>
      </div>
    </AppLayout>
  );
}
