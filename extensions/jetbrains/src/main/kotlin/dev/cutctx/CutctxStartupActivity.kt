package dev.cutctx
// TODO: rename file to CutCtxStartupActivity.kt

import com.intellij.openapi.components.service
import com.intellij.openapi.project.Project
import com.intellij.openapi.startup.ProjectActivity

class CutCtxStartupActivity : ProjectActivity {
    override suspend fun execute(project: Project) {
        val settings = CutCtxSettings.getInstance()
        if (!settings.autoStart) return
        val proxyService = service<ProxyService>()
        if (!proxyService.isRunning) {
            try {
                proxyService.start(settings.port, settings.binaryPath)
            } catch (e: Exception) {
                // Non-fatal: cutctx may not be installed
            }
        }
    }
}
