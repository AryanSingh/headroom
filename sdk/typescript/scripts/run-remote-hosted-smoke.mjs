import { performance } from "node:perf_hooks";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { HostedCompressionClient } from "../dist/index.js";

const baseUrl = process.env.CUTCTX_HOSTED_BASE_URL?.replace(/\/+$/, "");
const apiKey = process.env.CUTCTX_HOSTED_API_KEY;
if (!baseUrl || !apiKey) {
  console.log(JSON.stringify({
    status: "not_configured",
    reason: "CUTCTX_HOSTED_BASE_URL and CUTCTX_HOSTED_API_KEY are required",
  }, null, 2));
  process.exit(0);
}

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const artifactDirectory = resolve(scriptDirectory, "../../../artifacts");
const jsonOutput = process.env.CUTCTX_HOSTED_TS_SMOKE_JSON_OUTPUT
  ?? resolve(artifactDirectory, "remote-hosted-compression-smoke-typescript.json");
const markdownOutput = process.env.CUTCTX_HOSTED_TS_SMOKE_MARKDOWN_OUTPUT
  ?? resolve(artifactDirectory, "remote-hosted-compression-smoke-typescript.md");
const client = new HostedCompressionClient({ baseUrl, apiKey, timeout: 60_000 });
const percentile = (values, p) => values[Math.min(values.length - 1, Math.ceil(values.length * p) - 1)];
const results = [];

for (const [name, rows] of [["small", 12], ["medium", 120], ["large", 720]]) {
  const payload = Array.from({ length: rows }, (_, index) =>
    `row=${index} status=${index % 7 === 0 ? "error" : "ok"} repeated=staging-smoke`,
  ).join("\n");
  const latenciesMs = [];
  let tokensSaved = 0;
  for (let sample = 0; sample < 3; sample += 1) {
    const startedAt = performance.now();
    const result = await client.compressMessages([
      { role: "user", content: "Summarize this tool output and retain errors." },
      { role: "tool", content: payload },
    ]);
    latenciesMs.push(Math.round(performance.now() - startedAt));
    tokensSaved = result.tokensSaved;
  }
  latenciesMs.sort((a, b) => a - b);
  results.push({ payload: name, rows, samples: latenciesMs.length, p50_ms: percentile(latenciesMs, 0.5), p95_ms: percentile(latenciesMs, 0.95), tokens_saved: tokensSaved });
}

const evidence = { status: "passed", sdk: "typescript", base_url: baseUrl, results };
await Promise.all([
  mkdir(dirname(jsonOutput), { recursive: true }),
  mkdir(dirname(markdownOutput), { recursive: true }),
]);
await writeFile(jsonOutput, `${JSON.stringify(evidence, null, 2)}\n`, "utf8");
const markdown = [
  "# Remote Hosted Compression Smoke (TypeScript SDK)",
  "",
  `- Base URL: \`${baseUrl}\``,
  "",
  "| Payload | Rows | Samples | P50 | P95 | Tokens Saved |",
  "|---|---:|---:|---:|---:|---:|",
  ...results.map((result) => (
    `| ${result.payload} | ${result.rows} | ${result.samples} | ${result.p50_ms} ms | ${result.p95_ms} ms | ${result.tokens_saved} |`
  )),
  "",
  "API keys and payload bodies are intentionally excluded from this artifact.",
].join("\n");
await writeFile(markdownOutput, `${markdown}\n`, "utf8");
console.log(JSON.stringify(evidence, null, 2));
