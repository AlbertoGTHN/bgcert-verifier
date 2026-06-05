"use client";

import { useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import toast from "react-hot-toast";

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [showMfa, setShowMfa] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password, showMfa ? mfaCode : undefined);
      toast.success("Welcome back!");
      router.push("/dashboard");
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      if (detail === "MFA_REQUIRED") {
        setShowMfa(true);
        toast("Please enter your MFA code", { icon: "🔐" });
      } else {
        toast.error(detail || "Login failed. Check your credentials.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-gray-950">
      {/* Left: Branding */}
      <div className="hidden lg:flex flex-col justify-between w-1/2 bg-gradient-to-br from-brand-900 via-brand-800 to-brand-700 p-12 text-white">
        <div>
          <div className="mb-12">
            <Image
              src="/icc-logo-purple.png"
              alt="Interactive Contact Center"
              width={220}
              height={66}
              className="rounded-xl"
              priority
            />
          </div>
          <h1 className="text-4xl font-bold leading-tight mb-4">
            Certificate<br />Verification<br />
            <span className="text-brand-200">Platform</span>
          </h1>
          <p className="text-brand-200 text-lg leading-relaxed">
            Enterprise-grade background check validation for HR and Compliance teams across multiple countries.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {[
            { label: "Multi-language OCR", icon: "🌐" },
            { label: "QR Verification", icon: "📱" },
            { label: "Fraud Detection", icon: "🛡️" },
            { label: "Bulk Processing", icon: "⚡" },
          ].map((feat) => (
            <div key={feat.label} className="bg-white/10 rounded-xl p-4">
              <div className="text-2xl mb-2">{feat.icon}</div>
              <div className="text-sm font-medium">{feat.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Right: Login Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="lg:hidden mb-8">
            <Image
              src="/icc-logo-light.png"
              alt="Interactive Contact Center"
              width={180}
              height={54}
              className="rounded-lg"
              priority
            />
          </div>

          <h2 className="text-2xl font-bold text-gray-100 mb-1">Sign in</h2>
          <p className="text-gray-400 text-sm mb-8">
            Certificate Verification Platform
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="label text-gray-400">Email address</label>
              <input
                type="email"
                className="input"
                placeholder="you@iccbpo.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            <div>
              <label className="label text-gray-400">Password</label>
              <input
                type="password"
                className="input"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>

            {showMfa && (
              <div className="animate-fade-in">
                <label className="label text-gray-400">
                  🔐 MFA Code (6 digits)
                </label>
                <input
                  type="text"
                  className="input font-mono tracking-widest text-center text-lg"
                  placeholder="000000"
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  maxLength={6}
                  autoFocus
                />
              </div>
            )}

            <button
              type="submit"
              className="w-full btn-primary py-2.5 justify-center text-base"
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Signing in...
                </>
              ) : (
                "Sign in"
              )}
            </button>
          </form>

          <div className="mt-8 p-4 bg-gray-800/50 rounded-xl border border-gray-700">
            <p className="text-xs text-gray-500 text-center">
              <span className="font-medium text-gray-400">Default admin:</span>{" "}
              admin@iccbpo.com / Admin@ICCBPO2024!
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
