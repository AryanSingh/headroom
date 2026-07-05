package dev.cutctx

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.components.service
import com.intellij.openapi.ui.Messages

class ShowStatsAction : AnAction("Show CutCtx Stats") {
    override fun actionPerformed(e: AnActionEvent) {
        val settings = CutCtxSettings.getInstance()
        val stats = service<ProxyService>().getStats(settings.port)
        if (stats == null) {
            Messages.showInfoMessage("No stats available — is the proxy running?", "CutCtx Stats")
        } else {
            Messages.showInfoMessage(
                "Tokens saved: ${stats.tokensSaved.toLocaleString()}\n" +
                "Cost saved: \$${String.format("%.4f", stats.dollarsSaved)}\n" +
                "Requests compressed: ${stats.requestsCompressed}",
                "CutCtx Stats"
            )
        }
    }
    private fun Long.toLocaleString() = String.format("%,d", this)
}
