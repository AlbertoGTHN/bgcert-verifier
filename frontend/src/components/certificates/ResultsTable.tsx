"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  Search, Filter, RefreshCw, Trash2, Eye, MoreHorizontal,
  ChevronLeft, ChevronRight, Download, ExternalLink,
} from "lucide-react";
import { cn, formatDate, formatFileSize, formatConfidence, truncate, formatCountry } from "@/lib/utils";
import { StatusBadge } from "./StatusBadge";
import api from "@/lib/api";
import type { Certificate, ValidationStatus, FilterState } from "@/lib/types";

const STATUS_FILTER_OPTIONS: { value: ValidationStatus | ""; label: string }[] = [
  { value: "", label: "All Statuses" },
  { value: "verified_authentic", label: "✓ Verified Authentic" },
  { value: "verified_internal", label: "◈ Internal Analysis" },
  { value: "failed_fraudulent", label: "✗ Failed / Fraudulent" },
  { value: "technical_issue", label: "⚠ Technical Issue" },
  { value: "pending", label: "⏳ Pending" },
  { value: "processing", label: "🔄 Processing" },
  { value: "error", label: "💥 Error" },
];

export function ResultsTable() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [filters, setFilters] = useState<FilterState>({ page: 1, size: 20 });
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["certificates", filters],
    queryFn: () => api.getCertificates(filters),
    refetchInterval: 8000,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteCertificate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["certificates"] });
      queryClient.invalidateQueries({ queryKey: ["summary"] });
      toast.success("Certificate deleted");
    },
    onError: () => toast.error("Delete failed"),
  });

  const handleSearch = (val: string) => {
    setSearch(val);
    setFilters((f) => ({ ...f, search: val || undefined, page: 1 }));
  };

  const handleStatusFilter = (val: string) => {
    setFilters((f) => ({ ...f, status: (val || undefined) as ValidationStatus | undefined, page: 1 }));
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (data?.items) setSelected(new Set(data.items.map((c) => c.id)));
  };

  const clearSelection = () => setSelected(new Set());

  const exportSelected = async (format: "pdf" | "excel" | "csv") => {
    const ids = selected.size > 0 ? Array.from(selected).join(",") : undefined;
    await api.downloadReport(format, ids ? { cert_ids: ids } : {});
    toast.success(`Exporting ${format.toUpperCase()} report...`);
  };

  const certificates = data?.items || [];
  const total = data?.total || 0;
  const pages = data?.pages || 0;

  return (
    <div className="card">
      {/* Toolbar */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-800 flex flex-wrap gap-3 items-center">
        {/* Search */}
        <div className="relative flex-1 min-w-48">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name, cert #, country..."
            className="input pl-9"
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
          />
        </div>

        {/* Status filter */}
        <select
          className="input w-auto min-w-44"
          onChange={(e) => handleStatusFilter(e.target.value)}
        >
          {STATUS_FILTER_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        {/* Country filter */}
        <input
          type="text"
          placeholder="Filter by country"
          className="input w-40"
          onChange={(e) => setFilters((f) => ({ ...f, country: e.target.value || undefined, page: 1 }))}
        />

        <button
          onClick={() => refetch()}
          className="btn-secondary p-2"
          title="Refresh"
        >
          <RefreshCw size={15} />
        </button>

        {selected.size > 0 && (
          <div className="flex items-center gap-2 border-l border-gray-200 dark:border-gray-700 pl-3">
            <span className="text-xs text-gray-500">{selected.size} selected</span>
            <button onClick={() => exportSelected("pdf")} className="btn-secondary py-1.5 text-xs">PDF</button>
            <button onClick={() => exportSelected("excel")} className="btn-secondary py-1.5 text-xs">Excel</button>
            <button onClick={() => exportSelected("csv")} className="btn-secondary py-1.5 text-xs">CSV</button>
            <button onClick={clearSelection} className="text-xs text-gray-400 hover:text-gray-600">Clear</button>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-800/50">
              <th className="table-header w-10">
                <input
                  type="checkbox"
                  onChange={(e) => e.target.checked ? selectAll() : clearSelection()}
                  className="rounded border-gray-300"
                />
              </th>
              <th className="table-header">File / Holder</th>
              <th className="table-header">Country</th>
              <th className="table-header">Cert #</th>
              <th className="table-header">Status</th>
              <th className="table-header">Confidence</th>
              <th className="table-header">QR Code</th>
              <th className="table-header">Uploaded</th>
              <th className="table-header">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {isLoading ? (
              Array(5).fill(0).map((_, i) => (
                <tr key={i} className="animate-pulse">
                  {Array(9).fill(0).map((_, j) => (
                    <td key={j} className="table-cell">
                      <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-full" />
                    </td>
                  ))}
                </tr>
              ))
            ) : certificates.length === 0 ? (
              <tr>
                <td colSpan={9} className="text-center py-12">
                  <div className="text-gray-400 dark:text-gray-500">
                    <div className="text-4xl mb-2">📋</div>
                    <div className="font-medium">No certificates found</div>
                    <div className="text-sm mt-1">Upload PDF certificates to get started</div>
                  </div>
                </td>
              </tr>
            ) : (
              certificates.map((cert) => (
                <CertRow
                  key={cert.id}
                  cert={cert}
                  selected={selected.has(cert.id)}
                  onSelect={() => toggleSelect(cert.id)}
                  onView={() => router.push(`/certificates/${cert.id}`)}
                  onDelete={() => {
                    if (confirm("Delete this certificate?")) {
                      deleteMutation.mutate(cert.id);
                    }
                  }}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="p-4 border-t border-gray-200 dark:border-gray-800 flex items-center justify-between">
          <span className="text-xs text-gray-500">
            {total} total • Page {filters.page} of {pages}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setFilters((f) => ({ ...f, page: Math.max(1, f.page - 1) }))}
              disabled={filters.page <= 1}
              className="btn-secondary p-1.5 disabled:opacity-40"
            >
              <ChevronLeft size={15} />
            </button>
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-8 text-center">
              {filters.page}
            </span>
            <button
              onClick={() => setFilters((f) => ({ ...f, page: Math.min(pages, f.page + 1) }))}
              disabled={filters.page >= pages}
              className="btn-secondary p-1.5 disabled:opacity-40"
            >
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function CertRow({
  cert,
  selected,
  onSelect,
  onView,
  onDelete,
}: {
  cert: Certificate;
  selected: boolean;
  onSelect: () => void;
  onView: () => void;
  onDelete: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const confidencePct = Math.round(cert.confidence_score * 100);

  const confidenceColor =
    confidencePct >= 80 ? "text-green-600 dark:text-green-400" :
    confidencePct >= 50 ? "text-yellow-600 dark:text-yellow-400" :
    "text-red-600 dark:text-red-400";

  return (
    <tr
      className={cn(
        "hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors cursor-pointer",
        selected && "bg-brand-50 dark:bg-brand-900/10"
      )}
      onClick={onView}
    >
      <td className="table-cell" onClick={(e) => e.stopPropagation()}>
        <input
          type="checkbox"
          checked={selected}
          onChange={onSelect}
          className="rounded border-gray-300"
        />
      </td>

      <td className="table-cell">
        <div className="font-medium text-gray-900 dark:text-white text-xs truncate max-w-48">
          {cert.original_filename}
        </div>
        {cert.holder_name && (
          <div className="text-xs text-gray-400 mt-0.5">{cert.holder_name}</div>
        )}
        <div className="text-xs text-gray-300 dark:text-gray-600 mt-0.5">
          {formatFileSize(cert.file_size)}
        </div>
      </td>

      <td className="table-cell">
        <div className="text-xs">
          {cert.country
            ? <span title={cert.country}>{formatCountry(cert.country)}</span>
            : <span className="text-gray-300">Unknown</span>
          }
        </div>
        {cert.language_detected && (
          <div className="text-xs text-gray-400 uppercase">{cert.language_detected}</div>
        )}
      </td>

      <td className="table-cell">
        <span className="text-xs font-mono">
          {cert.cert_number || <span className="text-gray-300">—</span>}
        </span>
      </td>

      <td className="table-cell">
        <StatusBadge status={cert.status} size="sm" />
        {cert.is_potentially_fraudulent && (
          <div className="text-xs text-red-500 mt-1">⚠ Fraud indicators</div>
        )}
      </td>

      <td className="table-cell">
        {cert.status !== "pending" && cert.status !== "processing" && (
          <div className={cn("text-sm font-semibold", confidenceColor)}>
            {confidencePct > 0 ? `${confidencePct}%` : "—"}
          </div>
        )}
      </td>

      <td className="table-cell">
        {cert.qr_code_found ? (
          <div className="flex items-center gap-1">
            <span className="text-green-500 text-xs">✓</span>
            {cert.qr_url && (
              <a
                href={cert.qr_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="text-xs text-brand-500 hover:text-brand-700 truncate max-w-24 block"
              >
                {new URL(cert.qr_url).hostname}
              </a>
            )}
          </div>
        ) : (
          <span className="text-xs text-gray-300">No QR</span>
        )}
      </td>

      <td className="table-cell">
        <div className="text-xs">{formatDate(cert.uploaded_at)}</div>
        {cert.uploader_name && (
          <div className="text-xs text-gray-400">{cert.uploader_name}</div>
        )}
      </td>

      <td className="table-cell" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-1 relative">
          <button
            onClick={onView}
            className="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-brand-50 dark:hover:bg-brand-900/20 rounded-lg transition-colors"
            title="View details"
          >
            <Eye size={14} />
          </button>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <MoreHorizontal size={14} />
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-8 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-10 min-w-36 py-1">
              <button
                onClick={() => { onView(); setMenuOpen(false); }}
                className="w-full text-left px-3 py-2 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2"
              >
                <Eye size={12} /> View Details
              </button>
              {cert.screenshot_url && (
                <a
                  href={cert.screenshot_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full text-left px-3 py-2 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2"
                  onClick={() => setMenuOpen(false)}
                >
                  <ExternalLink size={12} /> View Screenshot
                </a>
              )}
              <hr className="border-gray-100 dark:border-gray-700 my-1" />
              <button
                onClick={() => { onDelete(); setMenuOpen(false); }}
                className="w-full text-left px-3 py-2 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2"
              >
                <Trash2 size={12} /> Delete
              </button>
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}
