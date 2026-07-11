// Build-time loaders for the portfolio content tree (repo-root `content/`).
// The site is a static build: these run in Node during `astro build`, reading
// the JSON that the MCP pipeline commits. content/ is data, site/ is template
// — this file is the only bridge between them.

import fs from 'node:fs';
import path from 'node:path';

export type Lang = 'en' | 'pt';

/** Every human-readable string is bilingual. */
export interface Bilingual {
  en: string;
  pt: string;
}

/** Pick a language out of a bilingual object. */
export function t(value: Bilingual | undefined, lang: Lang): string {
  return value ? value[lang] : '';
}

// content/ lives at the repo root, one level above site/. Resolved from the
// working directory (always site/ during `astro dev`/`astro build`) rather than
// import.meta.url, which points into the bundled output at build time.
const CONTENT_DIR = path.resolve(process.cwd(), '..', 'content');

function readJson<T>(relPath: string): T | null {
  const full = path.join(CONTENT_DIR, relPath);
  if (!fs.existsSync(full)) return null;
  return JSON.parse(fs.readFileSync(full, 'utf-8')) as T;
}

function readDir<T>(subdir: string): T[] {
  const dir = path.join(CONTENT_DIR, subdir);
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith('.json'))
    .map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf-8')) as T);
}

// ── Types (mirror mcp/schemas/*.json) ──────────────────────────────────────

export interface ProfileLink {
  label: string;
  url: string;
  icon?: string;
}

export interface Profile {
  name: string;
  headline: Bilingual;
  bio?: Bilingual;
  location?: Bilingual;
  avatar?: string;
  github_username?: string;
  links: ProfileLink[];
}

export type FeedType = 'decision' | 'problem-solved' | 'shipped' | 'learning';

export interface FeedEntry {
  id: string;
  date: string;
  type: FeedType;
  tags: string[];
  narrative: Bilingual;
  technical: Bilingual;
  outcome?: Bilingual;
  status: 'draft' | 'published';
}

export interface Project {
  id: string;
  featured: boolean;
  title: Bilingual;
  summary: Bilingual;
  case_study?: Bilingual;
  stack: string[];
  links?: Record<string, string>;
  period: { start: string; end: string | null };
}

export interface Now {
  updated: string;
  items: Bilingual[];
}

export interface Experience {
  role: Bilingual;
  organization: string;
  location?: Bilingual;
  period: { start: string; end: string | null };
  summary: Bilingual;
  highlights?: Bilingual[];
}

export interface SkillGroup {
  category: Bilingual;
  items: string[];
}

export interface Education {
  degree: Bilingual;
  institution: string;
  period: { start: string; end: string | null };
}

export interface Certification {
  name: string;
  issuer: string;
  date?: string;
  url?: string;
}

export interface LanguageSkill {
  language: Bilingual;
  level: Bilingual;
}

export interface Award {
  title: Bilingual;
  issuer?: string;
  date?: string;
}

export interface CV {
  experience?: Experience[];
  skills?: SkillGroup[];
  education?: Education[];
  certifications?: Certification[];
  languages?: LanguageSkill[];
  awards?: Award[];
}

// ── Loaders ─────────────────────────────────────────────────────────────────

export function getProfile(): Profile {
  const profile = readJson<Profile>('profile.json');
  if (!profile) throw new Error('content/profile.json is required');
  return profile;
}

export function getCV(): CV {
  return readJson<CV>('cv.json') ?? {};
}

export function getNow(): Now | null {
  return readJson<Now>('now.json');
}

/** Only published entries render on the live site, newest first. */
export function getFeed(): FeedEntry[] {
  return readDir<FeedEntry>('feed')
    .filter((e) => e.status === 'published')
    .sort((a, b) => b.date.localeCompare(a.date));
}

/** Featured projects first, then by start date descending. */
export function getProjects(): Project[] {
  return readDir<Project>('projects').sort((a, b) => {
    if (a.featured !== b.featured) return a.featured ? -1 : 1;
    return b.period.start.localeCompare(a.period.start);
  });
}
