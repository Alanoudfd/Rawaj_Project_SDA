/** Framework-neutral client for the Rawaj FastAPI backend. */
export class RawajApiError extends Error {
  constructor(message, { status, detail, response } = {}) {
    super(message);
    this.name = "RawajApiError";
    this.status = status;
    this.detail = detail;
    this.response = response;
  }
}

export class RawajJobError extends Error {
  constructor(job) {
    super(job.error || "Restaurant analysis failed. Start a new analysis to retry.");
    this.name = "RawajJobError";
    this.job = job;
  }
}

function abortError(signal) {
  return signal.reason || new DOMException("The request was cancelled.", "AbortError");
}

function delay(milliseconds, signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(abortError(signal));
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(abortError(signal));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, milliseconds);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

function describeDetail(detail) {
  if (typeof detail === "string") return detail;
  if (typeof detail?.message === "string") return detail.message;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      const location = Array.isArray(item.loc) ? item.loc.join(".") : "";
      return [location, item.msg || "Invalid value"].filter(Boolean).join(": ");
    }).join("; ");
  }
  return null;
}

export function createRawajClient({ baseUrl = "http://127.0.0.1:8000" } = {}) {
  if (typeof baseUrl !== "string" || !baseUrl.trim()) {
    throw new TypeError("baseUrl must be the backend URL, for example http://127.0.0.1:8000");
  }
  const apiUrl = `${baseUrl.trim().replace(/\/+$/, "")}/api`;
  const restaurantPath = (id) => `/restaurants/${encodeURIComponent(id)}`;

  async function request(path, { method = "GET", body, signal } = {}) {
    let response;
    try {
      response = await fetch(`${apiUrl}${path}`, {
        method,
        headers: {
          Accept: "application/json",
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        signal,
      });
    } catch (error) {
      if (signal?.aborted) throw abortError(signal);
      throw new RawajApiError(
        `Could not reach the Rawaj API at ${apiUrl}. Check that the backend is running and FRONTEND_ORIGINS includes your frontend origin.`,
        { detail: error.message },
      );
    }

    const text = await response.text();
    let payload = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        throw new RawajApiError(`The Rawaj API returned a non-JSON response (HTTP ${response.status}).`, {
          status: response.status,
        });
      }
    }
    if (!response.ok) {
      throw new RawajApiError(
        describeDetail(payload?.detail) || `Rawaj API request failed (HTTP ${response.status}).`,
        { status: response.status, detail: payload?.detail, response: payload },
      );
    }
    return payload;
  }

  const client = {
    listRestaurants({ offset = 0, limit = 50, signal } = {}) {
      const query = new URLSearchParams({ offset: String(offset), limit: String(limit) });
      return request(`/restaurants?${query}`, { signal });
    },

    createRestaurant(data, { signal } = {}) {
      return request("/restaurants", { method: "POST", body: data, signal });
    },

    getRestaurant(id, { signal } = {}) {
      return request(restaurantPath(id), { signal });
    },

    updateRestaurant(id, data, { signal } = {}) {
      return request(restaurantPath(id), { method: "PATCH", body: data, signal });
    },

    getRestaurantContext(id, { signal } = {}) {
      return request(`${restaurantPath(id)}/context`, { signal });
    },

    analyzeRestaurant(id, {
      content_limit = 30,
      lookback_days = 90,
      force_refresh = false,
      signal,
    } = {}) {
      return request(`${restaurantPath(id)}/analyze`, {
        method: "POST",
        body: { content_limit, lookback_days, force_refresh },
        signal,
      });
    },

    getJob(id, { signal } = {}) {
      return request(`/jobs/${encodeURIComponent(id)}`, { signal });
    },

    async waitForJob(id, {
      pollIntervalMs = 2000,
      timeoutMs = 900000,
      signal,
      onUpdate,
    } = {}) {
      if (!Number.isFinite(pollIntervalMs) || pollIntervalMs <= 0) {
        throw new TypeError("pollIntervalMs must be a positive number.");
      }
      if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
        throw new TypeError("timeoutMs must be a positive number.");
      }
      if (onUpdate !== undefined && typeof onUpdate !== "function") {
        throw new TypeError("onUpdate must be a function.");
      }
      if (signal?.aborted) throw abortError(signal);

      const controller = new AbortController();
      const onAbort = () => controller.abort(abortError(signal));
      signal?.addEventListener("abort", onAbort, { once: true });
      const timeout = setTimeout(() => {
        const error = new Error(`Timed out waiting for analysis ${id}. The server may still be working; check getJob() to continue.`);
        error.name = "TimeoutError";
        controller.abort(error);
      }, timeoutMs);

      try {
        while (true) {
          const job = await client.getJob(id, { signal: controller.signal });
          onUpdate?.(job);
          if (job.status === "completed") return job;
          if (job.status === "failed") throw new RawajJobError(job);
          if (job.status !== "queued" && job.status !== "running") {
            throw new RawajApiError(`Unknown analysis status: ${job.status}`);
          }
          await delay(pollIntervalMs, controller.signal);
        }
      } catch (error) {
        if (controller.signal.aborted) throw abortError(controller.signal);
        throw error;
      } finally {
        clearTimeout(timeout);
        signal?.removeEventListener("abort", onAbort);
      }
    },

    getStrategy(id, month, { signal } = {}) {
      return request(`${restaurantPath(id)}/strategy?${new URLSearchParams({ month })}`, { signal });
    },

    createStrategy(id, data, { signal } = {}) {
      return request(`${restaurantPath(id)}/strategy`, { method: "POST", body: data, signal });
    },

    updateTask(id, taskId, data, { signal } = {}) {
      return request(`${restaurantPath(id)}/strategy/tasks/${encodeURIComponent(taskId)}`, { method: "PATCH", body: data, signal });
    },

    addTask(id, data, { signal } = {}) {
      return request(`${restaurantPath(id)}/strategy/tasks`, { method: "POST", body: data, signal });
    },

    generateIdeas(id, data, { signal } = {}) {
      return request(`${restaurantPath(id)}/content-ideas`, { method: "POST", body: data, signal });
    },

    createOutreachDraft(id, { signal } = {}) {
      return request(`${restaurantPath(id)}/outreach/draft`, { method: "POST", signal });
    },
  };

  return client;
}
