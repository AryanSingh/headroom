package io.headroom;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.Interceptor;
import okhttp3.HttpUrl;
import java.io.IOException;
import java.time.Duration;

/**
 * Headroom context compression client for Java.
 *
 * Routes HTTP requests through the Headroom proxy to compress context
 * before it reaches the LLM provider.
 *
 * Usage:
 * <pre>{@code
 * HeadroomConfig config = HeadroomConfig.builder()
 *     .baseUrl("http://localhost:8080")
 *     .build();
 *
 * HeadroomClient client = new HeadroomClient(config);
 * OkHttpClient llmClient = client.wrapHttpClient();
 *
 * Request request = new Request.Builder()
 *     .url("https://api.openai.com/v1/chat/completions")
 *     .post(body)
 *     .build();
 *
 * Response response = llmClient.newCall(request).execute();
 * }</pre>
 */
public class HeadroomClient {

    private final HeadroomConfig config;
    private final OkHttpClient httpClient;

    /**
     * Create a new Headroom client with the given configuration.
     */
    public HeadroomClient(HeadroomConfig config) {
        this.config = config;
        this.httpClient = new OkHttpClient.Builder()
            .connectTimeout(config.getTimeout())
            .readTimeout(config.getTimeout())
            .addInterceptor(this::proxyIntercept)
            .build();
    }

    /**
     * Create a client with default settings (localhost:8080).
     */
    public HeadroomClient() {
        this(HeadroomConfig.builder().build());
    }

    /**
     * Wrap an existing OkHttpClient to route through Headroom.
     * Returns a new OkHttpClient with the Headroom proxy interceptor.
     */
    public OkHttpClient wrapHttpClient() {
        return new OkHttpClient.Builder()
            .connectTimeout(config.getTimeout())
            .readTimeout(config.getTimeout())
            .addInterceptor(this::proxyIntercept)
            .build();
    }

    /**
     * Wrap an existing OkHttpClient with a custom base configuration.
     */
    public OkHttpClient wrapHttpClient(OkHttpClient existing) {
        return existing.newBuilder()
            .addInterceptor(this::proxyIntercept)
            .build();
    }

    /**
     * Get the underlying OkHttpClient for direct requests.
     */
    public OkHttpClient getHttpClient() {
        return httpClient;
    }

    /**
     * Get the configuration.
     */
    public HeadroomConfig getConfig() {
        return config;
    }

    /**
     * OkHttp interceptor that rewrites URLs to route through the Headroom proxy.
     */
    private okhttp3.Response proxyIntercept(Interceptor.Chain chain) throws IOException {
        Request original = chain.request();
        HttpUrl originalUrl = original.url();

        // Rewrite URL to go through the proxy with _target parameter
        HttpUrl proxyUrl = originalUrl.newBuilder()
            .scheme(config.getBaseUrl().getScheme())
            .host(config.getBaseUrl().getHost())
            .port(config.getBaseUrl().getPort())
            .addQueryParameter("_target", originalUrl.toString())
            .build();

        Request proxyRequest = original.newBuilder()
            .url(proxyUrl)
            .build();

        return chain.proceed(proxyRequest);
    }
}
