// Local frontend-testing mock of the UGC backend (NOT for production, not
// imported by the app). Serves just enough of /api/v1 for the influencers page,
// with an in-memory influencer pool — but the email-dig endpoints do REAL
// extraction by reusing the creator-finder extension's parsing modules, so the
// full UX (select → 批量提取邮箱 → progress → write-back) can be exercised
// without Postgres/Redis/Celery.
//
// Run:  node --use-env-proxy scripts/mock-api.mjs      (proxy needed for TikTok/YouTube)
// Then: cd frontend && npm run dev                     (login with any email/password)
import { createServer } from "node:http";
import { Resolver, resolveMx } from "node:dns/promises";
import { randomUUID } from "node:crypto";
import { inflateRawSync } from "node:zlib";

const CREATOR_FINDER = "file:///C:/Users/Daniel/.codex/creator-finder-extension/server";
let profiles, emailDig, profileFetch;
try {
  profiles = await import(`${CREATOR_FINDER}/profiles.mjs`);
  emailDig = await import(`${CREATOR_FINDER}/emailDig.mjs`);
  profileFetch = await import(`${CREATOR_FINDER}/profileFetch.mjs`);
} catch (error) {
  console.error(`无法加载 creator-finder 模块（${CREATOR_FINDER}）：`, error.message);
  process.exit(1);
}

const PORT = 8917;
const CONCURRENCY = 3;
const LINK_CONCURRENCY = 5;

/** Run fn over items with bounded concurrency, preserving order (from index.mjs). */
async function mapPool(items, limit, fn) {
  const results = new Array(items.length);
  let cursor = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (cursor < items.length) {
      const index = cursor++;
      results[index] = await fn(items[index], index);
    }
  });
  await Promise.all(workers);
  return results;
}

// ---------------------------------------------------------------- in-memory DB
const now = () => new Date().toISOString();

function influencer({ name, email = null, phone = null, platform, username, followers = null, niche = null, country = "US", source = "manual" }) {
  const id = randomUUID();
  return {
    id,
    name,
    email,
    email_verified: false,
    phone,
    email_source: null,
    phone_source: null,
    email_dig_status: null,
    email_dig_at: null,
    avatar_url: null,
    niche,
    country: country || "US",
    status: "new",
    notes: null,
    source,
    platforms: platform
      ? [{
          id: randomUUID(),
          platform,
          username,
          profile_url: profiles.profileUrlFor(platform, username),
          followers,
          engagement_rate: null,
          avg_views: null,
          data_provider: null,
          external_id: null,
          last_synced_at: null,
        }]
      : [],
    tags: [],
    created_at: now(),
    updated_at: now(),
  };
}

// Mix: some with emails (outreach-ready), some real public accounts without
// emails so 批量提取邮箱 has something genuine to dig.
const influencers = [
  influencer({ name: "Jane Creator", email: "jane@example.com", platform: "tiktok", username: "janeugc", followers: 12000, niche: "beauty" }),
  influencer({ name: "Sam Kitchen", email: "sam@kitchen-demo.com", platform: "youtube", username: "samcooks", followers: 88000, niche: "food" }),
  influencer({ name: "MrBeast", platform: "youtube", username: "MrBeast", followers: 300000000 }),
  influencer({ name: "MKBHD", platform: "youtube", username: "mkbhd", followers: 19000000, niche: "tech" }),
  influencer({ name: "Linus Tech Tips", platform: "youtube", username: "LinusTechTips", followers: 15000000, niche: "tech" }),
  influencer({ name: "Gordon Ramsay", platform: "tiktok", username: "gordonramsayofficial", followers: 40000000, niche: "food" }),
  influencer({ name: "无邮箱达人A", platform: "tiktok", username: "no.such.creator.a1", followers: 500 }),
  influencer({ name: "无邮箱达人B", platform: "instagram", username: "instagram", followers: 600000000 }),
];

// One draft campaign so 发起外联 can be tested end-to-end locally.
const campaigns = [
  { id: randomUUID(), name: "本地测试外联活动", status: "draft", created_at: now(), updated_at: now() },
];

const digJobs = new Map();

// ------------------------------------------------- email dig (real, from index.mjs)
async function fetchText(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(url, {
      redirect: "follow",
      signal: controller.signal,
      headers: { "user-agent": "creator-finder-local/0.1 (personal research)" },
    });
    if (!response.ok) return "";
    const type = response.headers.get("content-type") ?? "";
    if (type && !/text|html|json|xml/i.test(type)) return "";
    return await response.text();
  } catch {
    return "";
  } finally {
    clearTimeout(timer);
  }
}

const NO_MX_CODES = new Set(["ENOTFOUND", "ENODATA", "NXDOMAIN"]);
const mxCache = new Map();
let fallbackResolver;
async function domainHasMx(domain) {
  if (mxCache.has(domain)) return mxCache.get(domain);
  let ok = true;
  try {
    const records = await resolveMx(domain);
    ok = Array.isArray(records) && records.length > 0;
  } catch (error) {
    if (NO_MX_CODES.has(error?.code)) {
      ok = false;
    } else {
      try {
        if (!fallbackResolver) {
          fallbackResolver = new Resolver();
          fallbackResolver.setServers(["223.5.5.5", "119.29.29.29"]);
        }
        const records = await fallbackResolver.resolveMx(domain);
        ok = Array.isArray(records) && records.length > 0;
      } catch (fallbackError) {
        ok = !NO_MX_CODES.has(fallbackError?.code);
      }
    }
  }
  mxCache.set(domain, ok);
  return ok;
}

// The plugin's cleanEmail lets JSON-escape artifacts (trailing "\") through
// because it tests with a non-anchored regex; enforce a full match here like
// the Python port does.
const STRICT_EMAIL = /^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,24}$/i;

async function mxValidate(rawEmails) {
  const emails = rawEmails.filter((e) => STRICT_EMAIL.test(e));
  const valid = [];
  for (const domain of emailDig.emailDomains(emails)) {
    if (await domainHasMx(domain)) valid.push(...emails.filter((e) => e.endsWith(`@${domain}`)));
  }
  return Array.from(new Set(valid));
}

// Phone/WhatsApp extraction — the creator-finder plugin never had this, so it
// lives here (mirrors the Python port's email_extract.extract_phones_from_html).
const WA_LINK = /(?:wa\.me\/|api\.whatsapp\.com\/send[^"'\s>]*?phone=)\+?(\d{6,15})/gi;
const TEL_LINK = /tel:(\+?[\d\-().\s]{6,20}\d)/gi;
const INTL_PHONE = /\+\d{1,4}(?:[\s\-.]?\(?\d{1,4}\)?){2,6}/g;
function normalizePhone(candidate) {
  const digits = candidate.replace(/\D/g, "");
  return digits.length >= 7 && digits.length <= 15 ? `+${digits}` : null;
}
function extractPhones(html) {
  if (typeof html !== "string" || !html) return [];
  const candidates = [];
  for (const m of html.matchAll(WA_LINK)) candidates.push(m[1]);
  for (const m of html.matchAll(TEL_LINK)) candidates.push(m[1]);
  const text = html.replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<[^>]+>/g, " ");
  for (const m of text.matchAll(INTL_PHONE)) candidates.push(m[0]);
  const seen = new Set(), out = [];
  for (const c of candidates) {
    const p = normalizePhone(c);
    if (p && !seen.has(p)) { seen.add(p); out.push(p); }
  }
  return out;
}

async function digUrl(url) {
  const html = await fetchText(url);
  let emails = emailDig.extractEmailsFromHtml(html);
  const phones = extractPhones(html);
  if (emails.length === 0 && profiles.isAggregator(url)) {
    for (const outbound of profiles.extractOutboundLinks(html, url).slice(0, 6)) {
      const oh = await fetchText(outbound);
      const found = emailDig.extractEmailsFromHtml(oh);
      phones.push(...extractPhones(oh));
      if (found.length) { emails = found; break; }
    }
  }
  if (emails.length === 0) {
    for (const contactUrl of emailDig.contactUrlsFor(url)) {
      const ch = await fetchText(contactUrl);
      const found = emailDig.extractEmailsFromHtml(ch);
      phones.push(...extractPhones(ch));
      if (found.length) { emails = found; break; }
    }
  }
  return { emails: await mxValidate(emails), phones };
}

async function digCreator(target) {
  const { html, finalUrl } = await profileFetch.fetchProfileText(target.profileUrl);
  const identity = profiles.profileIdentityFromRedirect(target, finalUrl);
  if (!html) return { ...identity, platform: target.platform, emails: [], phones: [], links: [], status: "unreachable" };
  // Modern YouTube pages JSON-escape "&" as the six characters \u0026, which
  // hides redirect links from the plugin-era regex — normalize before parsing.
  const scannable = target.platform === "youtube" ? html.replace(/\\u0026/g, "&") : html;
  const profile = profiles.parseProfileHtml(target.platform, scannable);
  const bioEmails = emailDig.extractEmailsFromHtml(profile.bio ?? "");
  const bioPhones = extractPhones(profile.bio ?? "");
  const links = profile.externalLinks ?? [];
  const dug = await mapPool(links.slice(0, 8), LINK_CONCURRENCY, (link) => digUrl(link));
  const emails = Array.from(new Set((await mxValidate(bioEmails)).concat(dug.flatMap((d) => d.emails))));
  const phones = Array.from(new Set(bioPhones.concat(dug.flatMap((d) => d.phones))));
  return {
    platform: target.platform,
    handle: identity.handle,
    profile_url: identity.profileUrl,
    display_name: profile.displayName ?? identity.displayName,
    follower_count: profile.followerCount,
    emails,
    phones,
    links,
    status: emails.length || phones.length ? "found" : "no-email",
  };
}

function applyRow(row) {
  const email = row.emails?.[0];
  const phone = row.phones?.[0];
  const digStatus = email || phone ? "found" : (row.status === "unreachable" ? "unreachable" : "no-email");
  const markDug = (inf) => { inf.email_dig_status = digStatus; inf.email_dig_at = now(); inf.updated_at = now(); };

  if (row.influencer_id) {
    const inf = influencers.find((i) => i.id === row.influencer_id);
    if (!inf) return "no-email";
    markDug(inf);
    let updated = false;
    if (phone && !inf.phone) { inf.phone = phone; inf.phone_source = "dig"; updated = true; }
    if (email && !inf.email) { inf.email = email; inf.email_source = "dig"; updated = true; }
    return updated ? "updated" : "no-email";
  }
  const match = influencers.find((i) =>
    i.platforms.some((p) => p.platform === row.platform && p.username.toLowerCase() === (row.handle || "").toLowerCase()),
  );
  if (match) {
    markDug(match);
    let updated = false;
    if (phone && !match.phone) { match.phone = phone; match.phone_source = "dig"; updated = true; }
    if (email && !match.email) { match.email = email; match.email_source = "dig"; updated = true; }
    return updated ? "updated" : "no-email";
  }
  if (!email && !phone) return "no-match-no-email";
  const created = influencer({
    name: row.display_name || row.handle,
    email,
    phone,
    platform: row.platform,
    username: row.handle,
    followers: row.follower_count ?? null,
    source: "email_dig",
  });
  created.email_dig_status = "found";
  created.email_dig_at = now();
  influencers.unshift(created);
  return "created";
}

async function runDigJob(job) {
  job.status = "running";
  const rows = job.results;
  let cursor = 0;
  const workers = Array.from({ length: Math.min(CONCURRENCY, rows.length) }, async () => {
    while (cursor < rows.length) {
      const index = cursor++;
      const row = rows[index];
      const target = profiles.resolveTarget(row.entry, row.platform || job.default_platform);
      if (!target) {
        Object.assign(row, { status: "unresolved", emails: [] });
      } else {
        try {
          Object.assign(row, await digCreator(target));
        } catch {
          Object.assign(row, { status: "unreachable", emails: [] });
        }
      }
      job.processed_count += 1;
      job.found_count = rows.filter((r) => (r.emails?.length ?? 0) > 0).length;
      job.phone_found_count = rows.filter((r) => (r.phones?.length ?? 0) > 0).length;
    }
  });
  await Promise.all(workers);
  for (const row of rows) {
    row.applied = applyRow(row);
    if (row.applied === "updated") job.updated_count += 1;
    if (row.applied === "created") job.created_count += 1;
  }
  job.status = "completed";
  job.completed_at = now();
}

// Mock Woto paid backfill: no real API, deterministically "unlock" contact info
// for existing influencers so the UI flow is testable. Real backend hits Woto.
async function runWotoBackfill(job) {
  job.status = "running";
  let hash = 0;
  for (const row of job.results) {
    if (row.status === "no-platform") { row.applied = "no-platform"; job.processed_count += 1; continue; }
    const inf = influencers.find((i) => i.id === row.influencer_id);
    if (!inf) { row.status = "unresolved"; row.applied = "missing"; job.processed_count += 1; continue; }
    // Stable pseudo-random from the id so results don't change between polls.
    for (const ch of String(row.influencer_id)) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
    const roll = (hash % 100);
    const email = roll < 55 ? `${(row.handle || "creator").toLowerCase().replace(/[^a-z0-9]/g, "")}@woto-demo.com` : null;
    const phone = roll % 10 < 3 ? `+1${String(2000000000 + (hash % 7999999999)).slice(0, 10)}` : null;
    row.emails = email ? [email] : [];
    row.phones = phone ? [phone] : [];
    let updated = false;
    if (email && !inf.email) { inf.email = email; inf.email_source = "woto"; updated = true; }
    if (phone && !inf.phone) { inf.phone = phone; inf.phone_source = "woto"; updated = true; }
    if (email || phone) { inf.email_dig_status = "found"; inf.email_dig_at = now(); }
    else { inf.email_dig_status = "not-in-woto"; inf.email_dig_at = now(); }
    inf.updated_at = now();
    row.status = email || phone ? "found" : "not-in-woto";
    row.applied = updated ? "updated" : (email ? "has-email" : "not-in-woto");
    if (updated) job.updated_count += 1;
    job.processed_count += 1;
    job.found_count = job.results.filter((r) => (r.emails?.length ?? 0) > 0).length;
    job.phone_found_count = job.results.filter((r) => (r.phones?.length ?? 0) > 0).length;
    await new Promise((r) => setTimeout(r, 250)); // visible progress
  }
  job.resolved_count = job.results.filter((r) => r.status !== "no-platform" && r.status !== "not-in-woto").length;
  job.status = "completed";
  job.completed_at = now();
}

// ------------------------------------------------------------------ csv import
function parseCsvLine(line, delim = ",") {
  const out = [];
  let cur = "", inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') { inQuotes = !inQuotes; continue; }
    if (ch === delim && !inQuotes) { out.push(cur); cur = ""; continue; }
    cur += ch;
  }
  out.push(cur);
  return out.map((s) => s.trim());
}

// Header aliases mirror the real backend's import_mapping.py _ALIASES (keyed by
// "squashed" headers: lower-cased, spaces/hyphens/underscores stripped).
const ALIASES = {
  name: ["name", "displayname", "nickname", "creatorname", "fullname",
    "昵称", "姓名", "名称", "达人", "达人名称", "达人昵称", "红人", "博主",
    "红人名", "红人名称", "红人昵称", "达人名"],
  email: ["email", "emails", "mail", "邮箱", "电子邮箱", "邮件"],
  username: ["username", "handle", "account", "uid", "userid", "screenname",
    "用户名", "账号", "账户"],
  platform: ["platform", "平台", "渠道"],
  followers: ["followers", "followercount", "fans", "fanscount", "subscribers",
    "粉丝", "粉丝数", "粉丝量"],
  niche: ["niche", "category", "vertical", "领域", "类目", "垂类", "分类"],
  country: ["country", "region", "inferredregion", "国家", "地区"],
  avg_views: ["avgviews", "averageviews", "平均播放", "平均播放量", "平均观看",
    "近60天平均观看量", "近30天平均观看量", "平均观看量"],
  profile_url: ["profileurl", "url", "link", "profilelink", "homepage",
    "主页", "链接", "主页链接", "红人主页链接", "达人主页链接"],
  channel_id: ["channelid", "channel", "频道id", "频道"],
};
const PLATFORM_VALUES = {
  tiktok: "tiktok", tt: "tiktok", 抖音: "tiktok",
  instagram: "instagram", ig: "instagram", insta: "instagram", ins: "instagram",
  youtube: "youtube", yt: "youtube", ytb: "youtube", 油管: "youtube",
};
const COUNTRY_NAMES = {
  美国: "US", 英国: "GB", 加拿大: "CA", 澳大利亚: "AU", 德国: "DE", 法国: "FR",
  日本: "JP", 韩国: "KR", 新加坡: "SG", 马来西亚: "MY", 印度尼西亚: "ID", 泰国: "TH",
  越南: "VN", 菲律宾: "PH", 墨西哥: "MX", 巴西: "BR", 中国: "CN", 印度: "IN",
};
const squash = (h) => String(h ?? "").replace(/^﻿/, "").trim().toLowerCase().replace(/[\s_-]+/g, "");
const ALIAS_TO_FIELD = Object.fromEntries(
  Object.entries(ALIASES).flatMap(([field, list]) => list.map((a) => [squash(a), field])),
);

function cleanCount(value) {
  const t = String(value ?? "").trim().toLowerCase().replace(/,/g, "").replace(/\s/g, "");
  const m = t.match(/^(\d+(?:\.\d+)?)([km万w亿]?)$/);
  if (!m) return null;
  let n = parseFloat(m[1]);
  const u = m[2];
  if (u === "k") n *= 1e3;
  else if (u === "万" || u === "w") n *= 1e4;
  else if (u === "m") n *= 1e6;
  else if (u === "亿") n *= 1e8;
  return Math.round(n);
}
function cleanCountry(value) {
  const t = String(value ?? "").trim();
  if (COUNTRY_NAMES[t]) return COUNTRY_NAMES[t];
  return /^[A-Za-z]{2}$/.test(t) ? t.toUpperCase() : null;
}
function identityFromUrl(url) {
  try {
    const u = new URL(/:\/\//.test(url) ? url : `https://${url}`);
    const host = u.hostname.replace(/^www\./, "").toLowerCase();
    const seg = u.pathname.split("/").filter(Boolean);
    if (host.endsWith("tiktok.com")) { const at = seg.find((s) => s.startsWith("@")); return at ? ["tiktok", at.slice(1)] : ["", ""]; }
    if (host.endsWith("instagram.com")) return seg[0] ? ["instagram", seg[0]] : ["", ""];
    if (host.endsWith("youtube.com")) {
      const at = seg.find((s) => s.startsWith("@"));
      if (at) return ["youtube", at.slice(1)];
      if (seg.length >= 2 && ["channel", "c", "user"].includes(seg[0])) return ["youtube", seg[1]];
    }
  } catch { /* ignore */ }
  return ["", ""];
}

/** Shared import path: first cell row is the header, the rest are data. */
function importRows(cellRows) {
  const nonEmpty = cellRows.filter((cells) => cells.some((c) => String(c ?? "").trim()));
  if (nonEmpty.length < 2) return { total_rows: 0, imported: 0, skipped: 0, errors: ["Empty file"], imported_without_email_ids: [] };
  const rawHeaders = nonEmpty[0].map((h) => String(h ?? "").replace(/^﻿/, "").trim());
  const fields = rawHeaders.map((h) => ALIAS_TO_FIELD[squash(h)] ?? null);
  if (!fields.includes("name") && !fields.includes("username") && !fields.includes("profile_url") && !fields.includes("channel_id")) {
    return {
      total_rows: nonEmpty.length - 1, imported: 0, skipped: nonEmpty.length - 1,
      errors: [`表头无法识别（需要 name/username/displayName/达人名称/红人名/主页链接 之一）。检测到的表头：${rawHeaders.join(" | ")}`],
      imported_without_email_ids: [],
    };
  }
  let imported = 0, skipped = 0;
  const errors = [], noEmailIds = [];
  for (let i = 1; i < nonEmpty.length; i++) {
    const values = nonEmpty[i];
    const row = {};
    fields.forEach((f, idx) => { if (f && !(f in row)) row[f] = String(values[idx] ?? "").trim(); });

    let platform = PLATFORM_VALUES[(row.platform || "").trim().toLowerCase()] || "";
    let username = (row.username || "").replace(/^@/, "").trim();
    const profileUrl = row.profile_url || "";
    if (profileUrl && (!platform || !username)) {
      const [dp, du] = identityFromUrl(profileUrl);
      platform = platform || dp;
      username = username || du;
    }
    username = username || (row.channel_id || "").trim();
    const name = row.name || username;
    if (!name) { errors.push(`Row ${i}: 缺少达人名/用户名`); skipped += 1; continue; }

    const email = (row.email || "").split(/[;,，；\s]+/).map((e) => e.trim().toLowerCase())
      .find((e) => /^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,24}$/.test(e)) || null;
    const created = influencer({
      name,
      email,
      platform: ["tiktok", "instagram", "youtube"].includes(platform) ? platform : null,
      username: username || name,
      followers: cleanCount(row.followers),
      niche: row.niche || null,
      country: cleanCountry(row.country) || "US",
      source: "csv_import",
    });
    influencers.unshift(created);
    imported += 1;
    if (!email) noEmailIds.push(created.id);
  }
  return { total_rows: nonEmpty.length - 1, imported, skipped, errors, imported_without_email_ids: noEmailIds };
}

function importCsv(text) {
  const lines = text.replace(/^﻿/, "").split(/\r?\n/).filter((l) => l.trim());
  // Excel's UTF-16 "Unicode Text" export is tab-separated.
  const delim = lines[0]?.includes("\t") ? "\t" : ",";
  return importRows(lines.map((line) => parseCsvLine(line, delim)));
}

// ---------------------------------------------------------------- xlsx import
// Minimal zero-dep .xlsx reader: unzip (central directory + inflateRaw), then
// regex-parse sharedStrings + the first worksheet. Good enough for the flat
// tables Excel / creator-finder produce.
function unzipEntry(buf, wanted) {
  let i = buf.length - 22;
  const min = Math.max(0, i - 65535);
  while (i >= min && buf.readUInt32LE(i) !== 0x06054b50) i--;
  if (i < min) return null;
  const count = buf.readUInt16LE(i + 10);
  let off = buf.readUInt32LE(i + 16);
  for (let n = 0; n < count; n++) {
    if (buf.readUInt32LE(off) !== 0x02014b50) return null;
    const method = buf.readUInt16LE(off + 10);
    const csize = buf.readUInt32LE(off + 20);
    const nameLen = buf.readUInt16LE(off + 28);
    const extraLen = buf.readUInt16LE(off + 30);
    const commentLen = buf.readUInt16LE(off + 32);
    const lho = buf.readUInt32LE(off + 42);
    const name = buf.toString("utf8", off + 46, off + 46 + nameLen);
    if (wanted.test(name)) {
      const dataStart = lho + 30 + buf.readUInt16LE(lho + 26) + buf.readUInt16LE(lho + 28);
      const data = buf.subarray(dataStart, dataStart + csize);
      return method === 8 ? inflateRawSync(data) : Buffer.from(data);
    }
    off += 46 + nameLen + extraLen + commentLen;
  }
  return null;
}

function decodeXml(text) {
  return text
    .replace(/&#x([0-9a-f]+);/gi, (_, c) => String.fromCodePoint(parseInt(c, 16)))
    .replace(/&#(\d+);/g, (_, c) => String.fromCodePoint(Number(c)))
    .replace(/&quot;/g, '"').replace(/&apos;/g, "'")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
}

function xlsxToRows(buf) {
  const sheet = unzipEntry(buf, /^xl\/worksheets\/sheet1\.xml$/);
  if (!sheet) return null;
  const shared = [];
  const ss = unzipEntry(buf, /^xl\/sharedStrings\.xml$/)?.toString("utf8");
  if (ss) {
    for (const m of ss.matchAll(/<si(?:\s[^>]*)?>([\s\S]*?)<\/si>/g)) {
      shared.push(
        Array.from(m[1].matchAll(/<t(?:\s[^>]*)?>([\s\S]*?)<\/t>/g), (t) => decodeXml(t[1])).join(""),
      );
    }
  }
  const colIndex = (ref) => {
    let idx = 0;
    for (const ch of ref) idx = idx * 26 + (ch.charCodeAt(0) - 64);
    return idx - 1;
  };
  const rows = [];
  for (const rm of sheet.toString("utf8").matchAll(/<row[^>]*>([\s\S]*?)<\/row>/g)) {
    const cells = [];
    for (const cm of rm[1].matchAll(/<c\s([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)) {
      const attrs = cm[1];
      const inner = cm[2] ?? "";
      const ref = attrs.match(/r="([A-Z]+)\d+"/)?.[1];
      const col = ref ? colIndex(ref) : cells.length;
      const type = attrs.match(/t="(\w+)"/)?.[1];
      let value;
      if (type === "inlineStr") {
        value = Array.from(inner.matchAll(/<t(?:\s[^>]*)?>([\s\S]*?)<\/t>/g), (t) => decodeXml(t[1])).join("");
      } else {
        const v = inner.match(/<v>([\s\S]*?)<\/v>/)?.[1] ?? "";
        value = type === "s" ? shared[Number(v)] ?? "" : decodeXml(v);
      }
      cells[col] = value;
    }
    rows.push(Array.from(cells, (c) => c ?? ""));
  }
  return rows;
}

// --------------------------------------------------------------------- server
const paginated = (items, page = 1, perPage = 20) => ({
  items: items.slice((page - 1) * perPage, page * perPage),
  total: items.length,
  page,
  per_page: perPage,
  pages: Math.max(1, Math.ceil(items.length / perPage)),
});

function send(res, status, body) {
  res.writeHead(status, {
    "content-type": "application/json",
    "access-control-allow-origin": "*",
    "access-control-allow-headers": "content-type, authorization",
    "access-control-allow-methods": "GET, POST, PUT, DELETE, OPTIONS",
  });
  res.end(JSON.stringify(body));
}

const USER = { id: randomUUID(), email: "test@local.dev", name: "本地测试", role: "admin", team_id: randomUUID(), created_at: now() };
const TOKENS = { access_token: "mock-access-token", refresh_token: "mock-refresh-token", token_type: "bearer" };

const server = createServer(async (req, res) => {
  if (req.method === "OPTIONS") return send(res, 204, {});
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const path = url.pathname.replace(/\/$/, "");
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const raw = Buffer.concat(chunks);
  const json = () => { try { return JSON.parse(raw.toString() || "{}"); } catch { return {}; } };

  try {
    // auth
    if (path === "/api/v1/auth/login" || path === "/api/v1/auth/register" || path === "/api/v1/auth/refresh")
      return send(res, 200, TOKENS);
    if (path === "/api/v1/auth/me") return send(res, 200, USER);

    // influencers
    if (path === "/api/v1/influencers" && req.method === "GET") {
      let items = influencers;
      const search = url.searchParams.get("search");
      if (search) items = items.filter((i) => i.name.toLowerCase().includes(search.toLowerCase()) || (i.email ?? "").includes(search.toLowerCase()));
      const hasEmail = url.searchParams.get("has_email");
      if (hasEmail === "true") items = items.filter((i) => i.email);
      if (hasEmail === "false") items = items.filter((i) => !i.email);
      const status = url.searchParams.get("status");
      if (status) items = items.filter((i) => i.status === status);
      const niche = url.searchParams.get("niche");
      if (niche) items = items.filter((i) => i.niche === niche);
      const source = url.searchParams.get("source");
      if (source) items = items.filter((i) => i.source === source);
      const digStatus = url.searchParams.get("dig_status");
      if (digStatus === "none") items = items.filter((i) => !i.email_dig_status);
      else if (digStatus) items = items.filter((i) => i.email_dig_status === digStatus);
      return send(res, 200, paginated(items, Number(url.searchParams.get("page")) || 1, Number(url.searchParams.get("per_page")) || 20));
    }
    if (path === "/api/v1/influencers" && req.method === "POST") {
      const body = json();
      const p = body.platforms?.[0];
      const created = influencer({ name: body.name, email: body.email, platform: p?.platform, username: p?.username, followers: p?.followers, niche: body.niche });
      influencers.unshift(created);
      return send(res, 201, created);
    }
    if (path === "/api/v1/influencers/import" && req.method === "POST") {
      // multipart: crude but sufficient — grab the file part's body
      const probe = raw.toString("latin1");
      const filename = probe.match(/filename="([^"]*)"/i)?.[1] ?? "";
      const headerEnd = raw.indexOf("\r\n\r\n");
      const boundaryStart = raw.lastIndexOf("\r\n--");
      const body = headerEnd >= 0 && boundaryStart > headerEnd ? raw.subarray(headerEnd + 4, boundaryStart) : Buffer.alloc(0);
      if (/\.xlsx$/i.test(filename) || (body[0] === 0x50 && body[1] === 0x4b)) {
        const rows = xlsxToRows(body);
        if (!rows) {
          return send(res, 200, {
            total_rows: 0, imported: 0, skipped: 0,
            errors: ["无法解析该 Excel 文件（mock 仅支持标准 .xlsx；.xls 老格式请另存为 .xlsx 或 CSV）"],
            imported_without_email_ids: [],
          });
        }
        return send(res, 200, importRows(rows));
      }
      // Excel's "Unicode text" export is UTF-16LE — decode by BOM.
      const text = body[0] === 0xff && body[1] === 0xfe
        ? body.subarray(2).toString("utf16le")
        : body.toString("utf8");
      return send(res, 200, importCsv(text));
    }
    const infMatch = path.match(/^\/api\/v1\/influencers\/([0-9a-f-]{36})$/);
    if (infMatch && req.method === "PUT") {
      const inf = influencers.find((i) => i.id === infMatch[1]);
      if (!inf) return send(res, 404, { detail: "not found" });
      const body = json();
      Object.assign(inf, { name: body.name ?? inf.name, email: body.email ?? inf.email, niche: body.niche ?? inf.niche, notes: body.notes ?? inf.notes, updated_at: now() });
      return send(res, 200, inf);
    }
    if (infMatch && req.method === "DELETE") {
      const idx = influencers.findIndex((i) => i.id === infMatch[1]);
      if (idx >= 0) influencers.splice(idx, 1);
      return send(res, 204, {});
    }

    // email dig
    if (path === "/api/v1/discovery/email-dig" && req.method === "POST") {
      const body = json();
      const rows = [];
      for (const entry of body.entries ?? []) {
        if (String(entry).trim()) rows.push({ entry: String(entry).trim(), status: "pending" });
      }
      for (const id of body.influencer_ids ?? []) {
        const inf = influencers.find((i) => i.id === id);
        if (!inf) continue;
        const p = inf.platforms[0];
        if (!p) { rows.push({ influencer_id: id, entry: inf.name, status: "no-platform" }); continue; }
        rows.push({ influencer_id: id, entry: p.profile_url || p.username, platform: p.platform, handle: p.username, status: "pending" });
      }
      if (!rows.length) return send(res, 400, { detail: "没有可提取的输入" });
      const job = {
        id: randomUUID(), team_id: USER.team_id, status: "queued", mode: "dig",
        default_platform: body.default_platform || "tiktok",
        input_count: rows.length, processed_count: 0, resolved_count: 0,
        found_count: 0, phone_found_count: 0, updated_count: 0, created_count: 0,
        results: rows, error_message: null,
        started_at: now(), completed_at: null, created_at: now(), updated_at: now(),
      };
      digJobs.set(job.id, job);
      runDigJob(job).catch((error) => { job.status = "failed"; job.error_message = error.message; });
      return send(res, 202, job);
    }
    const jobMatch = path.match(/^\/api\/v1\/discovery\/email-dig\/([0-9a-f-]{36})$/);
    if (jobMatch) {
      const job = digJobs.get(jobMatch[1]);
      return job ? send(res, 200, job) : send(res, 404, { detail: "not found" });
    }

    // Woto paid backfill — mock simulates the paid DB: ~55% of dug-empty
    // creators get an email, ~30% a phone. Real backend calls the Woto API.
    if (path === "/api/v1/influencers/woto-backfill" && req.method === "POST") {
      const body = json();
      const rows = [];
      for (const id of body.influencer_ids ?? []) {
        const inf = influencers.find((i) => i.id === id);
        if (!inf) continue;
        const p = inf.platforms[0];
        if (!p) { rows.push({ influencer_id: id, entry: inf.name, status: "no-platform" }); continue; }
        rows.push({ influencer_id: id, entry: p.username, platform: p.platform, handle: p.username, status: "pending" });
      }
      if (!rows.length) return send(res, 400, { detail: "勾选的达人不存在或没有平台账号" });
      const job = {
        id: randomUUID(), team_id: USER.team_id, status: "queued", mode: "woto",
        default_platform: "tiktok",
        input_count: rows.length, processed_count: 0, resolved_count: 0,
        found_count: 0, phone_found_count: 0, updated_count: 0, created_count: 0,
        results: rows, error_message: null,
        started_at: now(), completed_at: null, created_at: now(), updated_at: now(),
      };
      digJobs.set(job.id, job);
      runWotoBackfill(job).catch((error) => { job.status = "failed"; job.error_message = error.message; });
      return send(res, 202, job);
    }

    // Campaigns: expose one draft so outreach is testable end-to-end.
    if (path === "/api/v1/campaigns" && req.method === "GET") return send(res, 200, campaigns);
    if (path === "/api/v1/client-campaigns") return send(res, 200, []);
    const enrollMatch = path.match(/^\/api\/v1\/campaigns\/([^/]+)\/enroll$/);
    if (enrollMatch && req.method === "POST") {
      const ids = Array.isArray(json().influencer_ids) ? json().influencer_ids : [];
      // Mirror the real backend: only influencers with an email are enrolled.
      const eligible = ids.filter((id) => influencers.find((i) => i.id === id && i.email));
      for (const id of eligible) {
        const inf = influencers.find((i) => i.id === id);
        if (inf) { inf.status = "contacted"; inf.updated_at = now(); }
      }
      return send(res, 200, { enrolled: eligible.length, skipped: ids.length - eligible.length });
    }
    const startMatch = path.match(/^\/api\/v1\/campaigns\/([^/]+)\/start$/);
    if (startMatch && req.method === "POST") {
      const c = campaigns.find((x) => x.id === startMatch[1]);
      if (c) c.status = "active";
      return send(res, 200, { ok: true, status: "active" });
    }

    // sidebar counters & everything else the layout touches
    if (path.startsWith("/api/v1/")) return send(res, 200, paginated([], 1, 1));
    send(res, 404, { detail: "not found" });
  } catch (error) {
    send(res, 500, { detail: error.message });
  }
});

server.listen(PORT, () => {
  console.log(`mock UGC api listening on http://localhost:${PORT}`);
  const proxy = process.env.HTTPS_PROXY ?? process.env.HTTP_PROXY;
  const proxyEnabled = process.execArgv.includes("--use-env-proxy") || process.env.NODE_USE_ENV_PROXY === "1";
  console.log(proxy && proxyEnabled ? `outbound via proxy ${proxy}` : "outbound direct (TikTok/YouTube 直连不通时请用 --use-env-proxy 并设置 HTTPS_PROXY)");
});
