"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Upload, File, X, CheckCircle, AlertCircle, Loader2, FileUp } from "lucide-react";
import { cn, formatFileSize } from "@/lib/utils";
import api from "@/lib/api";
import type { UploadProgress } from "@/lib/types";

export function UploadZone() {
  const queryClient = useQueryClient();
  const [uploads, setUploads] = useState<UploadProgress[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);

  const updateUpload = (filename: string, updates: Partial<UploadProgress>) => {
    setUploads((prev) =>
      prev.map((u) => (u.filename === filename ? { ...u, ...updates } : u))
    );
  };

  const processFiles = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    // Add to queue
    const newUploads: UploadProgress[] = acceptedFiles.map((f) => ({
      filename: f.name,
      progress: 0,
      status: "uploading" as const,
    }));
    setUploads((prev) => [...newUploads, ...prev]);

    const processFile = async (file: File) => {
      try {
        updateUpload(file.name, { status: "uploading", progress: 0 });

        const cert = await api.uploadSingle(file, (pct) => {
          updateUpload(file.name, { progress: pct });
        });

        updateUpload(file.name, {
          status: "queued",
          progress: 100,
          certId: cert.id,
        });

        // Poll for completion
        pollStatus(cert.id, file.name);

      } catch (err: unknown) {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        updateUpload(file.name, {
          status: "error",
          error: detail || "Upload failed",
        });
        toast.error(`Failed to upload ${file.name}`);
      }
    };

    // Process in parallel (max 3 at a time)
    const chunks = chunkArray(acceptedFiles, 3);
    for (const chunk of chunks) {
      await Promise.all(chunk.map(processFile));
    }

    // Refresh data
    queryClient.invalidateQueries({ queryKey: ["certificates"] });
    queryClient.invalidateQueries({ queryKey: ["summary"] });
  }, [queryClient]);

  const pollStatus = async (certId: string, filename: string) => {
    let attempts = 0;
    const maxAttempts = 60;

    const poll = async () => {
      if (attempts >= maxAttempts) {
        updateUpload(filename, { status: "error", error: "Processing timeout" });
        return;
      }
      attempts++;

      try {
        const cert = await api.getCertificate(certId);
        if (["verified_authentic", "failed_fraudulent", "technical_issue", "error"].includes(cert.status)) {
          updateUpload(filename, { status: "done" });
          queryClient.invalidateQueries({ queryKey: ["certificates"] });
          queryClient.invalidateQueries({ queryKey: ["summary"] });

          if (cert.status === "verified_authentic") {
            toast.success(`✓ ${filename}: Verified Authentic`);
          } else if (cert.status === "failed_fraudulent") {
            toast.error(`✗ ${filename}: Failed / Possible Fraud`);
          } else if (cert.status === "technical_issue") {
            toast(`⚠ ${filename}: Technical Issue — Manual review needed`, {
              icon: "⚠️",
            });
          }
        } else if (cert.status === "processing") {
          updateUpload(filename, { status: "processing" });
          setTimeout(poll, 3000);
        } else {
          setTimeout(poll, 2000);
        }
      } catch {
        setTimeout(poll, 5000);
      }
    };

    setTimeout(poll, 2000);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: processFiles,
    accept: { "application/pdf": [".pdf"] },
    maxSize: 50 * 1024 * 1024,
    onDragEnter: () => setIsDragOver(true),
    onDragLeave: () => setIsDragOver(false),
    onDropAccepted: () => setIsDragOver(false),
    onDropRejected: (files) => {
      setIsDragOver(false);
      files.forEach((f) => {
        const err = f.errors[0];
        toast.error(`${f.file.name}: ${err.message}`);
      });
    },
  });

  const removeUpload = (filename: string) => {
    setUploads((prev) => prev.filter((u) => u.filename !== filename));
  };

  const clearCompleted = () => {
    setUploads((prev) => prev.filter((u) => u.status !== "done"));
  };

  return (
    <div className="card p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-white">Upload Certificates</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            PDF files • Max 50MB each • Bulk upload supported
          </p>
        </div>
        {uploads.some((u) => u.status === "done") && (
          <button onClick={clearCompleted} className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
            Clear completed
          </button>
        )}
      </div>

      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={cn(
          "relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200",
          isDragActive || isDragOver
            ? "border-brand-500 bg-brand-50 dark:bg-brand-900/10"
            : "border-gray-200 dark:border-gray-700 hover:border-brand-400 hover:bg-gray-50 dark:hover:bg-gray-800/50"
        )}
      >
        <input {...getInputProps()} />

        <div className="flex flex-col items-center gap-3">
          <div className={cn(
            "w-14 h-14 rounded-xl flex items-center justify-center transition-colors",
            isDragActive ? "bg-brand-100 dark:bg-brand-900/30" : "bg-gray-100 dark:bg-gray-800"
          )}>
            {isDragActive ? (
              <FileUp size={28} className="text-brand-600 dark:text-brand-400" />
            ) : (
              <Upload size={28} className="text-gray-400 dark:text-gray-500" />
            )}
          </div>

          {isDragActive ? (
            <p className="text-brand-600 dark:text-brand-400 font-medium">
              Drop PDF files here
            </p>
          ) : (
            <>
              <div>
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Drag & drop PDF certificates here
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  or <span className="text-brand-600 dark:text-brand-400 font-medium">click to browse</span>
                </p>
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-400">
                <span>📄 PDF only</span>
                <span>⚡ Bulk upload</span>
                <span>🔒 Encrypted storage</span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Upload Queue */}
      {uploads.length > 0 && (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {uploads.map((upload) => (
            <UploadItem
              key={upload.filename}
              upload={upload}
              onRemove={() => removeUpload(upload.filename)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function UploadItem({
  upload,
  onRemove,
}: {
  upload: UploadProgress;
  onRemove: () => void;
}) {
  const statusIcon = {
    uploading: <Loader2 size={14} className="text-blue-500 animate-spin" />,
    queued: <Loader2 size={14} className="text-purple-500 animate-spin" />,
    processing: <Loader2 size={14} className="text-brand-500 animate-spin" />,
    done: <CheckCircle size={14} className="text-green-500" />,
    error: <AlertCircle size={14} className="text-red-500" />,
  };

  const statusLabel = {
    uploading: "Uploading...",
    queued: "Queued",
    processing: "Processing...",
    done: "Complete",
    error: upload.error || "Error",
  };

  return (
    <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg group">
      <File size={16} className="text-gray-400 flex-shrink-0" />

      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate">
            {upload.filename}
          </span>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {statusIcon[upload.status]}
            <span className={cn(
              "text-xs",
              upload.status === "done" && "text-green-600 dark:text-green-400",
              upload.status === "error" && "text-red-600 dark:text-red-400",
              ["uploading", "queued", "processing"].includes(upload.status) && "text-gray-500",
            )}>
              {statusLabel[upload.status]}
            </span>
          </div>
        </div>

        {upload.status === "uploading" && (
          <div className="mt-1.5 h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-300"
              style={{ width: `${upload.progress}%` }}
            />
          </div>
        )}
      </div>

      {(upload.status === "done" || upload.status === "error") && (
        <button
          onClick={onRemove}
          className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 text-gray-400 hover:text-gray-600"
        >
          <X size={12} />
        </button>
      )}
    </div>
  );
}

function chunkArray<T>(arr: T[], size: number): T[][] {
  return Array.from({ length: Math.ceil(arr.length / size) }, (_, i) =>
    arr.slice(i * size, i * size + size)
  );
}
