import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export class AIExtensionConfigurator {
    constructor(private readonly port: number) {}

    async configure(): Promise<void> {
        const detected: string[] = [];

        if (vscode.extensions.getExtension('saoudrizwan.claude-dev') ||
            vscode.extensions.getExtension('cline.cline')) detected.push('Cline');
        if (vscode.extensions.getExtension('Continue.continue')) detected.push('Continue');

        if (detected.length === 0) {
            vscode.window.showInformationMessage(
                'No supported AI extensions detected (Cline, Continue). ' +
                `Set your API base URL to http://127.0.0.1:${this.port}/v1 manually.`
            );
            return;
        }

        const choice = await vscode.window.showQuickPick(
            detected.map(ext => ({ label: ext, description: `Configure ${ext} to use Cutctx proxy` })),
            { placeHolder: 'Select AI extension to configure' }
        );

        if (!choice) return;

        if (choice.label === 'Cline') await this.configureCline();
        if (choice.label === 'Continue') await this.configureContinue();
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
