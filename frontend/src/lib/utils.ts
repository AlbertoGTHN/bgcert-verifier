import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { format, formatDistanceToNow } from "date-fns";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date): string {
  if (!date) return "—";
  return format(new Date(date), "MMM d, yyyy");
}

export function formatDateTime(date: string | Date): string {
  if (!date) return "—";
  return format(new Date(date), "MMM d, yyyy HH:mm");
}

export function formatRelative(date: string | Date): string {
  if (!date) return "—";
  return formatDistanceToNow(new Date(date), { addSuffix: true });
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function formatConfidence(score: number): string {
  return `${Math.round(score * 100)}%`;
}

export function truncate(str: string, maxLen: number): string {
  if (!str || str.length <= maxLen) return str;
  return str.slice(0, maxLen) + "...";
}

export function getStatusEmoji(status: string): string {
  const map: Record<string, string> = {
    verified_authentic: "✅",
    failed_fraudulent: "❌",
    technical_issue: "⚠️",
    pending: "⏳",
    processing: "🔄",
    error: "💥",
  };
  return map[status] || "❓";
}

export function debounce<T extends (...args: unknown[]) => unknown>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timer: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

export function groupBy<T>(arr: T[], key: keyof T): Record<string, T[]> {
  return arr.reduce(
    (acc, item) => {
      const k = String(item[key]);
      (acc[k] = acc[k] || []).push(item);
      return acc;
    },
    {} as Record<string, T[]>
  );
}

// ── Country flags ────────────────────────────────────────────────────────────
export const COUNTRY_FLAGS: Record<string, string> = {
  // Latin America
  "Colombia": "🇨🇴",
  "Peru": "🇵🇪",
  "Mexico": "🇲🇽",
  "Chile": "🇨🇱",
  "Brazil": "🇧🇷",
  "Argentina": "🇦🇷",
  "Ecuador": "🇪🇨",
  "Venezuela": "🇻🇪",
  "Bolivia": "🇧🇴",
  "Paraguay": "🇵🇾",
  "Uruguay": "🇺🇾",
  "Costa Rica": "🇨🇷",
  "Panama": "🇵🇦",
  "El Salvador": "🇸🇻",
  "Honduras": "🇭🇳",
  "Guatemala": "🇬🇹",
  "Dominican Republic": "🇩🇴",
  "Jamaica": "🇯🇲",
  "Trinidad and Tobago": "🇹🇹",
  "Belize": "🇧🇿",
  // North America
  "United States": "🇺🇸",
  "Canada": "🇨🇦",
  // Europe
  "United Kingdom": "🇬🇧",
  "Spain": "🇪🇸",
  "France": "🇫🇷",
  "Germany": "🇩🇪",
  "Netherlands": "🇳🇱",
  "Portugal": "🇵🇹",
  "Italy": "🇮🇹",
  // Asia-Pacific
  "Philippines": "🇵🇭",
  "India": "🇮🇳",
  "Indonesia": "🇮🇩",
  "Malaysia": "🇲🇾",
  "Singapore": "🇸🇬",
  "Thailand": "🇹🇭",
  "Vietnam": "🇻🇳",
  "Bangladesh": "🇧🇩",
  "Sri Lanka": "🇱🇰",
  "Nepal": "🇳🇵",
  "Pakistan": "🇵🇰",
  // Africa
  "South Africa": "🇿🇦",
  "Nigeria": "🇳🇬",
  "Kenya": "🇰🇪",
  "Ghana": "🇬🇭",
  // Oceania
  "Australia": "🇦🇺",
  "New Zealand": "🇳🇿",
};

export function getCountryFlag(country: string | null | undefined): string {
  if (!country) return "";
  return COUNTRY_FLAGS[country] ?? "";
}

export function formatCountry(country: string | null | undefined): string {
  if (!country) return "";
  const flag = getCountryFlag(country);
  return flag ? `${flag} ${country}` : country;
}
