package com.cutctx;

import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Map;

/**
 * Java client for the Cutctx AI context compression proxy.
 *
 * <p>Cutctx reduces LLM API token usage by 60-95% by compressing prompt context
 * before forwarding requests to the model provider.</p>
 *
 * <h3>Usage:</h3>
 * <pre>{@code
 * CutctxClient client = new CutctxClient("http://localhost:8080");
 *
 * // Proxy a request through Cutctx
 * HttpURLConnection conn = client.proxy("https://api.openai.com/v1/chat/completions");
 * conn.setRequestMethod("POST");
 * conn.setRequestProperty("Content-Type", "application/json");
 * conn.setDoOutput(true);
 * conn.getOutputStream().write(jsonBody.getBytes());
 *
 * // Read response
 * byte[] response = conn.getInputStream().readAllBytes();
 * }</pre>
 *
 * <h3>As HTTP Transport:</h3>
 * <pre>{@code
 * CutctxClient client = new CutctxClient("http://localhost:8080");
 * HttpTransport transport = new CutctxHttpTransport(client);
 * HttpClient httpClient = HttpClient.newBuilder()
 *     .connectTimeout(Duration.ofSeconds(10))
 *     .build();
 * }</pre>
 */
public class CutctxClient {

    private final String proxyUrl;
    private final int connectTimeoutMs;
    private final int readTimeoutMs;

    /**
     * Creates a new Cutctx client.
     *
     * @param proxyUrl URL of the running Cutctx proxy (e.g. "http://localhost:8080")
     */
    public CutctxClient(String proxyUrl) {
        this(proxyUrl, 10_000, 60_000);
    }

    /**
     * Creates a new Cutctx client with custom timeouts.
     *
     * @param proxyUrl        URL of the running Cutctx proxy
     * @param connectTimeoutMs Connection timeout in milliseconds
     * @param readTimeoutMs    Read timeout in milliseconds
     */
    public CutctxClient(String proxyUrl, int connectTimeoutMs, int readTimeoutMs) {
        if (proxyUrl == null || proxyUrl.isEmpty()) {
            throw new IllegalArgumentException("proxyUrl is required");
        }
        this.proxyUrl = proxyUrl.endsWith("/") ? proxyUrl.substring(0, proxyUrl.length() - 1) : proxyUrl;
        this.connectTimeoutMs = connectTimeoutMs;
        this.readTimeoutMs = readTimeoutMs;
    }

    /**
     * Proxies an HTTP request through the Cutctx proxy.
     *
     * <p>The original target URL is passed as a query parameter (_target) so the
     * proxy can forward the request to the correct upstream provider.</p>
     *
     * @param targetUrl The original URL to proxy (e.g. "https://api.openai.com/v1/chat/completions")
     * @return An HttpURLConnection configured to go through the proxy
     * @throws IOException If the connection cannot be established
     */
    public HttpURLConnection proxy(String targetUrl) throws IOException {
        String proxyEndpoint = buildProxyUrl(targetUrl);
        URL url = new URL(proxyEndpoint);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setConnectTimeout(connectTimeoutMs);
        conn.setReadTimeout(readTimeoutMs);
        return conn;
    }

    /**
     * Proxies an HTTP request with a specific method.
     *
     * @param targetUrl The original URL to proxy
     * @param method    HTTP method (GET, POST, PUT, DELETE, etc.)
     * @return An HttpURLConnection configured with the method
     * @throws IOException If the connection cannot be established
     */
    public HttpURLConnection proxy(String targetUrl, String method) throws IOException {
        HttpURLConnection conn = proxy(targetUrl);
        conn.setRequestMethod(method);
        return conn;
    }

    /**
     * Proxies an HTTP request with headers.
     *
     * @param targetUrl The original URL to proxy
     * @param method    HTTP method
     * @param headers   Request headers to set
     * @return An HttpURLConnection configured with method and headers
     * @throws IOException If the connection cannot be established
     */
    public HttpURLConnection proxy(String targetUrl, String method, Map<String, String> headers) throws IOException {
        HttpURLConnection conn = proxy(targetUrl, method);
        for (Map.Entry<String, String> entry : headers.entrySet()) {
            conn.setRequestProperty(entry.getKey(), entry.getValue());
        }
        return conn;
    }

    /**
     * Returns the proxy URL.
     */
    public String getProxyUrl() {
        return proxyUrl;
    }

    private String buildProxyUrl(String targetUrl) {
        try {
            String encoded = URLEncoder.encode(targetUrl, StandardCharsets.UTF_8.toString());
            return proxyUrl + "?_target=" + encoded;
        } catch (Exception e) {
            throw new IllegalArgumentException("Invalid target URL: " + targetUrl, e);
        }
    }
}
