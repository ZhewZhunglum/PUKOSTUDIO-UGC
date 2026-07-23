export interface User {
  id: string;
  email: string;
  name: string;
  role: "admin" | "member";
  team_id: string;
  created_at: string;
}

export interface WotoAudienceItem {
  /** Age group label e.g. "18-24" */
  ageGroup?: string;
  /** Gender code "M" | "F" */
  sex?: string;
  /** ISO country code */
  regionCode?: string;
  regionName?: string;
  regionNameEn?: string;
  /** Distribution as a decimal fraction (0–1) */
  distributionValue: number;
}

export interface WotoPlatformMetrics {
  /** Raw API response from bloggerSearch */
  search?: Record<string, unknown>;
  /** Raw API response from bloggerDetail */
  detail?: Record<string, unknown>;
  total_star?: number;
  region_zh?: string;
  region_cover?: string;
  like_avg?: number;
  like_avg_60d?: number;
  view_avg_15d?: number;
  view_avg_30d?: number;
  view_avg_60d?: number;
  view_avg_15n?: number;
  view_avg_30n?: number;
  interactive_rate_60d?: number;
  interactive_rate_30n_all?: number;
  interactive_rate_90d_post?: number;
  content_num?: number;
  latest_publish_date?: string;
  is_tk_union?: boolean;
  gmv_30d?: number | string;
  biz_count?: number;
  has_amazon_tag?: boolean;
  cate_ids?: string[];
  cate_names?: string[];
  fans_age?: WotoAudienceItem[];
  fans_sex?: WotoAudienceItem[];
  fans_region?: WotoAudienceItem[];
  provider?: string;
  tags?: unknown[];
}

export interface InfluencerPlatform {
  id: string;
  platform: "tiktok" | "instagram" | "youtube";
  username: string;
  profile_url: string | null;
  data_provider: string | null;
  external_id: string | null;
  followers: number | null;
  engagement_rate: number | null;
  avg_views: number | null;
  content_topics: {
    woto_tags?: unknown[];
    has_email?: boolean;
    cate_names?: string[];
    cate_ids?: string[];
  } | null;
  raw_data: WotoPlatformMetrics | null;
  last_synced_at: string | null;
}

export interface Tag {
  id: string;
  name: string;
  color: string | null;
}

export interface Influencer {
  id: string;
  name: string;
  email: string | null;
  email_verified: boolean;
  phone: string | null;
  /** Which batch job sourced the contact: "dig" (free crawl) | "woto" (paid) | null (import/manual) */
  email_source: string | null;
  phone_source: string | null;
  /** Outcome of the last batch contact dig: found | no-email | unreachable */
  email_dig_status: string | null;
  email_dig_at: string | null;
  avatar_url: string | null;
  niche: string | null;
  country: string | null;
  status:
    | "new"
    | "contacted"
    | "replied"
    | "negotiating"
    | "signed"
    | "rejected"
    | "blacklisted";
  notes: string | null;
  source: string | null;
  platforms: InfluencerPlatform[];
  tags: Tag[];
  created_at: string;
  updated_at: string;
}

export type ClientStatus =
  | "new"
  | "contacted"
  | "replied"
  | "negotiating"
  | "signed"
  | "rejected"
  | "blacklisted";

export type ClientRelationshipType = "buyer" | "agency_prospect" | "partner";

export interface Client {
  id: string;
  company_name: string;
  contact_name: string | null;
  title: string | null;
  email: string | null;
  phone: string | null;
  industry: string | null;
  website: string | null;
  relationship_type: ClientRelationshipType;
  status: ClientStatus;
  notes: string | null;
  source: string | null;
  created_at: string;
  updated_at: string;
}

export type InfluencerCRMAction =
  | "mark_contacted"
  | "mark_replied"
  | "mark_negotiating"
  | "mark_signed"
  | "mark_rejected"
  | "special_attention"
  | "favorite"
  | "recommend"
  | "blacklist"
  | "restore"
  | "append_note";

export interface InfluencerCRMSummary {
  total: number;
  has_email: number;
  woto: number;
  by_status: Record<string, number>;
  by_tag: Record<string, number>;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface CampaignTargetCriteria {
  niches?: string[];
  min_followers?: number;
  max_followers?: number;
  countries?: string[];
}

export interface CampaignScheduleConfig {
  batch_size?: number;
  send_window_start?: string;
  send_window_end?: string;
  timezone?: string;
}

export interface CampaignStep {
  id: string;
  step_order: number;
  step_type: "initial" | "follow_up";
  template_id: string;
  delay_days: number;
  condition: {
    requires_reply?: boolean;
    skip_if_bounced?: boolean;
  } | null;
  attachment_ids: string[];
}

export interface Campaign {
  id: string;
  name: string;
  description: string | null;
  status: "draft" | "active" | "paused" | "completed" | "archived";
  campaign_type: "ugc" | "brand_promo" | "tiktok_shop";
  target_criteria: CampaignTargetCriteria | null;
  schedule_config: CampaignScheduleConfig | null;
  steps: CampaignStep[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface CampaignEnrollment {
  id: string;
  influencer_id: string;
  influencer_name: string;
  influencer_email: string | null;
  current_step: number;
  status: string;
  enrolled_at: string | null;
  last_sent_at: string | null;
  last_email_status: string | null;
  failure_reason: string | null;
}

export interface CampaignAIPlaybook {
  id: string | null;
  campaign_id: string;
  enabled: boolean;
  product_name: string | null;
  product_description: string | null;
  offer_summary: string | null;
  deliverables: string | null;
  sample_policy: string | null;
  pricing_rules: string | null;
  negotiation_limits: string | null;
  prohibited_claims: string | null;
  tone: string | null;
  language: string | null;
  signature: string | null;
  reply_guidelines: string | null;
  campaign_objectives: string | null;
  target_audience: string | null;
  key_messages: string | null;
  content_dos: string | null;
  content_donts: string | null;
  required_hashtags: string | null;
  disclosure_requirements: string | null;
  payment_terms: string | null;
  usage_rights: string | null;
  approval_process: string | null;
  contract_required: boolean;
  content_review_checklist: string | null;
  posting_guidance: string | null;
  performance_kpis: string | null;
  competitor_notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ClientCampaignStep {
  id: string;
  step_order: number;
  step_type: "initial" | "follow_up";
  template_id: string;
  delay_days: number;
  condition: {
    requires_reply?: boolean;
    skip_if_bounced?: boolean;
    ab_subject_b?: string;
  } | null;
  attachment_ids: string[];
}

export interface ClientCampaign {
  id: string;
  name: string;
  description: string | null;
  status: "draft" | "active" | "paused" | "completed" | "archived";
  target_criteria: CampaignTargetCriteria | null;
  schedule_config: CampaignScheduleConfig | null;
  steps: ClientCampaignStep[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ClientCampaignEnrollment {
  id: string;
  client_id: string;
  client_company_name: string;
  client_email: string | null;
  current_step: number;
  status: string;
  enrolled_at: string | null;
  last_sent_at: string | null;
  last_email_status: string | null;
  failure_reason: string | null;
}

export interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  body_html: string;
  body_text: string | null;
  category: string;
  language: string;
  is_library: boolean;
  variables: {
    fields?: string[];
  } | null;
  created_at: string;
  updated_at: string;
}

export interface Attachment {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  purpose: string;
  created_at: string;
}

export interface SmtpProviderConfig {
  host: string;
  port: number;
  username: string;
  password: string;
  use_tls: boolean;
}

export interface SesProviderConfig {
  region: string;
  access_key_id: string;
  secret_access_key: string;
}

export interface SendGridProviderConfig {
  api_key: string;
}

export type ProviderConfigInput =
  | SmtpProviderConfig
  | SesProviderConfig
  | SendGridProviderConfig;

export interface EmailAccount {
  id: string;
  email_address: string;
  display_name: string | null;
  provider_type: "ses" | "sendgrid" | "smtp";
  daily_limit: number;
  sent_today: number;
  warmup_stage: number;
  is_active: boolean;
  health_status: "healthy" | "degraded" | "suspended";
  signature_enabled: boolean;
  signature_mode: "structured" | "custom";
  signature_content: string | null;
  signature_html: string | null;
  signature_logo_attachment_id: string | null;
  brand_color: string | null;
  social_links: Record<string, string> | null;
  created_at: string;
}

export interface EmailMessage {
  id: string;
  direction: "outbound" | "inbound";
  from_address: string;
  to_address: string;
  subject: string;
  body_html: string | null;
  body_text: string | null;
  status: string;
  message_id: string | null;
  in_reply_to: string | null;
  references: string | null;
  sent_at: string | null;
  opened_at: string | null;
  created_at: string;
}

export interface DashboardStats {
  total_influencers: number;
  active_campaigns: number;
  emails_sent: number;
  emails_delivered: number;
  emails_opened: number;
  emails_replied: number;
  emails_bounced: number;
  open_rate: number;
  reply_rate: number;
  bounce_rate: number;
}

export interface DailyStats {
  date: string;
  emails_sent: number;
  emails_delivered: number;
  emails_opened: number;
  emails_replied: number;
  emails_bounced: number;
}

export interface DashboardData {
  stats: DashboardStats;
  daily: DailyStats[];
}

export interface ConversationMessage {
  id: string;
  direction: "outbound" | "inbound";
  from_address: string;
  to_address: string;
  subject: string;
  body_html: string | null;
  body_text: string | null;
  status: string;
  message_id: string | null;
  in_reply_to: string | null;
  references: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  influencer_id: string;
  influencer_name: string;
  influencer_email: string | null;
  last_message_at: string | null;
  unread_count: number;
  ai_intent: "interested" | "not_interested" | "question" | "negotiation" | "spam" | "unknown" | null;
  ai_confidence: number | null;
  needs_review: boolean;
  assigned_to: string | null;
  latest_subject: string | null;
  last_message_preview: string | null;
  latest_draft_id: string | null;
  latest_draft_status: AIDraftStatus | null;
  risk_level: AIRiskLevel | null;
  automation_status: "draft_ready" | "needs_playbook" | "manual" | null;
}

export interface ConversationDetail extends Conversation {
  messages: ConversationMessage[];
}

export interface ReplyDraft {
  subject: string;
  body_html: string;
  body_text: string;
  provider_available: boolean;
  fallback_reason: string | null;
}

export interface ClientConversationMessage {
  id: string;
  direction: "outbound" | "inbound";
  from_address: string;
  to_address: string;
  subject: string;
  body_html: string | null;
  body_text: string | null;
  status: string;
  message_id: string | null;
  in_reply_to: string | null;
  references: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface ClientConversation {
  id: string;
  client_id: string;
  client_company_name: string;
  client_email: string | null;
  last_message_at: string | null;
  unread_count: number;
  needs_review: boolean;
  assigned_to: string | null;
  latest_subject: string | null;
  last_message_preview: string | null;
}

export interface ClientConversationDetail extends ClientConversation {
  messages: ClientConversationMessage[];
}

export type AIRiskLevel = "low" | "medium" | "high";

export type AIDraftStatus =
  | "pending_review"
  | "approved"
  | "sent"
  | "discarded"
  | "failed";

export interface AIMessageDraft {
  id: string;
  team_id: string;
  conversation_id: string;
  campaign_id: string | null;
  influencer_id: string;
  subject: string;
  body_html: string;
  body_text: string | null;
  intent: string | null;
  confidence: number | null;
  risk_level: AIRiskLevel;
  status: AIDraftStatus;
  failure_reason: string | null;
  rationale: string | null;
  missing_context: string | null;
  approved_by: string | null;
  approved_at: string | null;
  sent_message_id: string | null;
  metadata_: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface AIActionLog {
  id: string;
  team_id: string;
  conversation_id: string | null;
  campaign_id: string | null;
  draft_id: string | null;
  action_type: string;
  actor_user_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface SOPModule {
  id: string;
  title: string;
  output: string;
  system_area: string;
}

export interface SOPPricingBenchmark {
  tier: string;
  follower_range: string;
  tiktok: string;
  instagram_reels: string;
  youtube: string;
  collaboration_model: string;
}

export interface SOPPlatformGuide {
  platform: string;
  content_formats: string;
  strength: string;
  ideal_creators: string;
  best_posting_window_utc: string;
  amplification_note: string;
}

export interface SOPRule {
  title: string;
  description: string;
  severity: string | null;
}

export interface SOPPlaybook {
  source_title: string;
  source_updated_at: string;
  operating_principle: string;
  modules: SOPModule[];
  pricing_benchmarks: SOPPricingBenchmark[];
  platform_guides: SOPPlatformGuide[];
  screening_rules: SOPRule[];
  compliance_rules: SOPRule[];
  negotiation_scripts: SOPRule[];
  review_checklist: string[];
  performance_metrics: SOPRule[];
}

export interface SOPInfluencerScore {
  influencer_id: string | null;
  tier: string;
  tier_label: string;
  readiness_score: number;
  recommendation: string;
  flags: string[];
  strengths: string[];
  next_steps: string[];
}

export interface WotoQuota {
  remain_quota: number | null;
  raw: Record<string, unknown>;
}

export interface WotoDictionaryItem {
  id: string | number | null;
  dict_code: string | null;
  dict_value: string | null;
  dict_type_code: string | null;
  raw: Record<string, unknown>;
}

export interface WotoSyncRequest {
  platform: "tiktok" | "instagram" | "youtube";
  search_type: "KEYWORD" | "NAME";
  keyword?: string | null;
  blogger_name?: string | null;
  exclude_keywords: string[];
  region_ids: string[];
  category_ids: string[];
  min_followers?: number | null;
  max_followers?: number | null;
  min_engagement_rate?: number | null;
  max_engagement_rate?: number | null;
  has_email?: boolean | null;
  min_avg_views?: number | null;
  max_avg_views?: number | null;
  sort: "FANS_NUM" | "VIEW_AVG" | "INTERACTIVE_RATE" | "TOTAL_STAR";
  sort_order: "asc" | "desc";
  limit: number;
  fetch_detail: boolean;
  enrich_contacts: boolean;
  campaign_id?: string | null;
}

export interface WotoSyncJob {
  id: string;
  team_id: string;
  campaign_id: string | null;
  platform: string;
  query: WotoSyncRequest | Record<string, unknown> | null;
  status: "queued" | "running" | "completed" | "failed";
  discovered: number;
  created_count: number;
  updated_count: number;
  enrolled_count: number;
  skipped_count: number;
  estimated_cost_cny: number | string;
  actual_cost_cny: number | string;
  billable_search_calls: number;
  billable_detail_calls: number;
  billable_contact_calls: number;
  warning_messages: string[] | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WotoPricingItem {
  operation: string;
  label: string;
  platform: string;
  unit_price_cny: number | string;
  unit: string;
  return_count: string | null;
  description: string;
}

export interface WotoDiscountTier {
  min_calls: number;
  max_calls: number | null;
  discount_rate: number | string;
  label: string;
}

export interface WotoPricingTable {
  currency: "CNY";
  valid_from: string;
  valid_to: string;
  rate_limit_per_minute: number;
  duplicate_policy: string;
  items: WotoPricingItem[];
  discount_tiers: WotoDiscountTier[];
  current_month_billable_calls: number;
  current_discount_rate: number | string;
  current_month_spend_cny: number | string;
}

export interface WotoCostEstimateLine {
  operation: string;
  label: string;
  platform: string;
  unit_price_cny: number | string;
  units: number;
  subtotal_cny: number | string;
  discounted_subtotal_cny: number | string;
  note: string | null;
}

export interface WotoCostEstimate {
  currency: "CNY";
  discount_rate: number | string;
  monthly_billable_calls_before: number;
  estimated_billable_calls: number;
  estimated_subtotal_cny: number | string;
  estimated_total_cny: number | string;
  lines: WotoCostEstimateLine[];
  notes: string[];
}
