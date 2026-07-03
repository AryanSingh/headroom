import { Map } from '@/components/map';

const stats = [
  { value: '87%', label: 'Avg Reduction' },
  { value: '100%', label: 'Accuracy' },
  { value: '6', label: 'Algorithms' },
  { value: '100+', label: 'Providers' },
];

export function StatsSection() {
  return (
    <section className="@container relative overflow-hidden py-12 not-prose md:py-20">
      <div className="mask-radial-to-75% absolute inset-0 hidden items-center justify-center max-md:hidden">
        <div className="w-[140%] min-w-[900px]">
          <Map />
        </div>
      </div>

      <div className="mx-auto max-w-5xl px-6">
        <div className="relative rounded-xl bg-fd-card p-6 shadow-xl ring-1 ring-fd-border shadow-black/6.5 sm:p-10 md:max-w-3/5 lg:max-w-1/2">
          <div className="mb-8 space-y-4">
            <h2 className="text-3xl font-semibold text-balance text-fd-muted-foreground">
              Context control plane for{' '}
              <strong className="font-semibold text-fd-foreground">AI agents</strong>
            </h2>
            <p className="text-fd-muted-foreground">
              Govern what reaches the model, attribute spend, remember shared
              context, and compress when it helps.{' '}
              <strong className="font-semibold text-fd-foreground">
                Local-first, reversible, and provider-neutral.
              </strong>
            </p>
          </div>

          <div className="grid grid-cols-2 gap-1 **:text-center *:rounded-md *:bg-fd-muted/50 *:p-4">
            {stats.map((stat) => (
              <div key={stat.label} className="space-y-2 *:block">
                <span className="text-3xl font-semibold">{stat.value}</span>
                <p className="text-xs text-fd-muted-foreground">
                  <strong className="font-medium text-fd-foreground">
                    {stat.label}
                  </strong>
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
