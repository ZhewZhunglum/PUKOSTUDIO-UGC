"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { INFLUENCER_STATUS_MAP, getFollowerTier } from "@/lib/constants";
import type { Influencer } from "@/types";
import { Pencil, Trash2 } from "lucide-react";

const PLATFORM_ICONS: Record<string, React.ReactNode> = {
  tiktok: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5">
      <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.5 2.89 2.89 0 0 1-2.89-2.89 2.89 2.89 0 0 1 2.89-2.89c.28 0 .54.04.79.1V9.01a6.32 6.32 0 0 0-.79-.05 6.34 6.34 0 0 0-6.34 6.34 6.34 6.34 0 0 0 6.34 6.34 6.34 6.34 0 0 0 6.33-6.34V8.69a8.18 8.18 0 0 0 4.78 1.52V6.77a4.85 4.85 0 0 1-1.01-.08z" />
    </svg>
  ),
  instagram: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-3.5 w-3.5">
      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.5" cy="6.5" r="0.5" fill="currentColor" stroke="none" />
    </svg>
  ),
  youtube: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5">
      <path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.5 12 3.5 12 3.5s-7.5 0-9.4.6A3 3 0 0 0 .5 6.2 31 31 0 0 0 0 12a31 31 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.6 9.4.6 9.4.6s7.5 0 9.4-.6a3 3 0 0 0 2.1-2.1A31 31 0 0 0 24 12a31 31 0 0 0-.5-5.8zM9.7 15.5V8.5l6.3 3.5-6.3 3.5z" />
    </svg>
  ),
};

function formatFollowers(value: number | null | undefined): string {
  if (!value) return "–";
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

interface InfluencerCardProps {
  influencer: Influencer;
  onEdit: (influencer: Influencer) => void;
  onDelete: (influencer: Influencer) => void;
}

export function InfluencerCard({ influencer, onEdit, onDelete }: InfluencerCardProps) {
  const firstPlatform = influencer.platforms[0] ?? null;
  const followerTier = firstPlatform ? getFollowerTier(firstPlatform.followers) : null;
  const statusInfo = INFLUENCER_STATUS_MAP[influencer.status];
  const initials = influencer.name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <Card className="group relative flex flex-col gap-3 p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md">
      {/* Avatar + status */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-3">
          {influencer.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={influencer.avatar_url}
              alt={influencer.name}
              className="h-10 w-10 rounded-full object-cover ring-1 ring-border"
            />
          ) : (
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted text-sm font-semibold text-muted-foreground ring-1 ring-border">
              {initials || "?"}
            </div>
          )}
          <div className="min-w-0">
            <Link
              href={`/influencers/${influencer.id}`}
              className="block truncate font-semibold leading-tight hover:underline"
            >
              {influencer.name}
            </Link>
            {influencer.email && (
              <p className="truncate text-xs text-muted-foreground">{influencer.email}</p>
            )}
          </div>
        </div>
        <Badge variant={statusInfo?.variant ?? "secondary"} className="shrink-0 text-xs">
          {statusInfo?.label ?? influencer.status}
        </Badge>
      </div>

      {/* Platform pills */}
      {influencer.platforms.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {influencer.platforms.map((p) => (
            <span
              key={p.id}
              className="flex items-center gap-1 rounded-full border bg-muted/50 px-2 py-0.5 text-xs text-muted-foreground"
            >
              {PLATFORM_ICONS[p.platform] ?? null}
              @{p.username}
            </span>
          ))}
        </div>
      )}

      {/* Stats row */}
      <div className="flex items-center gap-3 text-sm">
        {firstPlatform?.followers != null && (
          <div className="flex flex-col">
            <span className="text-xs text-muted-foreground">粉丝</span>
            <span className="font-semibold">{formatFollowers(firstPlatform.followers)}</span>
          </div>
        )}
        {firstPlatform?.engagement_rate != null && (
          <div className="flex flex-col">
            <span className="text-xs text-muted-foreground">互动率</span>
            <span className="font-semibold">{firstPlatform.engagement_rate.toFixed(1)}%</span>
          </div>
        )}
        {followerTier && (
          <span className={`ml-auto rounded-full px-2 py-0.5 text-xs font-medium ${followerTier.color}`}>
            {followerTier.value.charAt(0).toUpperCase() + followerTier.value.slice(1)}
          </span>
        )}
      </div>

      {/* Niche tag */}
      {influencer.niche && (
        <div>
          <Badge variant="outline" className="text-xs capitalize">
            {influencer.niche.replace(/_/g, " ")}
          </Badge>
        </div>
      )}

      {/* Actions — shown on hover */}
      <div className="flex justify-end gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
        <Button variant="ghost" size="sm" onClick={() => onEdit(influencer)}>
          <Pencil className="h-3.5 w-3.5" />
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onDelete(influencer)}>
          <Trash2 className="h-3.5 w-3.5 text-red-500" />
        </Button>
      </div>
    </Card>
  );
}
