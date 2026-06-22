package dev.cutctx

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.components.service
import com.intellij.openapi.ui.Messages

class StopProxyAction : AnAction("Stop CutCtx Proxy") {
    override fun actionPerformed(e: AnActionEvent) {
        service<ProxyService>().stop()
        Messages.showInfoMessage("CutCtx proxy stopped.", "CutCtx")
    }
}
