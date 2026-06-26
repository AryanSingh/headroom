package io.cutctx;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.Interceptor;
import okhttp3.HttpUrl;
import java.io.IOException;
import java.time.Duration;

/**
 * Cutctx context compression client for Java.
 *
 * Routes HTTP requests through the Cutctx proxy to compress context
 * before it reaches the LLM provider.
 *
 * Usage:
 * <pre>{@code
 * CutctxConfig config = CutctxConfig.builder()
 *     .baseUrl("http://localhost:8080")
 *     .build();
 *
 * CutctxClient client = new CutctxClient(config);
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
public class CutctxClient {

    private final CutctxConfig config;
    private final OkHttpClient httpClient;

    /**
     * Create a new Cutctx client with the given configuration.
     */
    public CutctxClient(CutctxConfig config) {
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
    public CutctxClient() {
        this(CutctxConfig.builder().build());
    }

    /**
     * Wrap an existing OkHttpClient to route through Cutctx.
     * Returns a new OkHttpClient with the Cutctx proxy interceptor.
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
    public CutctxConfig getConfig() {
        return config;
    }

    /**
     * OkHttp interceptor that rewrites URLs to route through the Cutctx proxy.
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
