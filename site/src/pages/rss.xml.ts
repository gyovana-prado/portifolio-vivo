// RSS feed of published entries, so people can subscribe to your work.
// Generated at build time from content/feed (published only), English narrative.
import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import { getFeed, getProfile, t } from '../lib/content';

export function GET(context: APIContext) {
  const profile = getProfile();
  const feed = getFeed();

  return rss({
    title: `${profile.name} — Feed`,
    description: t(profile.headline, 'en'),
    site: context.site ?? 'https://example.com',
    items: feed.map((entry) => ({
      title: t(entry.narrative, 'en').split('. ')[0],
      description: t(entry.narrative, 'en'),
      pubDate: new Date(`${entry.date}T00:00:00Z`),
      categories: entry.tags,
      link: `/#feed-${entry.id}`,
    })),
  });
}
