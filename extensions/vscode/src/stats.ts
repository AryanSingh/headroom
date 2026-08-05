import * as http from 'http';

export interface CutctxStats {
    tokensSaved: number;
    dollarsSaved: number;
    requestsCompressed: number;
}

function finiteNumber(value: unknown): number {
    return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

export function parseStatsPayload(payload: unknown): CutctxStats {
    const root = payload && typeof payload === 'object'
        ? payload as Record<string, unknown>
        : {};
    const summary = root.summary && typeof root.summary === 'object'
        ? root.summary as Record<string, unknown>
        : {};
    const cost = root.cost && typeof root.cost === 'object'
        ? root.cost as Record<string, unknown>
        : {};
    const requests = root.requests && typeof root.requests === 'object'
        ? root.requests as Record<string, unknown>
        : {};
    return {
        tokensSaved: finiteNumber(summary.saved),
        dollarsSaved: finiteNumber(cost.savings_usd),
        requestsCompressed: finiteNumber(requests.total),
    };
}

export class StatsPoller {
    private timer: NodeJS.Timeout | null = null;
    private latest: CutctxStats | null = null;

    constructor(private readonly port: number) {}

    start(): void {
        if (this.timer) return;
        this.poll();
        this.timer = setInterval(() => this.poll(), 30000);
    }

    stop(): void {
        if (this.timer) { clearInterval(this.timer); this.timer = null; }
    }

    getLatestStats(): CutctxStats | null {
        return this.latest;
    }

    private poll(): void {
        const req = http.get(`http://127.0.0.1:${this.port}/stats`, res => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    const json = JSON.parse(data);
                    this.latest = parseStatsPayload(json);
                } catch {}
            });
        });
        req.on('error', () => {});
        req.setTimeout(3000, () => req.destroy());
    }
}
