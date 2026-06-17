# Headroom Java SDK

Java client for the [Headroom](https://headroom.sh) AI context compression proxy.

Headroom reduces LLM API token usage by **60-95%** by compressing prompt context before forwarding requests to the model provider.

## Installation

### Maven

```xml
<dependency>
    <groupId>com.headroom</groupId>
    <artifactId>headroom-java</artifactId>
    <version>0.1.0</version>
</dependency>
```

### Gradle

```groovy
implementation 'com.headroom:headroom-java:0.1.0'
```

## Quick Start

```java
import com.headroom.HeadroomClient;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.URI;
import java.time.Duration;

public class Example {
    public static void main(String[] args) throws Exception {
        // 1. Create a Headroom client pointing to your proxy
        HeadroomClient client = new HeadroomClient("http://localhost:8080");

        // 2. Create an HTTP client
        HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

        // 3. Build your original request to the LLM provider
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create("https://api.openai.com/v1/chat/completions"))
            .header("Content-Type", "application/json")
            .header("Authorization", "Bearer sk-...")
            .POST(HttpRequest.BodyPublishers.ofString("""
                {
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "Hello!"}]
                }
                """))
            .build();

        // 4. Send through Headroom (auto-compresses context)
        HeadroomHttpTransport transport = new HeadroomHttpTransport(client);
        HttpRequest proxied = transport.rewrite(request);
        HttpResponse<String> response = httpClient.send(proxied, HttpResponse.BodyHandlers.ofString());

        System.out.println(response.body());
    }
}
```

## Architecture

```
Your App
  │
  ├── HeadroomClient.proxy("https://api.openai.com/...")
  │         │
  │         ▼
  │   Headroom Proxy (localhost:8080)
  │     ├── Compresses prompt context (60-95%)
  │     ├── Forwards to OpenAI/Anthropic/etc.
  │     └── Returns compressed response
  │
  └── Response (same as direct API call)
```

## API Reference

### `HeadroomClient`

| Method | Description |
|--------|-------------|
| `HeadroomClient(String proxyUrl)` | Create client with proxy URL |
| `HeadroomClient(String proxyUrl, int connectMs, int readMs)` | Create with custom timeouts |
| `proxy(String targetUrl)` | Get proxied HttpURLConnection |
| `proxy(String targetUrl, String method)` | Get proxied connection with HTTP method |
| `proxy(String targetUrl, String method, Map headers)` | Get proxied connection with headers |
| `getProxyUrl()` | Get the proxy URL |

### `HeadroomHttpTransport`

| Method | Description |
|--------|-------------|
| `HeadroomHttpTransport(HeadroomClient client)` | Create transport from client |
| `rewrite(HttpRequest request)` | Rewrite request to go through proxy |
| `send(HttpClient httpClient, HttpRequest request)` | Send request through proxy |

## Supported Providers

Works with any LLM provider:

- OpenAI (GPT-4, GPT-4o, etc.)
- Anthropic (Claude 3.5 Sonnet, Opus, etc.)
- Google (Gemini 1.5 Pro, etc.)
- AWS Bedrock
- Azure OpenAI
- Any OpenAI-compatible API

## Requirements

- Java 11+
- No external dependencies (uses `java.net.http` from JDK 11)

## License

Apache 2.0
