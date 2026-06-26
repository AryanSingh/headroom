package dev.cutctx
// TODO: rename file to CutCtxSettings.kt

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.*

@State(name = "CutCtxSettings", storages = [Storage("cutctx.xml")])
@Service(Service.Level.APP)
class CutCtxSettings : PersistentStateComponent<CutCtxSettings.State> {
    data class State(
        var port: Int = 8787,
        var binaryPath: String = "cutctx",
        var autoStart: Boolean = true
    )

    private var state = State()
    var port: Int get() = state.port; set(v) { state.port = v }
    var binaryPath: String get() = state.binaryPath; set(v) { state.binaryPath = v }
    var autoStart: Boolean get() = state.autoStart; set(v) { state.autoStart = v }

    override fun getState(): State = state
    override fun loadState(state: State) { this.state = state }

    companion object {
        fun getInstance(): CutCtxSettings =
            ApplicationManager.getApplication().service()
    }
}
