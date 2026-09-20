import { createRawajClient } from '../../frontend-integration/rawaj-api.js';

// In development Vite proxies /api; the built app is served directly by FastAPI.
// The frontend does not need an environment file or any service credentials.
export const api = createRawajClient({ baseUrl: window.location.origin });
