# GCP / Vertex AI Setup Checklist

**One-time manual setup.** This is not automated by Claude — nothing in Phase 0 makes a live Vertex AI call, so this can be done any time before Phase 3 begins. Do this yourself, following the steps below.

## Steps

1. **Create or select a GCP project.** In the [GCP Console](https://console.cloud.google.com/), create a new project (or reuse an existing one) dedicated to this demo. Note the **Project ID** — you'll need it for `GCP_PROJECT_ID`.

2. **Enable billing.** Vertex AI requires an active billing account attached to the project. Free-tier credits may cover demo-scale usage — check current GCP offers.

3. **Enable the Vertex AI API.** In the Console, go to *APIs & Services → Library*, search for "Vertex AI API" (`aiplatform.googleapis.com`), and enable it for your project. Or via `gcloud`:
   ```bash
   gcloud services enable aiplatform.googleapis.com --project=YOUR_PROJECT_ID
   ```

4. **Create a service account** with the **Vertex AI User** role (`roles/aiplatform.user`):
   ```bash
   gcloud iam service-accounts create ask-sous-agent \
     --project=YOUR_PROJECT_ID \
     --display-name="Ask Sous Agent"

   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:ask-sous-agent@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/aiplatform.user"
   ```

5. **Create and download its JSON key:**
   ```bash
   gcloud iam service-accounts keys create ~/secrets/ask-sous-key.json \
     --iam-account=ask-sous-agent@YOUR_PROJECT_ID.iam.gserviceaccount.com
   ```
   **Store the key file outside the repo tree** (e.g. `~/secrets/`), or if it must live inside the repo, only in a path already covered by `.gitignore` (`*service-account*.json`, `*credentials*.json`, `*.key.json`). Never commit it.

6. **Set local environment variables** in your `.env` (copied from `.env.example`):
   - `GOOGLE_APPLICATION_CREDENTIALS` — the absolute path to the key file from step 5.
   - `GCP_PROJECT_ID` — the project ID from step 1.
   - `GCP_REGION` — a region with Gemini model availability, e.g. `us-central1`. **Re-confirm current model/region availability at the start of Phase 3** — availability shifts over time, and this checklist may have been written well before Phase 3 actually starts.

7. **Check billing alerts / free-tier credit** before heavy use, so development doesn't produce an unexpected bill.

## Verification (do this once Phase 3 exists)

Phase 3 will be the first phase to make a live call. If it fails with an auth or permission error, re-check steps 4–6 first — a misconfigured service account won't surface until then.

**Status: completed (2026-07-16).** Project `your-gcp-project-id` (display name "ask-sous-dev"), service account `ask-sous-agent@your-gcp-project-id.iam.gserviceaccount.com` with the Vertex AI User role, key stored at `~/secrets/ask-sous-key.json` (outside the repo tree). Real calls confirmed working end-to-end: insights Q&A, streaming, function-calling, campaign generation, and embeddings (`embed_seed_data.py` run for real — 138 reviews + 16 campaigns embedded). Two real bugs and one real UX gap were found and fixed during this verification pass — see `docs/decisions/013-live-credentials-verification.md` for full detail; none of them were about GCP setup itself being wrong, all were latent bugs in this app's own code that only a live call could surface.
