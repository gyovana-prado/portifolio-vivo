// Human-readable date formatting, per language. Content stores machine dates
// (YYYY, YYYY-MM, YYYY-MM-DD); the site renders them for people.
import type { Lang } from './content';

const MONTHS: Record<Lang, string[]> = {
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
  pt: ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'],
};

/** '2022-10' → 'Oct 2022' / 'out 2022'; '2018' stays '2018'. */
export function formatYM(value: string, lang: Lang): string {
  const [year, month] = value.split('-');
  if (!month) return year;
  return `${MONTHS[lang][Number(month) - 1]} ${year}`;
}

/** '2026-07-11' → 'Jul 11, 2026' / '11 jul 2026'. Falls back to formatYM. */
export function formatDate(value: string, lang: Lang): string {
  const [year, month, day] = value.split('-');
  if (!day) return formatYM(value, lang);
  const m = MONTHS[lang][Number(month) - 1];
  return lang === 'en' ? `${m} ${Number(day)}, ${year}` : `${Number(day)} ${m} ${year}`;
}

/** {start, end} → 'Oct 2022 – Jan 2026' / 'out 2022 – atual'. */
export function formatPeriod(
  period: { start: string; end: string | null },
  lang: Lang,
  presentLabel: string,
): string {
  const end = period.end ? formatYM(period.end, lang) : presentLabel;
  return `${formatYM(period.start, lang)} – ${end}`;
}
