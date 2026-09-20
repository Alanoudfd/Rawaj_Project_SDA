# Rawaj frontend

React frontend integrated with the FastAPI application in the repository root.

```powershell
npm ci
npm run dev
```

Run FastAPI on port 8000. Vite serves development on http://127.0.0.1:5173 and proxies `/api` to FastAPI. No frontend `.env` is needed.

For the combined application, run `npm run build` and open http://127.0.0.1:8000. The root FastAPI app serves `dist/`.

The three pages are Home, Monthly Strategy (including the calendar), and Content Creation. Sign-in is a frontend preview, not authentication. Passwords are never transmitted or stored. Restaurant, plan, task, and selected-idea data is saved through the root API.

See the root README for setup, environment variables, and tests.
