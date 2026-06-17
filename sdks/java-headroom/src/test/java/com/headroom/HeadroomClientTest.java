package com.headroom;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class HeadroomClientTest {

    @Test
    void testConstructor() {
        HeadroomClient client = new HeadroomClient("http://localhost:8080");
        assertEquals("http://localhost:8080", client.getProxyUrl());
    }

    @Test
    void testConstructorStripsTrailingSlash() {
        HeadroomClient client = new HeadroomClient("http://localhost:8080/");
        assertEquals("http://localhost:8080", client.getProxyUrl());
    }

    @Test
    void testConstructorWithTimeouts() {
        HeadroomClient client = new HeadroomClient("http://localhost:8080", 5000, 30000);
        assertEquals("http://localhost:8080", client.getProxyUrl());
    }

    @Test
    void testConstructorNullUrl() {
        assertThrows(IllegalArgumentException.class, () -> new HeadroomClient(null));
    }

    @Test
    void testConstructorEmptyUrl() {
        assertThrows(IllegalArgumentException.class, () -> new HeadroomClient(""));
    }

    @Test
    void testTransportConstructor() {
        HeadroomClient client = new HeadroomClient("http://localhost:8080");
        HeadroomHttpTransport transport = new HeadroomHttpTransport(client);
        assertNotNull(transport);
    }

    @Test
    void testTransportNullClient() {
        assertThrows(IllegalArgumentException.class, () -> new HeadroomHttpTransport(null));
    }
}
