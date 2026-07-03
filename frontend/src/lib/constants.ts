export const SUPPLEMENT_NICHES = [
  { value: "protein", label: "Protein & Whey" },
  { value: "vitamins", label: "Vitamins & Minerals" },
  { value: "preworkout", label: "Pre-Workout" },
  { value: "probiotics", label: "Probiotics & Gut Health" },
  { value: "omega3", label: "Omega-3 & Fish Oil" },
  { value: "collagen", label: "Collagen & Beauty" },
  { value: "weight_loss", label: "Weight Management" },
  { value: "general_health", label: "General Health & Wellness" },
] as const;

export type SupplementNiche = (typeof SUPPLEMENT_NICHES)[number]["value"];

export const FOLLOWER_TIERS = [
  { value: "c", label: "C / Nano (<1W)", min: 0, max: 10000, color: "bg-slate-100 text-slate-700" },
  { value: "b", label: "B / Micro (1-10W)", min: 10000, max: 100000, color: "bg-blue-100 text-blue-700" },
  { value: "a", label: "A / Mid (10-50W)", min: 100000, max: 500000, color: "bg-emerald-100 text-emerald-700" },
  { value: "s", label: "S / Macro (50W+)", min: 500000, max: Infinity, color: "bg-amber-100 text-amber-700" },
] as const;

export function getFollowerTier(followers: number | null) {
  if (followers === null || followers === undefined) return null;
  return FOLLOWER_TIERS.find((t) => followers >= t.min && followers < t.max) ?? null;
}

export const CAMPAIGN_STATUS_MAP: Record<
  string,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  draft: { label: "草稿", variant: "secondary" },
  active: { label: "进行中", variant: "default" },
  paused: { label: "已暂停", variant: "outline" },
  completed: { label: "已完成", variant: "secondary" },
  archived: { label: "已归档", variant: "secondary" },
};

export const INFLUENCER_STATUS_MAP: Record<
  string,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  new: { label: "新建", variant: "secondary" },
  contacted: { label: "已联系", variant: "default" },
  replied: { label: "已回复", variant: "default" },
  negotiating: { label: "谈判中", variant: "default" },
  signed: { label: "已签约", variant: "default" },
  rejected: { label: "已拒绝", variant: "destructive" },
  blacklisted: { label: "黑名单", variant: "destructive" },
};

export const CONVERSATION_INTENT_MAP: Record<
  string,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  interested: { label: "感兴趣", variant: "default" },
  question: { label: "提问中", variant: "outline" },
  negotiation: { label: "议价中", variant: "outline" },
  not_interested: { label: "不感兴趣", variant: "secondary" },
  spam: { label: "垃圾回复", variant: "destructive" },
  unknown: { label: "待识别", variant: "secondary" },
};

export const AI_DRAFT_STATUS_MAP: Record<
  string,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  pending_review: { label: "待审核", variant: "default" },
  approved: { label: "已批准", variant: "outline" },
  sent: { label: "已发送", variant: "secondary" },
  discarded: { label: "已废弃", variant: "secondary" },
  failed: { label: "需补规则", variant: "destructive" },
};

export const AI_RISK_LEVEL_MAP: Record<
  string,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  low: { label: "低风险", variant: "secondary" },
  medium: { label: "中风险", variant: "outline" },
  high: { label: "高风险", variant: "destructive" },
};
