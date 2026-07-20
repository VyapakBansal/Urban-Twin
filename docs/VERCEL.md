# Vercel hosting (frontend)

Urban Twin’s **Cesium map** is a Vite SPA. Host it on Vercel; keep the **FastAPI** backend on a separate host (Azure VM, Railway, Render, etc.) because:
- Cesium + static assets fit Vercel
- Long-running ingest / Kafka / LightGBM training do **not**

## 1. Repo setup

This folder is `frontend/`. From the Vercel dashboard:

- **Root Directory:** `frontend`
- **Framework Preset:** Vite
- **Build Command:** `npm run build`
- **Output Directory:** `dist`

Or CLI:

```bash
cd frontend
npx vercel
```

## 2. Environment variables (Vercel project settings)

| Name | Value |
|---|---|
| `VITE_API_BASE` | `https://your-api-host.example.com` (or `/api` if reverse-proxied) |
| `VITE_WS_URL` | `wss://your-api-host.example.com/ws/live` |
| `VITE_CESIUM_ION_TOKEN` | optional Cesium ion token |
| `VITE_SUPABASE_URL` | optional — see `docs/SUPABASE.md` |
| `VITE_SUPABASE_ANON_KEY` | optional |

Production builds already default to same-origin `/api` + `/ws/live` when these are unset (nginx-style). On Vercel you **must** set `VITE_API_BASE` / `VITE_WS_URL` to your API host.

## 3. CORS

On the API host `.env`:

```
CORS_ORIGINS=http://localhost:5173,https://your-app.vercel.app,https://your-custom-domain.com
```

Restart the API after changing CORS.

## 4. vercel.json

Included in this directory for SPA fallback routing.
