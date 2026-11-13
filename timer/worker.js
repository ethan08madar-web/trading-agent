// Wakes the Robot: starts .github/workflows/robot.yml on GitHub (not a dry run).
// Secret GH_TOKEN: fine-grained token, this one repo, "Actions: Read and write" only.
const URL = "https://api.github.com/repos/ethan08madar-web/trading-agent/actions/workflows/robot.yml/dispatches";

async function wake(env) {
  const r = await fetch(URL, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.GH_TOKEN}`, Accept: "application/vnd.github+json",
               "User-Agent": "trading-robot-timer" },
    body: JSON.stringify({ ref: "main", inputs: { dry_run: "false" } }),
  });
  if (r.status !== 204) throw new Error(`GitHub said ${r.status}`); // shows as a failed cron in Cloudflare
  return r.status;
}

export default {
  scheduled: (_e, env, ctx) => ctx.waitUntil(wake(env)),
};
