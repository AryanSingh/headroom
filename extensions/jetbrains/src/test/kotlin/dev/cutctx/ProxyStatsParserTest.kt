package dev.cutctx

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class ProxyStatsParserTest {
    @Test
    fun `parses the current since-restart stats contract`() {
        val stats = parseCutctxStats(
            """
            {
              "summary": {"scope": "since_restart", "saved": 1250},
              "cost": {"scope": "since_restart", "savings_usd": 0.03125},
              "requests": {"scope": "since_restart", "total": 7}
            }
            """.trimIndent()
        )

        assertEquals(1250, stats.tokensSaved)
        assertEquals(0.03125, stats.dollarsSaved)
        assertEquals(7, stats.requestsCompressed)
    }

    @Test
    fun `missing or malformed counters fail closed to zero`() {
        val stats = parseCutctxStats("""{"summary":{"saved":"not-a-number"}}""")

        assertEquals(0, stats.tokensSaved)
        assertEquals(0.0, stats.dollarsSaved)
        assertEquals(0, stats.requestsCompressed)
    }
}
