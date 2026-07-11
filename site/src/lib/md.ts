// Minimal markdown → HTML for the technical/case-study layers.
// Content is authored by the owner or the pipeline (trusted), so no sanitizer
// is needed. Rendered at build time.
import { marked } from 'marked';

marked.setOptions({ gfm: true, breaks: false });

export function md(source: string | undefined): string {
  if (!source) return '';
  return marked.parse(source, { async: false }) as string;
}
