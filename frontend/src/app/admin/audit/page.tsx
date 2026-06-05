"use client";

import { useQuery } from "@tanstack/react-query";
import { AppLayout } from "@/components/layout/AppLayout";
import { formatDateTime } from "@/lib/utils";
import api from "@/lib/api";

export default function AuditLogsPage() {
  const { data: logs = [], isLoading } = useQuery({
    queryKey: ["audit-logs"],
    queryFn: () => api.getAuditLogs(200),
  });

  const ACTION_COLORS: Record<string, string> = {
    LOGIN_SUCCESS: "text-green-600 dark:text-green-400",
    LOGIN_FAILED: "text-red-600 dark:text-red-400",
    UPLOAD: "text-blue-600 dark:text-blue-400",
    DELETE: "text-red-600 dark:text-red-400",
    EXPORT: "text-purple-600 dark:text-purple-400",
  };

  return (
    <AppLayout title="Audit Logs" subtitle="Security and compliance audit trail">
      <div className="card overflow-hidden">
        <div className="p-4 border-b border-gray-200 dark:border-gray-800">
          <div className="text-sm text-gray-500">
            Showing {(logs as unknown[]).length} recent events
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="table-header">Action</th>
                <th className="table-header">User</th>
                <th className="table-header">Resource</th>
                <th className="table-header">IP Address</th>
                <th className="table-header">Status</th>
                <th className="table-header">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {isLoading ? (
                Array(8).fill(0).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    {Array(6).fill(0).map((_, j) => (
                      <td key={j} className="table-cell">
                        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : (logs as Record<string, string>[]).map((log) => (
                <tr key={log.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="table-cell">
                    <span className={`text-xs font-mono font-semibold ${ACTION_COLORS[log.action] || "text-gray-600 dark:text-gray-400"}`}>
                      {log.action}
                    </span>
                  </td>
                  <td className="table-cell text-xs">{log.user_id ? log.user_id.slice(0, 8) + "..." : "System"}</td>
                  <td className="table-cell text-xs">{log.resource_type || "—"}</td>
                  <td className="table-cell text-xs font-mono">{log.ip_address || "—"}</td>
                  <td className="table-cell">
                    <span className={`badge ${log.status === "success" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                      {log.status}
                    </span>
                  </td>
                  <td className="table-cell text-xs">{formatDateTime(log.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </AppLayout>
  );
}
