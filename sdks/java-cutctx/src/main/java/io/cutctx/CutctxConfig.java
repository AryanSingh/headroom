package io.cutctx;

import java.net.URI;
import java.time.Duration;

/**
 * Configuration for the Cutctx client.
 *
 * Use the builder pattern to create configurations:
 * <pre>{@code
 * CutctxConfig config = CutctxConfig.builder()
 *     .baseUrl("http://localhost:8080")
 *     .apiKey("hrk_...")
 *     .timeout(Duration.ofSeconds(30))
 *     .build();
 * }</pre>
 */
public class CutctxConfig {

    private final URI baseUrl;
    private final String apiKey;
    private final Duration timeout;
    private final boolean compressionEnabled;

    private CutctxConfig(Builder builder) {
        this.baseUrl = URI.create(builder.baseUrl);
        this.apiKey = builder.apiKey;
        this.timeout = builder.timeout;
        this.compressionEnabled = builder.compressionEnabled;
    }

    public static Builder builder() {
        return new Builder();
    }

    public URI getBaseUrl() { return baseUrl; }
    public String getApiKey() { return apiKey; }
    public Duration getTimeout() { return timeout; }
    public boolean isCompressionEnabled() { return compressionEnabled; }

    public static class Builder {
        private String baseUrl = "http://localhost:8080";
        private String apiKey = "";
        private Duration timeout = Duration.ofSeconds(30);
        private boolean compressionEnabled = true;

        public Builder baseUrl(String baseUrl) {
            this.baseUrl = baseUrl;
            return this;
        }

        public Builder apiKey(String apiKey) {
            this.apiKey = apiKey;
            return this;
        }

        public Builder timeout(Duration timeout) {
            this.timeout = timeout;
            return this;
        }

        public Builder compressionEnabled(boolean enabled) {
            this.compressionEnabled = enabled;
            return this;
        }

        public CutctxConfig build() {
            return new CutctxConfig(this);
        }
    }
}
