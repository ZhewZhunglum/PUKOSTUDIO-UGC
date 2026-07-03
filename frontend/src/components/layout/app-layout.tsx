"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "./sidebar";
import { useAuthStore } from "@/lib/auth";
import { Skeleton } from "@/components/ui/skeleton";
import { Bell, Calendar, ChevronRight, Search } from "lucide-react";

const CRUMB_MAP: Record<string, [string, string]> = {
  "/dashboard": ["工作台", "数据看板"],
  "/discovery": ["工作台", "发现达人"],
  "/influencers": ["资产", "达人管理"],
  "/blogerManager": ["资产", "红人管理"],
  "/campaigns": ["工作流", "建联活动"],
  "/inbox": ["工作流", "收件箱"],
  "/templates": ["系统", "邮件模板"],
  "/settings": ["系统", "设置"],
  "/guide": ["系统", "使用指南"],
};

function Topbar() {
  const pathname = usePathname();
  const rootPath = `/${pathname.split("/")[1] || "dashboard"}`;
  const crumbs = CRUMB_MAP[rootPath] ?? ["工作台", "UGC Outreach"];

  return (
    <header className="operator-topbar">
      <div className="operator-crumbs">
        <span>{crumbs[0]}</span>
        <ChevronRight className="h-3 w-3" />
        <span className="operator-crumb-current">{crumbs[1]}</span>
      </div>
      <div className="operator-search">
        <Search className="h-3.5 w-3.5" />
        <input placeholder="搜索达人、活动、对话..." />
        <kbd className="operator-kbd">⌘K</kbd>
      </div>
      <button className="operator-icon-btn" aria-label="通知">
        <Bell className="h-4 w-4" />
      </button>
      <button className="operator-icon-btn" aria-label="日历">
        <Calendar className="h-4 w-4" />
      </button>
    </header>
  );
}

function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="operator-app">
      <Sidebar />
      <main className="operator-main">
        <Topbar />
        <div className="operator-page">{children}</div>
      </main>
    </div>
  );
}

function LoadingShell() {
  return (
    <div className="operator-app">
      <div className="operator-sidebar">
        <div className="operator-brand">
          <Skeleton className="h-7 w-7 rounded-md" />
          <Skeleton className="h-4 w-24" />
        </div>
        <div className="flex flex-col gap-1">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full rounded-md" />
          ))}
        </div>
      </div>
      <main className="operator-main">
        <div className="operator-topbar">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="ml-auto h-8 w-72 rounded-md" />
        </div>
        <div className="operator-page space-y-4">
          <div className="space-y-2">
            <Skeleton className="h-7 w-40" />
            <Skeleton className="h-4 w-64" />
          </div>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-20 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-64 rounded-xl" />
        </div>
      </main>
    </div>
  );
}

export function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isLoading, fetchUser } = useAuthStore();

  useEffect(() => {
    fetchUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) return <LoadingShell />;
  if (!isAuthenticated) return <LoadingShell />;

  return <AppShell>{children}</AppShell>;
}
