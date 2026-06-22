import * as vscode from 'vscode';
import { ProxyManager } from './proxy';
import { StatusBarManager } from './statusBar';
import { StatsPoller } from './stats';
import { AIExtensionConfigurator } from './configurator';

let proxyManager: ProxyManager;
let statusBar: StatusBarManager;
let statsPoller: StatsPoller;

export async function activate(context: vscode.ExtensionContext) {
    const config = vscode.workspace.getConfiguration('cutctx');
    const port = config.get<number>('port', 8787);
    const binaryPath = config.get<string>('binaryPath', 'cutctx');
    const autoStart = config.get<boolean>('autoStart', true);

    proxyManager = new ProxyManager(binaryPath, port);
    statsPoller = new StatsPoller(port);
    statusBar = new StatusBarManager(port, proxyManager, statsPoller);
    statusBar.show();

    context.subscriptions.push(
        vscode.commands.registerCommand('cutctx.startProxy', async () => {
            try {
                await proxyManager.start();
                statsPoller.start();
                statusBar.update();
                vscode.window.showInformationMessage(`CutCtx proxy started on port ${port}`);
            } catch (err) {
                vscode.window.showErrorMessage(`Failed to start CutCtx: ${err}`);
            }
        }),
        vscode.commands.registerCommand('cutctx.stopProxy', async () => {
            await proxyManager.stop();
            statsPoller.stop();
            statusBar.update();
            vscode.window.showInformationMessage('CutCtx proxy stopped');
        }),
        vscode.commands.registerCommand('cutctx.showStats', async () => {
            const stats = statsPoller.getLatestStats();
            if (!stats) {
                vscode.window.showInformationMessage('No stats available — is the proxy running?');
                return;
            }
            vscode.window.showInformationMessage(
                `CutCtx Stats: ${stats.tokensSaved.toLocaleString()} tokens saved, $${stats.dollarsSaved.toFixed(4)} saved`
            );
        }),
        vscode.commands.registerCommand('cutctx.configureExtension', async () => {
            const configurator = new AIExtensionConfigurator(port);
            await configurator.configure();
        }),
        statusBar
    );

    if (autoStart) {
        try {
            if (!proxyManager.isRunning()) {
                await proxyManager.start();
                statsPoller.start();
                statusBar.update();
            }
        } catch (err) {
            // Non-fatal: cutctx may not be installed
        }
    }
}

export function deactivate() {
    proxyManager?.stop();
    statsPoller?.stop();
}
