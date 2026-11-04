// Hourly kick for the GitHub Actions build. GitHub's own cron drops most scheduled runs under load
// (we saw 5 runs in 26 hours), so Netlify's scheduler does the timekeeping and GitHub does the work.
// Needs GITHUB_DISPATCH_TOKEN (fine-grained PAT, repo wortha-watch, Actions: read & write) in the
// project's environment variables with the Functions scope.

const REPO = "perkinskit/wortha-watch";
const WORKFLOW = "build.yml";

export default async () => {
  const token = Netlify.env.get("GITHUB_DISPATCH_TOKEN");
  if (!token) {
    console.log("GITHUB_DISPATCH_TOKEN not set; nothing to do");
    return new Response("no token", { status: 200 });
  }
  const res = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "wortha-watch-scheduler",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  console.log(`dispatch ${WORKFLOW}: HTTP ${res.status}`);
  return new Response(`dispatch ${res.status}`, { status: res.ok ? 200 : 502 });
};

export const config = {
  schedule: "12 * * * *", // every hour at :12 UTC; the build itself takes ~2 minutes
};
