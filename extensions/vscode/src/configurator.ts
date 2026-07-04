import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export class AIExtensionConfigurator {
    constructor(private readonly port: number) {}

    async configure(): Promise<void> {
        const detected: string[] = ['VS Code / Cursor Global Proxy', 'GitHub Copilot'];

        if (vscode.extensions.getExtension('saoudrizwan.claude-dev') ||
            vscode.extensions.getExtension('cline.cline')) detected.push('Cline');
        if (vscode.extensions.getExtension('Continue.continue')) detected.push('Continue');

        const choice = await vscode.window.showQuickPick(
            detected.map(ext => ({ label: ext, description: `Configure ${ext} to use Cutctx proxy` })),
            { placeHolder: 'Select target to configure' }
        );

        if (!choice) return;

        if (choice.label === 'VS Code / Cursor Global Proxy') await this.configureGlobalProxy();
        if (choice.label === 'GitHub Copilot') await this.configureCopilot();
        if (choice.label === 'Cline') await this.configureCline();
        if (choice.label === 'Continue') await this.configureContinue();
    }

    private async configureGlobalProxy(): Promise<void> {
        const config = vscode.workspace.getConfiguration('http');
        const proxyUrl = `http://127.0.0.1:${this.port}`;
        await config.update('proxy', proxyUrl, vscode.ConfigurationTarget.Global);
        await config.update('proxyStrictSSL', false, vscode.ConfigurationTarget.Global);
        vscode.window.showInformationMessage(`Global http.proxy set to ${proxyUrl} (Strict SSL disabled).`);
    }

    private async configureCopilot(): Promise<void> {
        const config = vscode.workspace.getConfiguration('github.copilot');
        const proxyUrl = `http://127.0.0.1:${this.port}`;
        const advanced = config.get<Record<string, unknown>>('advanced') || {};
        advanced['debug.overrideProxyUrl'] = proxyUrl;
        advanced['debug.chatOverrideProxyUrl'] = proxyUrl;
        await config.update('advanced', advanced, vscode.ConfigurationTarget.Global);
        vscode.window.showInformationMessage(`GitHub Copilot proxy overrides set to ${proxyUrl}.`);
    }

    private async configureCline(): Promise<void> {
        const baseUrl = `http://127.0.0.1:${this.port}/v1`;
        const result = await vscode.window.showInformationMessage(
            `Set your Cline API base URL to: ${baseUrl}`,
            'Copy URL', 'Open Cline Settings'
        );
        if (result === 'Copy URL') {
            await vscode.env.clipboard.writeText(baseUrl);
            vscode.window.showInformationMessage('URL copied to clipboard');
        } else if (result === 'Open Cline Settings') {
            await vscode.commands.executeCommand('workbench.action.openSettings', 'cline');
        }
    }

    private async configureContinue(): Promise<void> {
        const configPath = path.join(os.homedir(), '.continue', 'config.json');
        const openaiBase = `http://127.0.0.1:${this.port}/v1`;

        try {
            let config: Record<string, unknown> = {};
            if (fs.existsSync(configPath)) {
                config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
            }

            // Only patch OpenAI-compatible models (those with provider 'openai' or existing apiBase)
            if (Array.isArray(config.models)) {
                config.models = (config.models as Record<string, unknown>[]).map(m => {
                    const provider = (m.provider as string) ?? '';
                    if (provider === 'openai' || provider === 'openai-native' || m.apiBase) {
                        return { ...m, apiBase: openaiBase };
                    }
                    return m;
                });
            }

            fs.mkdirSync(path.dirname(configPath), { recursive: true });
            fs.writeFileSync(configPath, JSON.stringify(config, null, 2) + '\n');
            vscode.window.showInformationMessage(`Continue configured to use Cutctx proxy. Reload VS Code to apply.`);
        } catch (err) {
            vscode.window.showErrorMessage(`Failed to configure Continue: ${err}`);
        }
    }
}
