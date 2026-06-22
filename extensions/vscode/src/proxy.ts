import * as child_process from 'child_process';
import * as http from 'http';

export class ProxyManager {
    private process: child_process.ChildProcess | null = null;
    private _running = false;

    constructor(private readonly binaryPath: string, private readonly port: number) {}

    async start(): Promise<void> {
        if (this._running) return;

        this.process = child_process.spawn(this.binaryPath, ['proxy', '--port', String(this.port)], {
            detached: false,
            stdio: ['ignore', 'pipe', 'pipe']
        });

        this.process.on('exit', () => { this._running = false; this.process = null; });

        try {
            await this.waitForReady(30000);
        } catch (err) {
            this.process.kill('SIGTERM');
            this.process = null;
            throw err;
        }
        this._running = true;
    }

    async stop(): Promise<void> {
        if (this.process) {
            this.process.kill('SIGTERM');
            this.process = null;
        }
        this._running = false;
    }

    isRunning(): boolean {
        return this._running;
    }

    private waitForReady(timeoutMs: number): Promise<void> {
        return new Promise((resolve, reject) => {
            const start = Date.now();
            const poll = () => {
                this.checkLivez().then(alive => {
                    if (alive) { resolve(); return; }
                    if (Date.now() - start > timeoutMs) { reject(new Error('Proxy startup timed out')); return; }
                    setTimeout(poll, 500);
                });
            };
            setTimeout(poll, 500);
        });
    }

    private checkLivez(): Promise<boolean> {
        return new Promise(resolve => {
            const req = http.get(`http://127.0.0.1:${this.port}/livez`, res => {
                resolve(res.statusCode === 200);
                res.resume();
            });
            req.on('error', () => resolve(false));
            req.setTimeout(1000, () => { req.destroy(); resolve(false); });
        });
    }
}
