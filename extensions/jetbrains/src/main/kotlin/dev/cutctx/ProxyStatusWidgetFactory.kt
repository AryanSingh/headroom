package dev.cutctx

import com.intellij.openapi.components.service
import com.intellij.openapi.project.Project
import com.intellij.openapi.util.Disposer
import com.intellij.openapi.wm.StatusBarWidget
import com.intellij.openapi.wm.StatusBarWidgetFactory
import com.intellij.util.concurrency.AppExecutorUtil
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit

class ProxyStatusWidgetFactory : StatusBarWidgetFactory {
    override fun getId() = "dev.cutctx.statusbar"
    override fun getDisplayName() = "CutCtx"
    override fun createWidget(project: Project): StatusBarWidget = ProxyStatusWidget(project)
}

class ProxyStatusWidget(private val project: Project) :
    StatusBarWidget, StatusBarWidget.TextPresentation {

    private val proxyService get() = service<ProxyService>()
    private val settings get() = CutCtxSettings.getInstance()
    private var statusBar: com.intellij.openapi.wm.StatusBar? = null
    private var future: ScheduledFuture<*>? = null

    override fun ID() = "dev.cutctx.statusbar"
    override fun getPresentation(): StatusBarWidget.WidgetPresentation = this
    override fun getAlignment() = 0f

    override fun getText(): String {
        val stats = proxyService.getLatestStats()
        return if (proxyService.isRunning) {
            val saved = stats?.tokensSaved ?: 0
            if (saved > 0) {
                val k = if (saved >= 1000) "${saved / 1000}K" else saved.toString()
                "⚡ CutCtx: $k saved"
            } else "⚡ CutCtx: Active"
        } else "⚡ CutCtx: Off"
    }

    override fun getTooltipText(): String {
        val stats = proxyService.getLatestStats()
        return if (proxyService.isRunning) {
            "CutCtx proxy running on port ${settings.port}. " +
            "Tokens saved: ${stats?.tokensSaved ?: 0}, " +
            "Cost saved: \$${String.format("%.4f", stats?.dollarsSaved ?: 0.0)}"
        } else "CutCtx proxy stopped. Go to Tools > CutCtx > Start."
    }

    override fun install(statusBar: com.intellij.openapi.wm.StatusBar) {
        this.statusBar = statusBar
        com.intellij.openapi.util.Disposer.register(statusBar as com.intellij.openapi.Disposable, this)
        future = AppExecutorUtil.getAppScheduledExecutorService()
            .scheduleWithFixedDelay({
                proxyService.getStats(settings.port)
                statusBar.updateWidget(ID())
            }, 0, 30, TimeUnit.SECONDS)
    }

    override fun dispose() {
        future?.cancel(false)
        statusBar = null
    }
}
