// GitHub stats fetched at BUILD time, not client-side.
// Client-side calls hit the 60 req/h unauthenticated limit; the content
// pipeline rebuilds often enough to keep these fresh. A GITHUB_TOKEN env var
// (any read-only token) raises the build-time rate limit but is optional.
// Any failure returns null — the site renders fine without stats.

export interface GitHubStats {
  username: string;
  publicRepos: number;
  followers: number;
  totalStars: number;
  profileUrl: string;
}

const API = 'https://api.github.com';

function headers(): Record<string, string> {
  const h: Record<string, string> = {
    Accept: 'application/vnd.github+json',
    'User-Agent': 'living-portfolio-build',
  };
  const token = process.env.GITHUB_TOKEN;
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

export async function getGitHubStats(
  username: string | undefined,
): Promise<GitHubStats | null> {
  if (!username || username.startsWith('CHANGE')) return null;

  try {
    const userRes = await fetch(`${API}/users/${username}`, { headers: headers() });
    if (!userRes.ok) return null;
    const user = (await userRes.json()) as {
      public_repos: number;
      followers: number;
      html_url: string;
    };

    // Sum stars across public repos (first 100 by default is plenty).
    let totalStars = 0;
    const reposRes = await fetch(
      `${API}/users/${username}/repos?per_page=100&type=owner`,
      { headers: headers() },
    );
    if (reposRes.ok) {
      const repos = (await reposRes.json()) as Array<{ stargazers_count: number }>;
      totalStars = repos.reduce((sum, r) => sum + (r.stargazers_count || 0), 0);
    }

    return {
      username,
      publicRepos: user.public_repos,
      followers: user.followers,
      totalStars,
      profileUrl: user.html_url,
    };
  } catch {
    return null;
  }
}
