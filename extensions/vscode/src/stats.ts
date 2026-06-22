import * as http from 'http';

export interface CutCtxStats {
    tokensSaved: number;
    dollarsSaved: number;
    requestsCompressed: number;
}

export class StatsPoller {
    private timer: NodeJS.Timeout | null = null;
    private latest: CutCtxStats | null = null;

    constructor(private readonly port: number) {}

    start(): void {
        if (this.timer) return;
        this.poll();
        this.timer = setInterval(() => this.poll(), 30000);
    }

    stop(): void {
        if (this.timer) { clearInterval(this.timer); this.timer = null; }
    }

    getLatestStats(): CutCtxStats | null {
        return this.latest;
    }

    private poll(): void {
        const req = http.get(`http://127.0.0.1:${this.port}/stats`, res => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    const json = JSON.parse(data);
                    const summary = json?.summary;
                    this.latest = {
                        tokensSaved: summary?.compression?.total_tokens_removed ?? 0,
                        dollarsSaved: summary?.cost?.total_saved_usd ?? 0,
                        requestsCompressed: summary?.compression?.requests_compressed ?? 0,
                    };
                } catch {}
            });
        });
        req.on('error', () => {});
        req.setTimeout(3000, () => req.destroy());
    }
}
