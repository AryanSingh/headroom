/**
 * Error hierarchy matching Python headroom.exceptions.
 */

export class CutCtxError extends Error {
  details?: Record<string, any>;

  constructor(message: string, details?: Record<string, any>) {
    super(message);
    this.name = "CutCtxError";
    this.details = details;
  }
}

export class CutCtxConnectionError extends CutCtxError {
  constructor(message: string, details?: Record<string, any>) {
    super(message, details);
    this.name = "CutCtxConnectionError";
  }
}

export class CutCtxAuthError extends CutCtxError {
  constructor(message: string, details?: Record<string, any>) {
    super(message, details);
    this.name = "CutCtxAuthError";
  }
}

export class CutCtxCompressError extends CutCtxError {
  statusCode: number;
  errorType: string;

  constructor(statusCode: number, errorType: string, message: string, details?: Record<string, any>) {
    super(message, details);
    this.name = "CutCtxCompressError";
    this.statusCode = statusCode;
    this.errorType = errorType;
  }
}

export class ConfigurationError extends CutCtxError {
  constructor(message: string, details?: Record<string, any>) {
    super(message, details);
    this.name = "ConfigurationError";
  }
}

export class ProviderError extends CutCtxError {
  constructor(message: string, details?: Record<string, any>) {
    super(message, details);
    this.name = "ProviderError";
  }
}

export class StorageError extends CutCtxError {
  constructor(message: string, details?: Record<string, any>) {
    super(message, details);
    this.name = "StorageError";
  }
}

export class TokenizationError extends CutCtxError {
  constructor(message: string, details?: Record<string, any>) {
    super(message, details);
    this.name = "TokenizationError";
  }
}

export class CacheError extends CutCtxError {
  constructor(message: string, details?: Record<string, any>) {
    super(message, details);
    this.name = "CacheError";
  }
}

export class ValidationError extends CutCtxError {
  constructor(message: string, details?: Record<string, any>) {
    super(message, details);
    this.name = "ValidationError";
  }
}

export class TransformError extends CutCtxError {
  constructor(message: string, details?: Record<string, any>) {
    super(message, details);
    this.name = "TransformError";
  }
}

// --- Proxy error mapping ---

const ERROR_TYPE_MAP: Record<string, new (message: string, details?: Record<string, any>) => CutCtxError> = {
  configuration_error: ConfigurationError,
  provider_error: ProviderError,
  storage_error: StorageError,
  tokenization_error: TokenizationError,
  cache_error: CacheError,
  validation_error: ValidationError,
  transform_error: TransformError,
};

/**
 * Map a proxy error response to the correct CutCtxError subclass.
 */
export function mapProxyError(
  status: number,
  type: string,
  message: string,
): CutCtxError {
  if (status === 401) return new CutCtxAuthError(message);
  const ErrorClass = ERROR_TYPE_MAP[type];
  if (ErrorClass) return new ErrorClass(message, { statusCode: status, errorType: type });
  return new CutCtxCompressError(status, type, message);
}
