// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// The public URL of the deployed site. Override with the SITE_URL env var at
// build time (Cloudflare Pages / Vercel both expose one). Host choice is
// deferred — this is a safe placeholder that only affects canonical/OG URLs.
const site = process.env.SITE_URL || 'https://example.com';

// https://astro.build/config
export default defineConfig({
  site,
  integrations: [sitemap()],
  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'pt'],
    routing: {
      prefixDefaultLocale: false, // EN at /, PT at /pt
    },
  },
});
