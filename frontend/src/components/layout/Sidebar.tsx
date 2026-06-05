"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  FileCheck,
  FileText,
  Users,
  LogOut,
  BarChart3,
  ChevronRight,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  roles?: string[];
  badge?: string;
}

const navItems: NavItem[] = [
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: <LayoutDashboard size={18} />,
  },
  {
    href: "/certificates",
    label: "Certificates",
    icon: <FileCheck size={18} />,
  },
  {
    href: "/reports",
    label: "Reports",
    icon: <FileText size={18} />,
  },
  {
    href: "/admin/users",
    label: "Users",
    icon: <Users size={18} />,
    roles: ["admin"],
  },
  {
    href: "/admin/audit",
    label: "Audit Logs",
    icon: <BarChart3 size={18} />,
    roles: ["admin", "compliance"],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();

  const visible = navItems.filter(
    (item) => !item.roles || (user && item.roles.includes(user.role))
  );

  return (
    <aside className="fixed left-0 top-0 h-full w-[260px] bg-gray-950 border-r border-gray-800 flex flex-col z-40">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-gray-800">
        <Image
          src="/icc-logo-light.png"
          alt="Interactive Contact Center"
          width={160}
          height={48}
          className="rounded-md"
          priority
        />
        <div className="text-xs text-gray-500 mt-1.5">Certificate Checker</div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        <div className="text-xs font-semibold text-gray-600 uppercase tracking-wider px-3 mb-2 mt-2">
          Main Menu
        </div>
        {visible.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group",
                isActive
                  ? "bg-brand-800 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-gray-100"
              )}
            >
              <span className={cn(
                "flex-shrink-0",
                isActive ? "text-white" : "text-gray-500 group-hover:text-gray-300"
              )}>
                {item.icon}
              </span>
              <span className="flex-1">{item.label}</span>
              {item.badge && (
                <span className="bg-brand-600 text-white text-xs px-1.5 py-0.5 rounded-full">
                  {item.badge}
                </span>
              )}
              {isActive && <ChevronRight size={14} className="text-white/50" />}
            </Link>
          );
        })}
      </nav>

      {/* User section */}
      <div className="p-3 border-t border-gray-800">
        {user && (
          <div className="px-3 py-2 mb-2">
            <div className="text-xs font-medium text-gray-200 truncate">{user.name}</div>
            <div className="text-xs text-gray-500 truncate">{user.email}</div>
            <div className="mt-1">
              <span className="inline-block text-xs px-2 py-0.5 bg-gray-800 text-gray-400 rounded-full capitalize">
                {user.role}
              </span>
            </div>
          </div>
        )}
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:bg-red-900/20 hover:text-red-400 transition-colors"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
