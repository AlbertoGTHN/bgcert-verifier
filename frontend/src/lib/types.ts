// ─── API Types ────────────────────────────────────────────────────────────────

export type ValidationStatus =
  | "pending"
  | "processing"
  | "verified_authentic"
  | "verified_internal"
  | "failed_fraudulent"
  | "technical_issue"
  | "error";

export type UserRole = "admin" | "compliance" | "hr" | "viewer";

export type CertificateType =
  | "criminal_background"
  | "police_clearance"
  | "government_clearance"
  | "court_record"
  | "unknown";

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  is_active: boolean;
  mfa_enabled: boolean;
  department?: string;
  last_login?: string;
  created_at: string;
}

export interface Certificate {
  id: string;
  filename: string;
  original_filename: string;
  file_size: number;
  page_count: number;
  country?: string;
  language_detected?: string;
  cert_type: CertificateType;
  holder_name?: string;
  holder_id?: string;
  cert_number?: string;
  issue_date?: string;
  expiry_date?: string;
  issuing_authority?: string;
  qr_code_found: boolean;
  qr_code_data?: string;
  qr_url?: string;
  status: ValidationStatus;
  validation_result?: string;
  confidence_score: number;
  verification_url?: string;
  verification_domain?: string;
  is_official_domain?: boolean;
  verification_text?: string;
  screenshot_url?: string;
  error_details?: string;
  error_code?: string;
  fraud_indicators?: Record<string, unknown>;
  fraud_score: number;
  is_potentially_fraudulent: boolean;
  processing_time_seconds?: number;
  analyst_notes?: string;
  uploaded_at: string;
  processed_at?: string;
  uploaded_by_id?: string;
  uploader_name?: string;
}

export interface CertificateListResponse {
  items: Certificate[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface ValidationSummary {
  total: number;
  verified_authentic: number;
  verified_internal: number;
  failed_fraudulent: number;
  technical_issue: number;
  pending: number;
  processing: number;
  error: number;
  avg_confidence: number;
  countries: string[];
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface ApiError {
  detail: string;
  status?: number;
}

// ─── UI Types ─────────────────────────────────────────────────────────────────

export interface UploadProgress {
  filename: string;
  progress: number;
  status: "uploading" | "queued" | "processing" | "done" | "error";
  certId?: string;
  error?: string;
}

export interface FilterState {
  status?: ValidationStatus;
  country?: string;
  search?: string;
  dateFrom?: string;
  dateTo?: string;
  page: number;
  size: number;
}

export interface StatusConfig {
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
  textColor: string;
  icon: string;
  darkBg: string;
  darkText: string;
}

// ─── Status Configuration Map ─────────────────────────────────────────────────

export const STATUS_CONFIG: Record<ValidationStatus, StatusConfig> = {
  verified_internal: {
    label: "Internal Analysis",
    color: "teal",
    bgColor: "bg-teal-50",
    borderColor: "border-teal-200",
    textColor: "text-teal-700",
    darkBg: "dark:bg-teal-900/20",
    darkText: "dark:text-teal-400",
    icon: "◈",
  },
  verified_authentic: {
    label: "Verified Authentic",
    color: "green",
    bgColor: "bg-green-50",
    borderColor: "border-green-200",
    textColor: "text-green-700",
    darkBg: "dark:bg-green-900/20",
    darkText: "dark:text-green-400",
    icon: "✓",
  },
  failed_fraudulent: {
    label: "Failed / Fraudulent",
    color: "red",
    bgColor: "bg-red-50",
    borderColor: "border-red-200",
    textColor: "text-red-700",
    darkBg: "dark:bg-red-900/20",
    darkText: "dark:text-red-400",
    icon: "✗",
  },
  technical_issue: {
    label: "Technical Issue",
    color: "yellow",
    bgColor: "bg-yellow-50",
    borderColor: "border-yellow-200",
    textColor: "text-yellow-700",
    darkBg: "dark:bg-yellow-900/20",
    darkText: "dark:text-yellow-400",
    icon: "⚠",
  },
  pending: {
    label: "Pending",
    color: "gray",
    bgColor: "bg-gray-50",
    borderColor: "border-gray-200",
    textColor: "text-gray-600",
    darkBg: "dark:bg-gray-800",
    darkText: "dark:text-gray-400",
    icon: "○",
  },
  processing: {
    label: "Processing",
    color: "blue",
    bgColor: "bg-blue-50",
    borderColor: "border-blue-200",
    textColor: "text-blue-600",
    darkBg: "dark:bg-blue-900/20",
    darkText: "dark:text-blue-400",
    icon: "↻",
  },
  error: {
    label: "Error",
    color: "red",
    bgColor: "bg-red-50",
    borderColor: "border-red-200",
    textColor: "text-red-700",
    darkBg: "dark:bg-red-900/20",
    darkText: "dark:text-red-400",
    icon: "!",
  },
};
