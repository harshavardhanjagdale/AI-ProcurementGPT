"use client";

import { useEffect, useState } from "react";
import { LogOut, User } from "lucide-react";
import { authService } from "@/services/auth.service";
import type { User as UserType } from "@/types";

export function Header() {
  const [user, setUser] = useState<UserType | null>(null);

  useEffect(() => {
    authService.getMe().then(setUser).catch(() => {});
  }, []);

  return (
    <header className="h-16 border-b border-border bg-white flex items-center justify-between px-8">
      <div>
        <h2 className="text-sm text-muted-foreground">Welcome back,</h2>
        <h1 className="text-lg font-semibold text-foreground">
          {user?.full_name || "Loading..."}
        </h1>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted">
          <User className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm text-foreground">{user?.role?.replace("_", " ")}</span>
        </div>
        <button
          onClick={() => authService.logout()}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-muted-foreground hover:bg-red-50 hover:text-red-600 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </button>
      </div>
    </header>
  );
}
