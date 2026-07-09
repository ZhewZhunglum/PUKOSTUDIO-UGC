"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  BookOpen,
  LayoutDashboard,
  Users,
  Megaphone,
  FileText,
  Inbox,
  Settings,
  Sparkles,
  ChevronDown,
  Building2,
  Handshake,
} from "lucide-react";
import { useAuthStore } from "@/lib/auth";
import api from "@/lib/api";

interface Badges {
  influencers: number;
  campaigns: number;
  inbox: number;
  clients: number;
  clientCampaigns: number;
  clientInbox: number;
}

const systemNav = [
  { href: "/templates", label: "邮件模板", icon: FileText },
  { href: "/settings",  label: "设置",     icon: Settings },
  { href: "/guide",     label: "使用指南", icon: BookOpen },
];

interface NavItemProps {
  href: string;
  label: string;
  icon: React.ElementType;
  isNew?: boolean;
  count?: number;
  isActive: boolean;
}

function NavItem({ href, label, icon: Icon, isNew, count, isActive }: NavItemProps) {
  return (
    <Link href={href} className={cn("operator-nav-item", isActive && "active")}>
      <Icon className="h-[15px] w-[15px] shrink-0" style={{ opacity: 0.9 }} />
      <span>{label}</span>
      {isNew && !isActive && <span className="operator-new-dot" />}
      {count != null && count > 0 && (
        <span className="operator-nav-count">{count.toLocaleString("zh-CN")}</span>
      )}
    </Link>
  );
}

export function Sidebar() {
  const logout = useAuthStore((s) => s.logout);
  const user = useAuthStore((s) => s.user);
  const pathname = usePathname();
  const [badges, setBadges] = useState<Badges>({ influencers: 0, campaigns: 0, inbox: 0, clients: 0, clientCampaigns: 0, clientInbox: 0 });

  useEffect(() => {
    Promise.all([
      api.get("/influencers", { params: { per_page: 1 } }).catch(() => null),
      api.get("/campaigns").catch(() => null),
      api.get("/conversations", { params: { per_page: 1 } }).catch(() => null),
      api.get("/clients", { params: { per_page: 1 } }).catch(() => null),
      api.get("/client-campaigns").catch(() => null),
      api.get("/client-conversations").catch(() => null),
    ]).then(([infRes, campRes, convRes, clientRes, clientCampRes, clientConvRes]) => {
      setBadges({
        influencers: infRes?.data?.total ?? 0,
        campaigns: Array.isArray(campRes?.data) ? campRes.data.filter((c: { status: string }) => c.status === "active").length : 0,
        inbox: convRes?.data?.total ?? 0,
        clients: clientRes?.data?.total ?? 0,
        clientCampaigns: Array.isArray(clientCampRes?.data) ? clientCampRes.data.filter((c: { status: string }) => c.status === "active").length : 0,
        clientInbox: Array.isArray(clientConvRes?.data) ? clientConvRes.data.length : 0,
      });
    });
  }, []);

  const workflowNav = [
    { href: "/dashboard",   label: "数据看板", icon: LayoutDashboard },
    { href: "/discovery",   label: "发现达人", icon: Sparkles, isNew: true },
    { href: "/influencers", label: "达人管理", icon: Users, count: badges.influencers },
    { href: "/campaigns",   label: "建联活动", icon: Megaphone, count: badges.campaigns },
    { href: "/inbox",       label: "收件箱",   icon: Inbox, count: badges.inbox },
  ];

  const clientNav = [
    { href: "/clients", label: "客户管理", icon: Building2, count: badges.clients },
    { href: "/client-campaigns", label: "客户建联", icon: Handshake, count: badges.clientCampaigns },
    { href: "/client-inbox", label: "客户收件箱", icon: Inbox, count: badges.clientInbox },
  ];

  const initials = user?.name ? user.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase() : "OP";
  const displayName = user?.name ?? "Brand Ops";

  return (
    <aside className="operator-sidebar">
      {/* Brand */}
      <div className="operator-brand">
        <div className="operator-brand-mark">U</div>
        <div>
          <div className="operator-brand-name">UGC Outreach</div>
          <div className="operator-brand-tag">Operator Workspace</div>
        </div>
      </div>

      {/* Workflow */}
      <div className="operator-nav-section">Workflow</div>
      {workflowNav.map((item) => (
        <NavItem
          key={item.href}
          {...item}
          isActive={pathname === item.href || pathname.startsWith(item.href + "/")}
        />
      ))}

      {/* B端客户 */}
      <div className="operator-nav-section">B端客户</div>
      {clientNav.map((item) => (
        <NavItem
          key={item.href}
          {...item}
          isActive={pathname === item.href || pathname.startsWith(item.href + "/")}
        />
      ))}

      {/* System */}
      <div className="operator-nav-section">System</div>
      {systemNav.map((item) => (
        <NavItem
          key={item.href}
          {...item}
          isActive={pathname === item.href || pathname.startsWith(item.href + "/")}
        />
      ))}

      {/* User card */}
      <div className="operator-sidebar-footer">
        <button onClick={logout} className="operator-user-card w-full">
          <div className="operator-user-avatar">{initials}</div>
          <div style={{ lineHeight: 1.2, flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: "12.5px", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{displayName}</div>
            <div style={{ fontSize: "11px", color: "var(--ink-3)" }}>Brand Ops · TW</div>
          </div>
          <ChevronDown className="h-3 w-3 shrink-0" style={{ color: "var(--ink-4)" }} />
        </button>
      </div>
    </aside>
  );
}
