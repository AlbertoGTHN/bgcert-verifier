"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  ArrowLeft, RefreshCw, ExternalLink, Shield, AlertTriangle,
  CheckCircle, XCircle, Globe, FileText, User, Calendar,
  Hash, Building, Clock, Download, ChevronDown, ChevronUp, Image as ImageIcon,
} from "lucide-react";
import { cn, formatDateTime, formatFileSize, formatConfidence, formatDate, formatCountry } from "@/lib/utils";
import { StatusBadge } from "./StatusBadge";
import api from "@/lib/api";
import type { Certificate } from "@/lib/types";

export function CertificateDetail({ certId }: { certId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [showRawOcr, setShowRawOcr] = useState(false);
  const [showFraud, setShowFraud] = useState(false);
  const [notes, setNotes] = useState("");
  const [editingNotes, setEditingNotes] = useState(false);
  const [screenshotOpen, setScreenshotOpen] = useState(false);

  const { data: cert, isLoading } = useQuery({
    queryKey: ["certificate", certId],
    queryFn: () => api.getCertificate(certId),
    onSuccess: (data: Certificate) => {
      setNotes(data.analyst_notes || "");
    },
    refetchInterval: (data: Certificate | undefined) =>
      data?.status === "processing" || data?.status === "pending" ? 3000 : false,
  });

  const updateMutation = useMutation({
    mutationFn: (updates: { analyst_notes?: string }) => api.updateCertificate(certId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["certificate", certId] });
      toast.success("Notes saved");
      setEditingNotes(false);
    },
  });

  const reprocessMutation = useMutation({
    mutationFn: () => api.reprocessCertificate(certId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["certificate", certId] });
      toast.success("Reprocessing started");
    },
    onError: () => toast.error("Reprocess failed"),
  });

  if (isLoading) {
    return (
      <div className="space-y-4 animate-pulse">
        {[1, 2, 3].map((i) => (
          <div key={i} className="card p-6">
            <div className="h-5 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-4" />
            <div className="space-y-2">
              {Array(4).fill(0).map((_, j) => (
                <div key={j} className="h-4 bg-gray-200 dark:bg-gray-700 rounded" />
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!cert) return <div className="text-center py-12 text-gray-400">Certificate not found</div>;

  const screenshotSrc = cert.screenshot_url
    ? cert.screenshot_url.startsWith("http")
      ? cert.screenshot_url
      : cert.screenshot_url  // relative URL — served via Next.js /screenshots proxy
    : null;

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      {/* Back + Actions */}
      <div className="flex items-center justify-between">
        <button onClick={() => router.back()} className="btn-secondary gap-2">
          <ArrowLeft size={15} />
          Back
        </button>
        <div className="flex gap-2">
          <button
            onClick={() => reprocessMutation.mutate()}
            disabled={reprocessMutation.isPending || cert.status === "processing"}
            className="btn-secondary gap-2"
          >
            <RefreshCw size={15} className={cn(reprocessMutation.isPending && "animate-spin")} />
            Re-verify
          </button>
        </div>
      </div>

      {/* Status Banner */}
      <StatusBanner cert={cert} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left: Certificate Info */}
        <div className="lg:col-span-2 space-y-5">
          {/* Document Info */}
          <div className="card p-5">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <FileText size={16} className="text-brand-600" />
              Document Information
            </h3>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
              <InfoRow label="File Name" value={cert.original_filename} mono />
              <InfoRow label="File Size" value={formatFileSize(cert.file_size)} />
              <InfoRow label="Pages" value={cert.page_count || "—"} />
              <InfoRow label="Certificate Type" value={cert.cert_type?.replace(/_/g, " ")} capitalize />
              <InfoRow label="Country" value={cert.country ? formatCountry(cert.country) : null} />
              <InfoRow label="Language" value={cert.language_detected?.toUpperCase()} />
              <InfoRow label="Issuing Authority" value={cert.issuing_authority} colSpan />
            </dl>
          </div>

          {/* Person Info */}
          <div className="card p-5">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <User size={16} className="text-brand-600" />
              Certificate Holder
            </h3>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
              <InfoRow label="Full Name" value={cert.holder_name} />
              <InfoRow label="ID / Document #" value={cert.holder_id} mono />
              <InfoRow label="Certificate Number" value={cert.cert_number} mono />
              <InfoRow label="Issue Date" value={cert.issue_date} />
              <InfoRow label="Expiry Date" value={cert.expiry_date} />
            </dl>
          </div>

          {/* QR + Verification */}
          <div className="card p-5">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <Globe size={16} className="text-brand-600" />
              QR Code & Verification
            </h3>
            <dl className="grid grid-cols-1 gap-y-3">
              <InfoRow label="QR Code Found" value={cert.qr_code_found ? "Yes" : "No"} />
              {cert.qr_url && (
                <div>
                  <dt className="text-xs text-gray-500 dark:text-gray-400 mb-1">QR URL</dt>
                  <a
                    href={cert.qr_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-mono text-brand-600 hover:text-brand-800 break-all flex items-center gap-1"
                  >
                    {cert.qr_url}
                    <ExternalLink size={11} className="flex-shrink-0" />
                  </a>
                </div>
              )}
              {cert.verification_domain && (
                <InfoRow
                  label="Verification Domain"
                  value={
                    <span className={cn(
                      "flex items-center gap-1",
                      cert.is_official_domain ? "text-green-600" : "text-yellow-600"
                    )}>
                      {cert.is_official_domain ? <CheckCircle size={12} /> : <AlertTriangle size={12} />}
                      {cert.verification_domain}
                      {cert.is_official_domain && " (Official)"}
                    </span>
                  }
                />
              )}
              {cert.validation_result && (
                <div>
                  <dt className="text-xs text-gray-500 dark:text-gray-400 mb-1">Validation Summary</dt>
                  <dd className="text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                    {cert.validation_result}
                  </dd>
                </div>
              )}
              {cert.error_details && (
                <div>
                  <dt className="text-xs text-gray-500 dark:text-gray-400 mb-1">Error Details</dt>
                  <dd className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/10 rounded-lg p-3 font-mono">
                    [{cert.error_code}] {cert.error_details}
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Fraud Analysis */}
          {cert.fraud_score > 0 && (
            <div className="card p-5">
              <button
                className="flex items-center justify-between w-full"
                onClick={() => setShowFraud(!showFraud)}
              >
                <h3 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <Shield size={16} className={cert.is_potentially_fraudulent ? "text-red-500" : "text-green-500"} />
                  Fraud Detection
                  {cert.is_potentially_fraudulent && (
                    <span className="badge-failed ml-2">⚠ Suspicious</span>
                  )}
                </h3>
                {showFraud ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>

              {showFraud && (
                <div className="mt-4 space-y-3 animate-fade-in">
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-gray-600 dark:text-gray-400">Fraud Score:</span>
                    <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all",
                          cert.fraud_score < 0.3 ? "bg-green-500" :
                          cert.fraud_score < 0.6 ? "bg-yellow-500" : "bg-red-500"
                        )}
                        style={{ width: `${cert.fraud_score * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-semibold">
                      {Math.round(cert.fraud_score * 100)}%
                    </span>
                  </div>

                  {cert.fraud_indicators && (
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {Object.entries(cert.fraud_indicators)
                        .filter(([k]) => !["details", "error"].includes(k))
                        .map(([category, data]) => (
                          <div key={category} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                            <div className="font-medium text-gray-700 dark:text-gray-300 capitalize mb-1">
                              {category.replace(/_/g, " ")}
                            </div>
                            {typeof data === "object" && data !== null && (
                              <div className="text-gray-500">
                                {(data as Record<string, unknown>).tampered === true && <span className="text-red-500">⚠ Tampered</span>}
                                {(data as Record<string, unknown>).inconsistent === true && <span className="text-yellow-500">⚠ Inconsistent</span>}
                                {(data as Record<string, unknown>).detected === true && <span className="text-red-500">⚠ Detected</span>}
                                {(data as Record<string, unknown>).tampered === false && <span className="text-green-500">✓ Clean</span>}
                              </div>
                            )}
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Analyst Notes */}
          <div className="card p-5">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
              <FileText size={16} className="text-brand-600" />
              Analyst Notes
            </h3>
            {editingNotes ? (
              <div className="space-y-2">
                <textarea
                  className="input h-24 resize-none"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Add review notes, observations, or decisions..."
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => updateMutation.mutate({ analyst_notes: notes })}
                    className="btn-primary py-1.5 text-xs"
                    disabled={updateMutation.isPending}
                  >
                    Save Notes
                  </button>
                  <button
                    onClick={() => { setEditingNotes(false); setNotes(cert.analyst_notes || ""); }}
                    className="btn-secondary py-1.5 text-xs"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div
                className="text-sm text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 rounded-lg p-3 min-h-16 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                onClick={() => setEditingNotes(true)}
              >
                {cert.analyst_notes || <span className="text-gray-300 dark:text-gray-600">Click to add analyst notes...</span>}
              </div>
            )}
          </div>
        </div>

        {/* Right: Metadata */}
        <div className="space-y-5">
          {/* Timing */}
          <div className="card p-5">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <Clock size={16} className="text-brand-600" />
              Processing Info
            </h3>
            <dl className="space-y-3">
              <InfoRow label="Uploaded" value={formatDateTime(cert.uploaded_at)} />
              <InfoRow label="Processed" value={cert.processed_at ? formatDateTime(cert.processed_at) : "Pending"} />
              <InfoRow
                label="Processing Time"
                value={cert.processing_time_seconds ? `${cert.processing_time_seconds.toFixed(1)}s` : "—"}
              />
              <InfoRow label="Uploaded by" value={cert.uploader_name} />
              <InfoRow label="OCR Confidence" value={cert.ocr_confidence ? `${Math.round(cert.ocr_confidence * 100)}%` : "—"} />
            </dl>
          </div>

          {/* Screenshot */}
          {screenshotSrc && (
            <div className="card p-5">
              <h3 className="font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                <ImageIcon size={16} className="text-brand-600" />
                Verification Screenshot
              </h3>
              <div
                className="cursor-pointer rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 hover:border-brand-400 transition-colors"
                onClick={() => setScreenshotOpen(true)}
              >
                <img
                  src={screenshotSrc}
                  alt="Verification page screenshot"
                  className="w-full object-cover max-h-48"
                />
              </div>
              <div className="flex gap-2 mt-3">
                <a
                  href={screenshotSrc}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary py-1.5 text-xs gap-1.5 flex-1 justify-center"
                >
                  <ExternalLink size={12} /> View Full
                </a>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Fullscreen screenshot */}
      {screenshotOpen && screenshotSrc && (
        <div
          className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setScreenshotOpen(false)}
        >
          <img
            src={screenshotSrc}
            alt="Screenshot"
            className="max-w-full max-h-full rounded-xl shadow-2xl"
          />
        </div>
      )}
    </div>
  );
}

function StatusBanner({ cert }: { cert: Certificate }) {
  const statusBg = {
    verified_authentic: "bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800",
    failed_fraudulent: "bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800",
    technical_issue: "bg-yellow-50 dark:bg-yellow-900/10 border-yellow-200 dark:border-yellow-800",
    pending: "bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700",
    processing: "bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800",
    error: "bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800",
  };

  return (
    <div className={cn("card p-5 border", statusBg[cert.status])}>
      <div className="flex items-start gap-4">
        <StatusBadge status={cert.status} size="lg" />
        <div className="flex-1">
          <div className="font-semibold text-gray-900 dark:text-white text-lg">
            {cert.original_filename}
          </div>
          {cert.validation_result && (
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              {cert.validation_result}
            </p>
          )}
        </div>
        {cert.confidence_score > 0 && (
          <div className="text-right flex-shrink-0">
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {Math.round(cert.confidence_score * 100)}%
            </div>
            <div className="text-xs text-gray-500">Confidence</div>
          </div>
        )}
      </div>
    </div>
  );
}

function InfoRow({
  label,
  value,
  mono = false,
  capitalize = false,
  colSpan = false,
}: {
  label: string;
  value?: string | number | React.ReactNode | null;
  mono?: boolean;
  capitalize?: boolean;
  colSpan?: boolean;
}) {
  return (
    <div className={colSpan ? "col-span-2" : ""}>
      <dt className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">{label}</dt>
      <dd className={cn(
        "text-sm text-gray-800 dark:text-gray-200",
        mono && "font-mono",
        capitalize && "capitalize",
        !value && "text-gray-300 dark:text-gray-600"
      )}>
        {value ?? "—"}
      </dd>
    </div>
  );
}
