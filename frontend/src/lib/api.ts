import axios, { AxiosInstance, AxiosError } from "axios";
import Cookies from "js-cookie";
import type {
  Certificate, CertificateListResponse, ValidationSummary,
  TokenResponse, User, FilterState,
} from "./types";

// In browser: use /api proxy (Next.js rewrites to backend container)
// In server components: use direct backend URL
const BASE_URL = typeof window !== "undefined" ? "" : (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000");

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: `${BASE_URL}/api/v1`,
      headers: { "Content-Type": "application/json" },
      timeout: 30000,
    });

    // Attach token to every request
    this.client.interceptors.request.use((config) => {
      const token = Cookies.get("access_token");
      if (token) config.headers.Authorization = `Bearer ${token}`;
      return config;
    });

    // Handle token expiry
    this.client.interceptors.response.use(
      (res) => res,
      async (error: AxiosError) => {
        if (error.response?.status === 401) {
          const refreshToken = Cookies.get("refresh_token");
          if (refreshToken) {
            try {
              const res = await this.refreshTokens(refreshToken);
              Cookies.set("access_token", res.access_token, { expires: 1/24 });
              Cookies.set("refresh_token", res.refresh_token, { expires: 7 });
              if (error.config) {
                error.config.headers.Authorization = `Bearer ${res.access_token}`;
                return this.client.request(error.config);
              }
            } catch {
              this.logout();
            }
          } else {
            this.logout();
          }
        }
        return Promise.reject(error);
      }
    );
  }

  logout() {
    Cookies.remove("access_token");
    Cookies.remove("refresh_token");
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }

  // ─── Auth ──────────────────────────────────────────────────────────────────

  async login(email: string, password: string, mfaCode?: string): Promise<TokenResponse> {
    const { data } = await this.client.post<TokenResponse>("/auth/login", {
      email,
      password,
      mfa_code: mfaCode,
    });
    return data;
  }

  async refreshTokens(refreshToken: string): Promise<TokenResponse> {
    const { data } = await this.client.post<TokenResponse>("/auth/refresh", {
      refresh_token: refreshToken,
    });
    return data;
  }

  async getMe(): Promise<User> {
    const { data } = await this.client.get<User>("/auth/me");
    return data;
  }

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await this.client.post("/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }

  // ─── Upload ────────────────────────────────────────────────────────────────

  async uploadSingle(
    file: File,
    onProgress?: (pct: number) => void
  ): Promise<Certificate> {
    const form = new FormData();
    form.append("file", file);
    const { data } = await this.client.post<Certificate>("/upload/single", form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded * 100) / e.total));
        }
      },
    });
    return data;
  }

  async uploadBulk(
    files: File[],
    onProgress?: (pct: number) => void
  ): Promise<Certificate[]> {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    const { data } = await this.client.post<Certificate[]>("/upload/bulk", form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded * 100) / e.total));
        }
      },
    });
    return data;
  }

  // ─── Certificates ──────────────────────────────────────────────────────────

  async getCertificates(filters: Partial<FilterState> = {}): Promise<CertificateListResponse> {
    const params: Record<string, string | number | undefined> = {
      page: filters.page ?? 1,
      size: filters.size ?? 20,
    };
    if (filters.status) params.status = filters.status;
    if (filters.country) params.country = filters.country;
    if (filters.search) params.search = filters.search;
    if (filters.dateFrom) params.date_from = filters.dateFrom;
    if (filters.dateTo) params.date_to = filters.dateTo;

    const { data } = await this.client.get<CertificateListResponse>("/certificates", { params });
    return data;
  }

  async getCertificate(id: string): Promise<Certificate> {
    const { data } = await this.client.get<Certificate>(`/certificates/${id}`);
    return data;
  }

  async updateCertificate(id: string, updates: { analyst_notes?: string; status?: string }): Promise<Certificate> {
    const { data } = await this.client.patch<Certificate>(`/certificates/${id}`, updates);
    return data;
  }

  async deleteCertificate(id: string): Promise<void> {
    await this.client.delete(`/certificates/${id}`);
  }

  async reprocessCertificate(id: string): Promise<Certificate> {
    const { data } = await this.client.post<Certificate>(`/certificates/${id}/reprocess`);
    return data;
  }

  async getSummary(): Promise<ValidationSummary> {
    const { data } = await this.client.get<ValidationSummary>("/certificates/summary");
    return data;
  }

  // ─── Reports ───────────────────────────────────────────────────────────────

  getReportUrl(
    format: "pdf" | "excel" | "csv",
    params: { cert_ids?: string; status?: string; country?: string } = {}
  ): string {
    const token = Cookies.get("access_token");
    const qs = new URLSearchParams(params as Record<string, string>);
    if (token) qs.set("token", token);
    const formatMap = { pdf: "pdf", excel: "excel", csv: "csv" };
    return `${BASE_URL}/api/v1/reports/export/${formatMap[format]}?${qs.toString()}`;
  }

  async downloadReport(
    format: "pdf" | "excel" | "csv",
    params: { cert_ids?: string; status?: string; country?: string } = {}
  ): Promise<void> {
    const token = Cookies.get("access_token");
    const qs = new URLSearchParams(params as Record<string, string>);
    const formatExt = { pdf: "pdf", excel: "xlsx", csv: "csv" };
    const mimeType = {
      pdf: "application/pdf",
      excel: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      csv: "text/csv",
    };

    const response = await this.client.get(`/reports/export/${format}`, {
      params,
      responseType: "blob",
    });

    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `iccbpo_report_${Date.now()}.${formatExt[format]}`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  }

  // ─── Admin ─────────────────────────────────────────────────────────────────

  async getUsers(): Promise<User[]> {
    const { data } = await this.client.get<User[]>("/admin/users");
    return data;
  }

  async createUser(payload: {
    email: string;
    name: string;
    password: string;
    role: string;
    department?: string;
  }): Promise<User> {
    const { data } = await this.client.post<User>("/admin/users", payload);
    return data;
  }

  async updateUser(id: string, updates: Partial<User>): Promise<User> {
    const { data } = await this.client.put<User>(`/admin/users/${id}`, updates);
    return data;
  }

  async deactivateUser(id: string): Promise<void> {
    await this.client.delete(`/admin/users/${id}`);
  }

  async getAuditLogs(limit = 100): Promise<unknown[]> {
    const { data } = await this.client.get(`/admin/audit-logs?limit=${limit}`);
    return data;
  }
}

export const api = new ApiClient();
export default api;
