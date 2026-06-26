package dev.cutctx
// TODO: rename file to CutCtxConfigurable.kt

import com.intellij.openapi.options.Configurable
import com.intellij.ui.components.JBCheckBox
import com.intellij.ui.components.JBTextField
import com.intellij.util.ui.FormBuilder
import javax.swing.JComponent
import javax.swing.JPanel

class CutCtxConfigurable : Configurable {
    private val portField = JBTextField()
    private val pathField = JBTextField()
    private val autoStartBox = JBCheckBox("Auto-start proxy when IDE launches")

    override fun getDisplayName() = "CutCtx"

    override fun createComponent(): JComponent = FormBuilder.createFormBuilder()
        .addLabeledComponent("Proxy port:", portField)
        .addLabeledComponent("cutctx binary path:", pathField)
        .addComponent(autoStartBox)
        .addComponentFillVertically(JPanel(), 0)
        .panel

    override fun isModified(): Boolean {
        val s = CutCtxSettings.getInstance()
        return portField.text != s.port.toString() ||
               pathField.text != s.binaryPath ||
               autoStartBox.isSelected != s.autoStart
    }

    override fun apply() {
        val s = CutCtxSettings.getInstance()
        s.port = portField.text.toIntOrNull() ?: 8787
        s.binaryPath = pathField.text.ifBlank { "cutctx" }
        s.autoStart = autoStartBox.isSelected
    }

    override fun reset() {
        val s = CutCtxSettings.getInstance()
        portField.text = s.port.toString()
        pathField.text = s.binaryPath
        autoStartBox.isSelected = s.autoStart
    }
}
