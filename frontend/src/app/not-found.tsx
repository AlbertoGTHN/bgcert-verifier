"use client";

import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <div className="text-center space-y-4">
        <div className="text-6xl">🔍</div>
        <h1 className="text-3xl font-bold text-white">Page Not Found</h1>
        <p className="text-gray-400">The page you're looking for doesn't exist.</p>
        <Link href="/dashboard" className="btn-primary inline-flex justify-center mt-4">
          Go to Dashboard
        </Link>
      </div>
    </div>
  );
}
