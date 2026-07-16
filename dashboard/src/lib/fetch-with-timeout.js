export class TimeoutError extends Error {
  constructor(timeoutMs) {
    super(`Request timed out after ${timeoutMs}ms`);
    this.name = "TimeoutError";
  }
}

function abortReason(signal) {
  return signal.reason || new DOMException("The operation was aborted", "AbortError");
}

export async function fetchWithTimeout(input, options = {}) {
  const { signal: callerSignal, timeoutMs, fetchImpl = globalThis.fetch, ...init } = options;
  if (callerSignal?.aborted) {
    throw abortReason(callerSignal);
  }

  const controller = new AbortController();
  let outcome = null;
  const timeoutError = new TimeoutError(timeoutMs);
  const onCallerAbort = () => {
    if (outcome) {
      return;
    }
    outcome = "caller";
    controller.abort(abortReason(callerSignal));
  };
  const timeoutId = setTimeout(() => {
    if (outcome) {
      return;
    }
    outcome = "timeout";
    controller.abort(timeoutError);
  }, timeoutMs);

  callerSignal?.addEventListener("abort", onCallerAbort, { once: true });
  try {
    const response = await fetchImpl(input, { ...init, signal: controller.signal });
    if (outcome === "caller") {
      throw abortReason(callerSignal);
    }
    if (outcome === "timeout") {
      throw timeoutError;
    }
    return response;
  } catch (error) {
    if (outcome === "caller") {
      throw abortReason(callerSignal);
    }
    if (outcome === "timeout") {
      throw timeoutError;
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
    callerSignal?.removeEventListener("abort", onCallerAbort);
  }
}
