import Link from 'next/link';

import { Button } from './button';
import { CodeBlock } from './code-block';

type FeatureCard = {
  title: string;
  description: string;
  href: string;
  code?: string;
  lang?: string;
};

const features: FeatureCard[] = [
  {
    title: 'Lossless Compression (CCR)',
    description:
      'Compresses aggressively, stores originals, and gives the LLM a tool to retrieve full details. Nothing is thrown away.',
    href: '/docs/ccr',
  },
  {
    title: 'Smart Content Detection',
    description:
      'Auto-detects JSON, code, logs, text, diffs, and HTML. Routes each payload to the most appropriate compressor. Zero configuration needed.',
    href: '/docs/how-compression-works',
  },
  {
    title: 'Cache Optimization',
    description:
      'Stabilizes prefixes so provider KV caches hit. Tracks frozen messages to preserve the prompt-cache discount.',
    href: '/docs/cache-optimization',
  },
  {
    title: 'Image Compression',
    description:
      '40-90% token reduction via the trained ML router. Automatically selects the right resize and quality tradeoff per image.',
    href: '/docs/image-compression',
  },
  {
    title: 'Persistent Memory',
    description:
      'Hierarchical memory (user/session/agent/turn) with SQLite + HNSW backends. Survives across conversations.',
    href: '/docs/memory',
  },
  {
    title: 'Failure Learning',
    description:
      'Reads past sessions, finds failed tool calls, correlates what succeeded, and writes learnings to CLAUDE.md.',
    href: '/docs/failure-learning',
  },
  {
    title: 'Multi-Agent Context',
    description: 'Compress what moves between agents. Any framework.',
    href: '/docs/shared-context',
    code: 'ctx = SharedContext()\nctx.put("research", big_output)\nsummary = ctx.get("research")',
    lang: 'python',
  },
  {
    title: 'Metrics & Observability',
    description:
      'Prometheus endpoint, per-request logging, cost tracking, budget limits, and pipeline timing breakdowns.',
    href: '/docs/metrics',
  },
];

export async function KeyFeatures() {
  return (
    <div className="grid grid-cols-1 gap-4 my-8 not-prose md:grid-cols-2">
      {features.map((feature) => (
        <div
          key={feature.title}
          className="flex flex-col rounded-xl border border-fd-border bg-fd-card p-5"
        >
          <h3 className="text-base font-semibold text-fd-foreground">
            {feature.title}
          </h3>
          <p className="mt-2 flex-1 text-sm text-fd-muted-foreground">
            {feature.description}
          </p>

          {feature.code ? <CodeBlock code={feature.code} lang={feature.lang} /> : null}

          <Link
            href={feature.href}
            className="mt-3 text-sm font-medium hover:underline"
          >
            Learn more &rarr;
          </Link>
        </div>
      ))}
    </div>
  );
}

type IntegrationCard = {
  title: string;
  description: string;
  code: string;
  lang: string;
  href: string;
};

const integrations: IntegrationCard[] = [
  {
    title: 'LangChain',
    description:
      'Wrap any chat model. Supports memory, retrievers, tools, streaming, and async workflows.',
    code: 'from cutctx.integrations.langchain import CutCtxChatModel\nllm = CutCtxChatModel(ChatOpenAI())',
    lang: 'python',
    href: '/docs/langchain',
  },
  {
    title: 'Agno',
    description: 'Full agent framework integration with observability hooks.',
    code: 'from cutctx.integrations.agno import CutCtxAgnoModel\nmodel = CutCtxAgnoModel(Claude())\nagent = Agent(model=model)',
    lang: 'python',
    href: '/docs/agno',
  },
  {
    title: 'Strands',
    description: 'Model wrapping plus tool-output hooks for Strands Agents.',
    code: 'from cutctx.integrations.strands import CutCtxStrandsModel\nmodel = CutCtxStrandsModel(...)\nagent = Agent(model=model)',
    lang: 'python',
    href: '/docs/strands',
  },
  {
    title: 'MCP Tools',
    description:
      'Three tools for Claude Code, Cursor, or any MCP client: cutctx_compress, cutctx_retrieve, and cutctx_stats.',
    code: 'cutctx mcp install && claude',
    lang: 'bash',
    href: '/docs/mcp',
  },
  {
    title: 'TypeScript SDK',
    description:
      'compress(), Vercel AI SDK middleware, and OpenAI/Anthropic client wrappers.',
    code: 'npm install cutctx-ai',
    lang: 'bash',
    href: '/docs/vercel-ai-sdk',
  },
  {
    title: 'Vercel AI SDK',
    description:
      'One-liner withCutCtx() or cutctxMiddleware() support for any Vercel AI SDK model.',
    code: "import { withCutCtx } from 'cutctx-ai/vercel-ai'\nconst model = withCutCtx(openai('gpt-4o'))",
    lang: 'typescript',
    href: '/docs/vercel-ai-sdk',
  },
];

export async function FrameworkIntegrations() {
  return (
    <div className="not-prose">
      <div className="grid grid-cols-1 gap-4 my-8 md:grid-cols-2">
        {integrations.map((integration) => (
          <div
            key={integration.title}
            className="flex flex-col rounded-xl border border-fd-border bg-fd-card p-5"
          >
            <h3 className="text-base font-semibold text-fd-foreground">
              {integration.title}
            </h3>
            <p className="mt-2 flex-1 text-sm text-fd-muted-foreground">
              {integration.description}
            </p>
            <CodeBlock code={integration.code} lang={integration.lang} />
            <Link
              href={integration.href}
              className="mt-3 text-sm font-medium hover:underline"
            >
              {integration.title} Guide &rarr;
            </Link>
          </div>
        ))}
      </div>

      <Button variant="link" size="sm" asChild>
        <Link href="/docs/quickstart">All integration patterns &rarr;</Link>
      </Button>
    </div>
  );
}
