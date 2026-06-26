import * as vscode from 'vscode';
import { ProxyManager } from './proxy';
import { StatsPoller } from './stats';

export class StatusBarManager implements vscode.Disposable {
    private item: vscode.StatusBarItem;
    private timer: NodeJS.Timeout | null = null;

    constructor(
        private readonly port: number,
        private readonly proxy: ProxyManager,
        private readonly stats: StatsPoller
    ) {
        this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
        this.item.command = 'cutctx.showStats';
    }

    show(): void {
        this.update();
        this.item.show();
        this.timer = setInterval(() => this.update(), 15000);
    }

    update(): void {
        const running = this.proxy.isRunning();
        const latest = this.stats.getLatestStats();
        if (running && latest && latest.tokensSaved > 0) {
            const k = latest.tokensSaved >= 1000 ? `${(latest.tokensSaved / 1000).toFixed(1)}K` : String(latest.tokensSaved);
            this.item.text = `$(check) Cutctx: ${k} tokens saved`;
            this.item.tooltip = `$${latest.dollarsSaved.toFixed(4)} saved across ${latest.requestsCompressed} requests\nClick for details`;
            this.item.backgroundColor = undefined;
        } else if (running) {
            this.item.text = `$(check) Cutctx: Active`;
            this.item.tooltip = `Proxy running on port ${this.port}`;
            this.item.backgroundColor = undefined;
        } else {
            this.item.text = `$(circle-slash) Cutctx: Off`;
            this.item.tooltip = `Click: Cutctx.showStats | Run 'Cutctx: Start Proxy' to enable`;
            this.item.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        }
    }

    dispose(): void {
        if (this.timer) clearInterval(this.timer);
        this.item.dispose();
    }
}
