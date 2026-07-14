// Static UI strings (section titles, labels). Content strings live in content/;
// these are the template's own chrome.
import type { Lang, FeedType } from './content';

export const ui = {
  en: {
    now: 'Now',
    updated: 'updated',
    feed: 'Feed',
    feedEmpty: 'Nothing logged yet — this feed fills itself as real work happens.',
    projects: 'Projects',
    experience: 'Experience',
    skills: 'Skills',
    education: 'Education',
    certifications: 'Certifications',
    languages: 'Languages',
    awards: 'Awards',
    technicalDetail: 'Technical detail',
    outcome: 'Outcome',
    present: 'present',
    repos: 'repos',
    followers: 'followers',
    stars: 'stars',
    switchLang: 'Português',
    caseStudy: 'Case study',
    skipToContent: 'Skip to content',
  },
  pt: {
    now: 'Agora',
    updated: 'atualizado',
    feed: 'Feed',
    feedEmpty: 'Nada registrado ainda — este feed se preenche sozinho conforme o trabalho real acontece.',
    projects: 'Projetos',
    experience: 'Experiência',
    skills: 'Habilidades',
    education: 'Formação',
    certifications: 'Certificações',
    languages: 'Idiomas',
    awards: 'Prêmios',
    technicalDetail: 'Detalhe técnico',
    outcome: 'Resultado',
    present: 'atual',
    repos: 'repositórios',
    followers: 'seguidores',
    stars: 'estrelas',
    switchLang: 'English',
    caseStudy: 'Estudo de caso',
    skipToContent: 'Pular para o conteúdo',
  },
} satisfies Record<Lang, Record<string, string>>;

export type UIStrings = (typeof ui)[Lang];

// Feed type → badge label, per language.
export const typeBadge: Record<Lang, Record<FeedType, string>> = {
  en: {
    decision: 'Decision',
    'problem-solved': 'Problem solved',
    shipped: 'Shipped',
    learning: 'Learning',
  },
  pt: {
    decision: 'Decisão',
    'problem-solved': 'Problema resolvido',
    shipped: 'Entregue',
    learning: 'Aprendizado',
  },
};
