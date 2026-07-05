package dev.cutctx

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.components.service
import com.intellij.openapi.ui.Messages

class StartProxyAction : AnAction("Start CutCtx Proxy") {
    override fun actionPerformed(e: AnActionEvent) {
        val settings = CutCtxSettings.getInstance()
        val proxyService = service<ProxyService>()
        com.intellij.openapi.application.ApplicationManager.getApplication().executeOnPooledThread {
            try {
                proxyService.start(settings.port, settings.binaryPath)
                com.intellij.openapi.application.ApplicationManager.getApplication().invokeLater {
                    Messages.showInfoMessage("CutCtx proxy started on port ${settings.port}", "CutCtx")
                }
            } catch (ex: Exception) {
                com.intellij.openapi.application.ApplicationManager.getApplication().invokeLater {
                    Messages.showErrorDialog("Failed to start CutCtx: ${ex.message}", "CutCtx Error")
                }
            }
        }
    }
}
