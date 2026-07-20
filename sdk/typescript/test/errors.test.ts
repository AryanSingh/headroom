/**
 * Tests for error hierarchy — matches Python test_exceptions.py patterns.
 */
import { describe, it, expect } from "vitest";
import {
  CutctxError,
  CutctxConnectionError,
  CutctxAuthError,
  CutctxCompressError,
  ConfigurationError,
  ProviderError,
  StorageError,
  TokenizationError,
  CacheError,
  ValidationError,
  TransformError,
  mapProxyError,
} from "../src/errors.js";

describe("CutctxError", () => {
  it("has correct name and message", () => {
    const err = new CutctxError("test error");
    expect(err.name).toBe("CutctxError");
    expect(err.message).toBe("test error");
    expect(err).toBeInstanceOf(Error);
  });

  it("supports details", () => {
    const err = new CutctxError("test", { key: "value" });
    expect(err.details).toEqual({ key: "value" });
  });

  it("details are optional", () => {
    const err = new CutctxError("test");
    expect(err.details).toBeUndefined();
  });
});

describe("CutctxConnectionError", () => {
  it("inherits from CutctxError", () => {
    const err = new CutctxConnectionError("connection failed");
    expect(err).toBeInstanceOf(CutctxError);
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe("CutctxConnectionError");
  });
});

describe("CutctxAuthError", () => {
  it("inherits from CutctxError", () => {
    const err = new CutctxAuthError("unauthorized");
    expect(err).toBeInstanceOf(CutctxError);
    expect(err.name).toBe("CutctxAuthError");
  });
});

describe("CutctxCompressError", () => {
  it("includes statusCode and errorType", () => {
    const err = new CutctxCompressError(500, "compression_error", "failed");
    expect(err).toBeInstanceOf(CutctxError);
    expect(err.name).toBe("CutctxCompressError");
    expect(err.statusCode).toBe(500);
    expect(err.errorType).toBe("compression_error");
    expect(err.message).toBe("failed");
  });
});

describe("ConfigurationError", () => {
  it("inherits from CutctxError", () => {
    const err = new ConfigurationError("bad config");
    expect(err).toBeInstanceOf(CutctxError);
    expect(err.name).toBe("ConfigurationError");
  });
});

describe("ProviderError", () => {
  it("inherits from CutctxError", () => {
    const err = new ProviderError("provider failed");
    expect(err).toBeInstanceOf(CutctxError);
    expect(err.name).toBe("ProviderError");
  });
});

describe("StorageError", () => {
  it("inherits from CutctxError", () => {
    const err = new StorageError("db error");
    expect(err).toBeInstanceOf(CutctxError);
    expect(err.name).toBe("StorageError");
  });
});

describe("TokenizationError", () => {
  it("inherits from CutctxError", () => {
    const err = new TokenizationError("token count failed");
    expect(err).toBeInstanceOf(CutctxError);
    expect(err.name).toBe("TokenizationError");
  });
});

describe("CacheError", () => {
  it("inherits from CutctxError", () => {
    const err = new CacheError("cache miss");
    expect(err).toBeInstanceOf(CutctxError);
    expect(err.name).toBe("CacheError");
  });
});

describe("ValidationError", () => {
  it("inherits from CutctxError", () => {
    const err = new ValidationError("invalid setup");
    expect(err).toBeInstanceOf(CutctxError);
    expect(err.name).toBe("ValidationError");
  });
});

describe("TransformError", () => {
  it("inherits from CutctxError", () => {
    const err = new TransformError("transform failed");
    expect(err).toBeInstanceOf(CutctxError);
    expect(err.name).toBe("TransformError");
  });
});

describe("mapProxyError", () => {
  it("maps 401 to CutctxAuthError", () => {
    const err = mapProxyError(401, "auth_error", "unauthorized", {
      code: "invalid_client_key",
      remediation: "Run cutctx auth login.",
    });
    expect(err).toBeInstanceOf(CutctxAuthError);
    expect(err.message).toBe("unauthorized");
    expect(err.details).toEqual({
      code: "invalid_client_key",
      remediation: "Run cutctx auth login.",
    });
  });

  it("maps configuration_error type", () => {
    const err = mapProxyError(400, "configuration_error", "bad config");
    expect(err).toBeInstanceOf(ConfigurationError);
  });

  it("maps provider_error type", () => {
    const err = mapProxyError(502, "provider_error", "upstream failed");
    expect(err).toBeInstanceOf(ProviderError);
  });

  it("maps storage_error type", () => {
    const err = mapProxyError(500, "storage_error", "db down");
    expect(err).toBeInstanceOf(StorageError);
  });

  it("maps tokenization_error type", () => {
    const err = mapProxyError(500, "tokenization_error", "bad tokens");
    expect(err).toBeInstanceOf(TokenizationError);
  });

  it("maps cache_error type", () => {
    const err = mapProxyError(500, "cache_error", "cache issue");
    expect(err).toBeInstanceOf(CacheError);
  });

  it("maps validation_error type", () => {
    const err = mapProxyError(422, "validation_error", "invalid");
    expect(err).toBeInstanceOf(ValidationError);
  });

  it("maps transform_error type", () => {
    const err = mapProxyError(500, "transform_error", "transform broke");
    expect(err).toBeInstanceOf(TransformError);
  });

  it("falls back to CutctxCompressError for unknown types", () => {
    const err = mapProxyError(500, "unknown_error", "something broke");
    expect(err).toBeInstanceOf(CutctxCompressError);
  });
});
