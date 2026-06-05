"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle, XCircle, AlertTriangle, Clock, FileText, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import api from "@/lib/api";
import type { ValidationSummary } from "@/lib/types";

interface StatCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  icon: React.ReactNode;
  colorClass: string;
  bgClass: string;
  trend?: string;
}

function StatCard({ title, value, subtitle, icon, colorClass, bgClass, trend }: StatCardProps) {
  return (
    <div className="card p-5 flex items-start gap-4 hover:shadow-md transition-shadow">
      <div className={cn("p-3 rounded-xl flex-shrink-0", bgClass)}>
        <span className={colorClass}>{icon}</span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-2xl font-bold text-gray-900 dark:text-white">{value}</div>
        <div className="text-sm font-medium text-gray-600 dark:text-gray-400 mt-0.5">{title}</div>
        {subtitle && (
          <div className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{subtitle}</div>
        )}
      </div>
      {trend && (
        <div className="text-xs text-green-500 font-medium">{trend}</div>
      )}
    </div>
  );
}

export function StatsCards() {
  const { data, isLoading } = useQuery<ValidationSummary>({
    queryKey: ["summary"],
    queryFn: () => api.getSummary(),
    refetchInterval: 10000,
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-7 gap-4">
        {Array(7).fill(0).map((_, i) => (
          <div key={i} className="card p-5 animate-pulse">
            <div className="flex gap-4">
              <div className="w-12 h-12 bg-gray-200 dark:bg-gray-700 rounded-xl" />
              <div className="flex-1 space-y-2">
                <div className="h-7 bg-gray-200 dark:bg-gray-700 rounded w-16" />
                <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-24" />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  const s = data || {
    total: 0, verified_authentic: 0, verified_internal: 0, failed_fraudulent: 0,
    technical_issue: 0, pending: 0, processing: 0, error: 0,
    avg_confidence: 0, countries: [],
  };

  const verifiedPct = s.total > 0
    ? Math.round(((s.verified_authentic + s.verified_internal) / s.total) * 100)
    : 0;

  const stats: StatCardProps[] = [
    {
      title: "Total Certificates",
      value: s.total,
      subtitle: `${s.countries.length} countries`,
      icon: <FileText size={20} />,
      colorClass: "text-blue-600 dark:text-blue-400",
      bgClass: "bg-blue-50 dark:bg-blue-900/20",
    },
    {
      title: "Verified Authentic",
      value: s.verified_authentic,
      subtitle: `${verifiedPct}% verified total`,
      icon: <CheckCircle size={20} />,
      colorClass: "text-green-600 dark:text-green-400",
      bgClass: "bg-green-50 dark:bg-green-900/20",
    },
    {
      title: "Internal Analysis",
      value: s.verified_internal,
      subtitle: "Approved offline",
      icon: <span className="text-lg leading-none">◈</span>,
      colorClass: "text-teal-600 dark:text-teal-400",
      bgClass: "bg-teal-50 dark:bg-teal-900/20",
    },
    {
      title: "Failed / Fraudulent",
      value: s.failed_fraudulent,
      subtitle: s.failed_fraudulent > 0 ? "Requires review" : "None detected",
      icon: <XCircle size={20} />,
      colorClass: "text-red-600 dark:text-red-400",
      bgClass: "bg-red-50 dark:bg-red-900/20",
    },
    {
      title: "Technical Issues",
      value: s.technical_issue,
      subtitle: "Cannot auto-verify",
      icon: <AlertTriangle size={20} />,
      colorClass: "text-yellow-600 dark:text-yellow-400",
      bgClass: "bg-yellow-50 dark:bg-yellow-900/20",
    },
    {
      title: "Pending / Processing",
      value: s.pending + s.processing,
      subtitle: s.processing > 0 ? `${s.processing} active` : "Queue empty",
      icon: <Clock size={20} />,
      colorClass: "text-purple-600 dark:text-purple-400",
      bgClass: "bg-purple-50 dark:bg-purple-900/20",
    },
    {
      title: "Avg Confidence",
      value: `${Math.round(s.avg_confidence * 100)}%`,
      subtitle: "Verification score",
      icon: <TrendingUp size={20} />,
      colorClass: "text-brand-600 dark:text-brand-400",
      bgClass: "bg-brand-50 dark:bg-brand-900/20",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-7 gap-4">
      {stats.map((stat) => (
        <StatCard key={stat.title} {...stat} />
      ))}
    </div>
  );
}
