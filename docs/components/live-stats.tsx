import Link from 'next/link';

import { fetchCommunityStats, fmtNum, fmtUsd } from '@/lib/telemetry';

/**
 * Renders the published community snapshot bundled with the docs site.
 */
export async function LiveStats() {
  const data = await fetchCommunityStats();
  const stats = [
    { value: fmtNum(data.total_tokens_saved), label: 'Tokens Saved' },
    { value: fmtUsd(data.total_cost_saved), label: 'Cost Saved' },
    { value: fmtNum(data.total_requests), label: 'Requests Optimized' },
    { value: fmtNum(data.unique_instances), label: 'Active Instances' },
  ];

  return (
    <div className="not-prose">
      <div className="my-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="flex flex-col items-center rounded-xl border border-fd-border bg-fd-card p-5"
          >
            <span className="text-2xl font-bold text-fd-foreground">
              {stat.value}
            </span>
            <span className="mt-1 text-sm text-fd-muted-foreground">
              {stat.label}
            </span>
          </div>
        ))}
      </div>

      <p className="mb-3 text-sm text-fd-muted-foreground">
        Snapshot from the latest published anonymous community telemetry bundle.
      </p>

      <Link
        href="/docs/community-savings"
        className="text-sm font-medium hover:underline"
      >
        View detailed charts and breakdowns &rarr;
      </Link>
    </div>
  );
}
