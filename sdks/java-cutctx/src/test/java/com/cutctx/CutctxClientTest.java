package com.cutctx;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CutctxClientTest {

    @Test
    void testConstructor() {
        CutctxClient client = new CutctxClient("http://localhost:8080");
        assertEquals("http://localhost:8080", client.getProxyUrl());
    }

    @Test
    void testConstructorStripsTrailingSlash() {
        CutctxClient client = new CutctxClient("http://localhost:8080/");
        assertEquals("http://localhost:8080", client.getProxyUrl());
    }

    @Test
    void testConstructorWithTimeouts() {
        CutctxClient client = new CutctxClient("http://localhost:8080", 5000, 30000);
        assertEquals("http://localhost:8080", client.getProxyUrl());
    }

    @Test
    void testConstructorNullUrl() {
        assertThrows(IllegalArgumentException.class, () -> new CutctxClient(null));
    }

    @Test
    void testConstructorEmptyUrl() {
        assertThrows(IllegalArgumentException.class, () -> new CutctxClient(""));
    }

    @Test
    void testTransportConstructor() {
        CutctxClient client = new CutctxClient("http://localhost:8080");
        CutctxHttpTransport transport = new CutctxHttpTransport(client);
        assertNotNull(transport);
    }

    @Test
    void testTransportNullClient() {
        assertThrows(IllegalArgumentException.class, () -> new CutctxHttpTransport(null));
    }
}
