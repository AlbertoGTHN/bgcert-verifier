"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { UserPlus, Edit2, Ban, Shield, User } from "lucide-react";
import { AppLayout } from "@/components/layout/AppLayout";
import { cn, formatDate } from "@/lib/utils";
import api from "@/lib/api";
import type { User as UserType, UserRole } from "@/lib/types";

const ROLE_COLORS: Record<UserRole, string> = {
  admin: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  compliance: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  hr: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  viewer: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400",
};

function CreateUserModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "hr" as UserRole,
    department: "",
  });

  const mutation = useMutation({
    mutationFn: () => api.createUser(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("User created");
      onClose();
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || "Failed to create user");
    },
  });

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="card max-w-md w-full p-6 space-y-4">
        <h3 className="font-semibold text-gray-900 dark:text-white text-lg">Create New User</h3>

        <div>
          <label className="label">Full Name</label>
          <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div>
          <label className="label">Email</label>
          <input type="email" className="input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </div>
        <div>
          <label className="label">Password (min 8 chars)</label>
          <input type="password" className="input" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </div>
        <div>
          <label className="label">Role</label>
          <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}>
            <option value="hr">HR</option>
            <option value="compliance">Compliance</option>
            <option value="admin">Admin</option>
            <option value="viewer">Viewer</option>
          </select>
        </div>
        <div>
          <label className="label">Department (optional)</label>
          <input className="input" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
        </div>

        <div className="flex gap-3 pt-2">
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !form.name || !form.email || !form.password}
            className="btn-primary flex-1 justify-center"
          >
            {mutation.isPending ? "Creating..." : "Create User"}
          </button>
          <button onClick={onClose} className="btn-secondary flex-1 justify-center">Cancel</button>
        </div>
      </div>
    </div>
  );
}

export default function AdminUsersPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);

  const { data: users = [], isLoading } = useQuery<UserType[]>({
    queryKey: ["admin-users"],
    queryFn: () => api.getUsers(),
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => api.deactivateUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("User deactivated");
    },
  });

  return (
    <AppLayout title="User Management" subtitle="Manage HR and compliance team access">
      <div className="max-w-5xl space-y-5">
        <div className="flex justify-between items-center">
          <div>
            <span className="text-sm text-gray-500">{users.length} total users</span>
          </div>
          <button onClick={() => setShowCreate(true)} className="btn-primary gap-2">
            <UserPlus size={16} />
            Create User
          </button>
        </div>

        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr>
                <th className="table-header">User</th>
                <th className="table-header">Role</th>
                <th className="table-header">Department</th>
                <th className="table-header">Last Login</th>
                <th className="table-header">Status</th>
                <th className="table-header">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {isLoading ? (
                Array(4).fill(0).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    {Array(6).fill(0).map((_, j) => (
                      <td key={j} className="table-cell">
                        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : users.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="table-cell">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-brand-100 dark:bg-brand-900/30 rounded-full flex items-center justify-center">
                        <span className="text-xs font-semibold text-brand-700 dark:text-brand-400">
                          {user.name.charAt(0).toUpperCase()}
                        </span>
                      </div>
                      <div>
                        <div className="text-sm font-medium text-gray-900 dark:text-white">{user.name}</div>
                        <div className="text-xs text-gray-400">{user.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="table-cell">
                    <span className={cn("badge capitalize", ROLE_COLORS[user.role])}>
                      {user.role}
                    </span>
                  </td>
                  <td className="table-cell text-xs">{user.department || "—"}</td>
                  <td className="table-cell text-xs">{user.last_login ? formatDate(user.last_login) : "Never"}</td>
                  <td className="table-cell">
                    <span className={cn(
                      "badge",
                      user.is_active
                        ? "bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400"
                        : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500"
                    )}>
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="table-cell">
                    <button
                      onClick={() => {
                        if (confirm(`Deactivate ${user.name}?`)) {
                          deactivateMutation.mutate(user.id);
                        }
                      }}
                      disabled={!user.is_active}
                      className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors disabled:opacity-30"
                      title="Deactivate user"
                    >
                      <Ban size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showCreate && <CreateUserModal onClose={() => setShowCreate(false)} />}
    </AppLayout>
  );
}
