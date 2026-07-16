import assert from "node:assert/strict";
import test from "node:test";

import { fetchWithTimeout, TimeoutError } from "../src/lib/fetch-with-timeout.js";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });
  return { promise, resolve, reject };
}

function createTimerHarness() {
  const timers = new Map();
  const cleared = [];
  let nextId = 1;
  return {
    install() {
      const originalSetTimeout = globalThis.setTimeout;
      const originalClearTimeout = globalThis.clearTimeout;
      globalThis.setTimeout = (callback, delay) => {
        const id = nextId++;
        timers.set(id, { callback, delay });
        return id;
      };
      globalThis.clearTimeout = (id) => {
        cleared.push(id);
        timers.delete(id);
      };
      return () => {
        globalThis.setTimeout = originalSetTimeout;
        globalThis.clearTimeout = originalClearTimeout;
      };
    },
    fireOnlyTimer() {
      assert.equal(timers.size, 1);
      const [[id, timer]] = timers;
      timers.delete(id);
      timer.callback();
    },
    get pendingCount() {
      return timers.size;
    },
    get clearedCount() {
      return cleared.length;
    },
  };
}

function trackAbortSignal(controller) {
  const signal = controller.signal;
  const originalAdd = signal.addEventListener.bind(signal);
  const originalRemove = signal.removeEventListener.bind(signal);
  let adds = 0;
  let removes = 0;
  signal.addEventListener = (...args) => {
    adds += 1;
    return originalAdd(...args);
  };
  signal.removeEventListener = (...args) => {
    removes += 1;
    return originalRemove(...args);
  };
  return { signal, get adds() { return adds; }, get removes() { return removes; } };
}

test("rejects an already-aborted caller signal without starting fetch or a timeout", async () => {
  const controller = new AbortController();
  const reason = new DOMException("Caller stopped", "AbortError");
  controller.abort(reason);
  const timers = createTimerHarness();
  const restore = timers.install();
  let calls = 0;

  try {
    await assert.rejects(
      fetchWithTimeout("/contracts", { signal: controller.signal, timeoutMs: 10, fetchImpl: () => { calls += 1; } }),
      (error) => error === reason,
    );
    assert.equal(calls, 0);
    assert.equal(timers.pendingCount, 0);
  } finally {
    restore();
  }
});

test("preserves a caller abort reason instead of normalizing it as a timeout", async () => {
  const controller = new AbortController();
  const tracked = trackAbortSignal(controller);
  const timers = createTimerHarness();
  const restore = timers.install();
  const request = deferred();

  try {
    const operation = fetchWithTimeout("/contracts", {
      signal: tracked.signal,
      timeoutMs: 10,
      fetchImpl: (_input, { signal }) => new Promise((resolve, reject) => {
        signal.addEventListener("abort", () => reject(signal.reason), { once: true });
        request.promise.then(resolve, reject);
      }),
    });
    const reason = new DOMException("Route changed", "AbortError");
    controller.abort(reason);
    await assert.rejects(operation, (error) => error === reason);
    assert.equal(timers.pendingCount, 0);
    assert.equal(timers.clearedCount, 1);
    assert.equal(tracked.adds, tracked.removes);
  } finally {
    restore();
  }
});

test("normalizes only its own timeout as TimeoutError", async () => {
  const timers = createTimerHarness();
  const restore = timers.install();
  const request = deferred();

  try {
    const operation = fetchWithTimeout("/contracts", {
      timeoutMs: 10,
      fetchImpl: (_input, { signal }) => new Promise((resolve, reject) => {
        signal.addEventListener("abort", () => reject(signal.reason), { once: true });
        request.promise.then(resolve, reject);
      }),
    });
    timers.fireOnlyTimer();
    await assert.rejects(operation, (error) => error instanceof TimeoutError && error.message === "Request timed out after 10ms");
    assert.equal(timers.pendingCount, 0);
  } finally {
    restore();
  }
});

for (const outcome of ["success", "http error", "caller abort", "timeout"]) {
  test(`cleans up timeout and caller listener after ${outcome}`, async () => {
    const controller = new AbortController();
    const tracked = trackAbortSignal(controller);
    const timers = createTimerHarness();
    const restore = timers.install();
    const request = deferred();

    try {
      const operation = fetchWithTimeout("/contracts", {
        signal: tracked.signal,
        timeoutMs: 10,
        fetchImpl: (_input, { signal }) => new Promise((resolve, reject) => {
          signal.addEventListener("abort", () => reject(signal.reason), { once: true });
          request.promise.then(resolve, reject);
        }),
      });
      if (outcome === "success") request.resolve({ ok: true });
      if (outcome === "http error") request.resolve({ ok: false, status: 503 });
      if (outcome === "caller abort") controller.abort(new DOMException("stop", "AbortError"));
      if (outcome === "timeout") timers.fireOnlyTimer();

      if (outcome === "success" || outcome === "http error") {
        await assert.doesNotReject(operation);
      } else {
        await assert.rejects(operation);
      }
      assert.equal(timers.pendingCount, 0);
      assert.equal(timers.clearedCount, 1);
      assert.equal(tracked.adds, tracked.removes);
    } finally {
      restore();
    }
  });
}
