package com.headroom;

import java.io.IOException;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.URI;

/**
 * An HTTP interceptor that routes all requests through the Headroom proxy.
 *
 * <p>Use this with Java 11+ HttpClient to transparently compress all LLM API calls:</p>
 *
 * <pre>{@code
 * HeadroomClient client = new HeadroomClient("http://localhost:8080");
 * HeadroomHttpTransport transport = new HeadroomHttpTransport(client);
 *
 * HttpClient httpClient = HttpClient.newBuilder()
 *     .connectTimeout(Duration.ofSeconds(10))
 *     .build();
 *
 * // All requests through httpClient will be proxied through Headroom
 * HttpRequest request = HttpRequest.newBuilder()
 *     .uri(URI.create("https://api.openai.com/v1/chat/completions"))
 *     .header("Content-Type", "application/json")
 *     .POST(HttpRequest.BodyPublishers.ofString(jsonBody))
 *     .build();
 *
 * HttpResponse<String> response = transport.send(httpClient, request);
 * }</pre>
 */
public class HeadroomHttpTransport {

    private final HeadroomClient client;

    /**
     * Creates a new transport interceptor.
     *
     * @param client The Headroom client to route requests through
     */
    public HeadroomHttpTransport(HeadroomClient client) {
        if (client == null) {
            throw new IllegalArgumentException("client is required");
        }
        this.client = client;
    }

    /**
     * Rewrites an HttpRequest to go through the Headroom proxy.
     *
     * @param request The original request
     * @return A new request routed through the proxy
     */
    public HttpRequest rewrite(HttpRequest request) {
        String originalUri = request.uri().toString();
        String proxyUrl = client.getProxyUrl() + "?_target=" + encodeUrl(originalUri);

        HttpRequest.Builder builder = HttpRequest.newBuilder()
            .uri(URI.create(proxyUrl))
            .timeout(request.timeout().orElse(java.time.Duration.ofSeconds(60)))
            .version(request.version().orElse(HttpClient.Version.HTTP_1_1));

        // Copy headers
        request.headers().map().forEach((key, values) -> {
            values.forEach(value -> builder.header(key, value));
        });

        // Copy method and body
        request.bodyPublisher().ifPresent(body -> {
            builder.method(request.method(), body);
        });

        return builder.build();
    }

    /**
     * Sends a request through the Headroom proxy.
     *
     * @param httpClient The HTTP client to use
     * @param request    The original request
     * @return The response from the upstream provider
     * @throws IOException          If an I/O error occurs
     * @throws InterruptedException If the thread is interrupted
     */
    public <T> HttpResponse<T> send(HttpClient httpClient, HttpRequest request)
            throws IOException, InterruptedException {
        HttpRequest rewritten = rewrite(request);
        return httpClient.send(rewritten, HttpResponse.BodyHandlers.discarding());
    }

    private String encodeUrl(String url) {
        try {
            return java.net.URLEncoder.encode(url, java.nio.charset.StandardCharsets.UTF_8.toString());
        } catch (Exception e) {
            throw new IllegalArgumentException("Invalid URL: " + url, e);
        }
    }
}
