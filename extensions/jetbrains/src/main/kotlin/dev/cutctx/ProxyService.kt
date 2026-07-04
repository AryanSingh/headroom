package dev.cutctx

import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.logger
import com.intellij.util.net.HttpConfigurable
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit

data class CutCtxStats(
    val tokensSaved: Long,
    val dollarsSaved: Double,
    val requestsCompressed: Int
)

@Service(Service.Level.APP)
class ProxyService {
    private val log = logger<ProxyService>()
    private var process: Process? = null
    private var latestStats: CutCtxStats? = null
    private var activePort: Int = 8787

    @Volatile private var _isRunning = false
    val isRunning: Boolean get() = _isRunning

    fun start(port: Int = 8787, binaryPath: String = "cutctx") {
        if (_isRunning) return
        activePort = port
        try {
            process = ProcessBuilder(binaryPath, "proxy", "--port", port.toString())
                .redirectErrorStream(true)
                .start()
            process?.onExit()?.thenRun { _isRunning = false }
            waitForReady(port, 30)
            
            val httpConfigurable = HttpConfigurable.getInstance()
            httpConfigurable.USE_HTTP_PROXY = true
            httpConfigurable.PROXY_HOST = "127.0.0.1"
            httpConfigurable.PROXY_PORT = port

            _isRunning = true
            log.info("CutCtx proxy started on port $port")
        } catch (e: Exception) {
            process?.destroy()
            process = null
            log.warn("Failed to start CutCtx proxy: ${e.message}")
            throw e
        }
    }

    fun stop() {
        _isRunning = false
        
        val httpConfigurable = HttpConfigurable.getInstance()
        httpConfigurable.USE_HTTP_PROXY = false
        
        process?.let {
            it.destroy()
            if (!it.waitFor(5, TimeUnit.SECONDS)) it.destroyForcibly()
        }
        process = null
    }

    fun getStats(port: Int = 8787): CutCtxStats? {
        return try {
            val url = URL("http://127.0.0.1:$port/stats")
            val conn = url.openConnection() as HttpURLConnection
            conn.connectTimeout = 2000
            conn.readTimeout = 3000
            if (conn.responseCode == 200) {
                val body = conn.inputStream.bufferedReader().readText()
                parseStats(body).also { latestStats = it }
            } else null
        } catch (e: Exception) { null }
    }

    fun getLatestStats(): CutCtxStats? = latestStats

    private fun checkLivez(port: Int = 8787): Boolean {
        return try {
            val url = URL("http://127.0.0.1:$port/livez")
            val conn = url.openConnection() as HttpURLConnection
            conn.connectTimeout = 1000
            conn.readTimeout = 1000
            conn.responseCode == 200
        } catch (e: Exception) { false }
    }

    private fun waitForReady(port: Int, timeoutSeconds: Int) {
        val deadline = System.currentTimeMillis() + timeoutSeconds * 1000L
        while (System.currentTimeMillis() < deadline) {
            if (checkLivez(port)) return
            Thread.sleep(500)
        }
        throw RuntimeException("CutCtx proxy did not become ready within ${timeoutSeconds}s")
    }

    private fun parseStats(json: String): CutCtxStats {
        // Simple regex-based parsing to avoid adding a JSON dependency
        fun extractLong(key: String): Long =
            Regex(""""$key"\s*:\s*(\d+)""").find(json)?.groupValues?.get(1)?.toLongOrNull() ?: 0L
        fun extractDouble(key: String): Double =
            Regex(""""$key"\s*:\s*([\d.]+)""").find(json)?.groupValues?.get(1)?.toDoubleOrNull() ?: 0.0
        return CutCtxStats(
            tokensSaved = extractLong("total_tokens_removed"),
            dollarsSaved = extractDouble("total_saved_usd"),
            requestsCompressed = extractLong("requests_compressed").toInt()
        )
    }
}
