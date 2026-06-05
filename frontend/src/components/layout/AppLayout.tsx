"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import Cookies from "js-cookie";

interface AppLayoutProps {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
}

export function AppLayout({ children, title, subtitle }: AppLayoutProps) {
  const router = useRouter();
  const { isAuthenticated, refreshUser } = useAuthStore();

  useEffect(() => {
    const token = Cookies.get("access_token");
    if (!token && !isAuthenticated) {
      router.push("/login");
      return;
    }
    refreshUser();
  }, []);

  if (!isAuthenticated && !Cookies.get("access_token")) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <Sidebar />
      <div className="pl-[260px] min-h-screen flex flex-col">
        <Header title={title} subtitle={subtitle} />
        <main className="flex-1 p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
