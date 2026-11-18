# Travel Agent Platform — Production Operational Runbooks

| Metadata | Value |
| :--- | :--- |
| **Document ID** | `OPS-RB-001` |
| **Related Docs** | [Operational Hub](operational_documentation.md) · [Deployment Guide](deployment_guide.md) · [Onboarding](onboarding_guide.md) · [Troubleshooting](troubleshooting_guide.md) · [API Docs](api_documentation.md) |
| **Design Standard** | Every runbook follows a uniform 5-step incident structure: **Impact → Preconditions → Execution → Verification → Follow-Up / Escalation**. Commands are copy-pasteable with explicit environment variables. |

---

## Runbook Index

| ID | Runbook Title | Trigger / Alert Condition | Default Severity | Target MTTR |
| :---: | :--- | :--- | :---: | :---: |
| **[`RB-01`](#rb-01-production-service-outage--elevated-5xx--triage--immutable-rollback)** | Production Service Outage / Elevated `5xx` — Triage & Immutable Rollback | Cloud Run `5xx` rate `> 2%` or post-deploy regression | `SEV-1` | `<= 15 min` |
| **[`RB-02`](#rb-02-primary-region-europe-west9-outage--multi-region-failover--recovery)** | Primary Region (`europe-west9`) Outage — Multi-Region Failover & Recovery | `europe-west9` Cloud Run unreachable or regional GCP incident | `SEV-1` / `SEV-2` | `<= 25s` (API) / `<= 15m` (UI URL) |
| **[`RB-03`](#rb-03-vertex-ai-quota-exhaustion-429-or-primary-model-degradation--emergency-model-swap)** | Vertex AI Quota Exhaustion (`429`) or Primary Model Degradation — Emergency Model Swap | Spike in `Failing over to backup model` or dual-model `500`s | `SEV-1` / `SEV-2` | `<= 15 min` |
| **[`RB-04`](#rb-04-terraform-state-lock-contention-or-corrupted-tfstate--recovery)** | Terraform State Lock Contention or Corrupted `.tfstate` — Recovery | `Error acquiring the state lock` or state corruption in CI/CD | `SEV-2` | `<= 20 min` |
| **[`RB-05`](#rb-05-traffic-spike--latency-saturation--emergency-capacity-scaling)** | Traffic Spike / Latency Saturation — Emergency Capacity Scaling | Instance count hitting `max_instances` or latency `> 15s` | `SEV-2` / `SEV-3` | `<= 15 min` |
| **[`RB-06`](#rb-06-scheduled-multi-region-dr--backup-verification-drills)** | Scheduled Multi-Region DR & Backup Verification Drills | Weekly probe check / Monthly live RTO & backup restore drill | Routine | `~5 min` |
| **[`RB-07`](#rb-07-iam-drift-remediation--default-service-account-hardening-audit)** | IAM Drift Remediation & Default Service Account Hardening Audit | Quarterly security review or IAM policy drift alert | Routine / `SEV-2` | `<= 10 min` |
| **[`RB-08`](#rb-08-intentional-api-schema-change--openapi-31-snapshot-regeneration)** | Intentional API Schema Change & OpenAPI 3.1 Snapshot Regeneration | `test_api_versioning_and_contracts.py` failing on schema update | Routine | `<= 5 min` |
| **[`RB-09`](#rb-09-ai-quality-regression--running-the-7-metric-geap-eval--loss-flywheel)** | AI Quality Regression — Running the 7-Metric GEAP Eval & Loss Flywheel | Routing errors, flight/price mutation, or prompt/model tuning | `SEV-3` / Routine | `~15–30 min` |

---

## `RB-01`: Production Service Outage / Elevated `5xx` — Triage & Immutable Rollback

| Field | Value |
| :--- | :--- |
| **Severity** | `SEV-1` |
| **Trigger / Symptom** | Elevated HTTP `500`/`502`/`503`/`504` on `flights-search-app`, `conversational-app`, or `frontend`, or broken release immediately following deployment. |
| **Target MTTR** | `< 2 min` (emergency traffic shift) · `<= 10 min` (Terraform state convergence) |
| **Required IAM** | `roles/run.admin` (emergency traffic pin) or `roles/cloudbuild.builds.editor` + `roles/iam.serviceAccountUser` on `travel-agent-cicd` |

### 1. Impact & Automated Mitigations
- If only `europe-west9` is returning `5xx`, [`frontend/src/apiClient.js`](../frontend/src/apiClient.js) (`postWithRegionalFailover`) is already automatically retrying browser API calls against `europe-west1`.
- If a bad code/config deploy pushed broken containers to **both** regions simultaneously, cross-region failover will also hit the broken revision—**roll back immediately**.

### 2. Preconditions
```bash
export PROJECT_ID="travel-agent-prod-512211"
export PRIMARY_REGION="europe-west9"
export SECONDARY_REGION="europe-west1"
```

### 3. Step-by-Step Execution

1. **Identify the failing service and inspect the last 20 errors:**
   ```bash
   gcloud logging read \
     'resource.type="cloud_run_revision" AND (severity>=ERROR OR httpRequest.status>=500)' \
     --project="${PROJECT_ID}" \
     --limit=20 \
     --format="table(timestamp, resource.labels.service_name, resource.labels.revision_name, resource.labels.location, httpRequest.status, textPayload)"
   ```

2. **Check recent revisions to identify whether a new rollout caused the outage:**
   ```bash
   for SVC in flights-search-app conversational-app frontend; do
     echo "=== ${SVC} (${PRIMARY_REGION}) ==="
     gcloud run revisions list --service="${SVC}" --region="${PRIMARY_REGION}" --project="${PROJECT_ID}" --limit=3 \
       --format="table(metadata.name, status.conditions[0].status, spec.containers[0].image, metadata.creationTimestamp)"
   done
   ```

3. **Fast Mitigation (`< 30s`): Shift 100% of Cloud Run traffic back to the prior healthy revision** *(run for the affected service in both regions)*:
   ```bash
   SVC="conversational-app"   # Or flights-search-app / frontend
   GOOD_REV_PRIMARY="<prior-healthy-revision-europe-west9>"
   GOOD_REV_SECONDARY="<prior-healthy-revision-europe-west1>"

   gcloud run services update-traffic "${SVC}" \
     --to-revisions="${GOOD_REV_PRIMARY}=100" \
     --region="${PRIMARY_REGION}" --project="${PROJECT_ID}"

   gcloud run services update-traffic "${SVC}" \
     --to-revisions="${GOOD_REV_SECONDARY}=100" \
     --region="${SECONDARY_REGION}" --project="${PROJECT_ID}"
   ```

4. **Permanent State Convergence (`~5 min`): Reconcile Terraform & all services to the last known-good Git SHA/tag:**
   ```bash
   # Look up retained image tags in Artifact Registry
   gcloud artifacts docker images list \
     "${PRIMARY_REGION}-docker.pkg.dev/${PROJECT_ID}/travel-agent/conversational-app" \
     --include-tags --project="${PROJECT_ID}" --limit=5

   # Checkout the prior known-good commit/tag and deploy via Cloud Build
   git checkout <GOOD_GIT_SHA_OR_TAG>
   IMAGE_TAG="<GOOD_GIT_SHA_OR_TAG>" ./deployment/deploy.sh prod
   ```

### 4. Verification Criteria
```bash
./deployment/validate_dr.sh --env prod --probe-only
```
- All 6 regional services (`3` primary + `3` secondary) return `/healthz=200` and `/readyz=200`.
- Cloud Logging shows zero new `severity>=ERROR` entries over a 5-minute window.

### 5. Follow-Up / Escalation
- If `5xx` errors persist on a previously healthy image SHA, the root cause is an external dependency (`Vertex AI` or regional GCP infrastructure) → escalate immediately to **`RB-02`** (Regional Outage) or **`RB-03`** (Vertex AI Outage).

---

## `RB-02`: Primary Region (`europe-west9`) Outage — Multi-Region Failover & Recovery

| Field | Value |
| :--- | :--- |
| **Severity** | `SEV-1` (if primary `frontend` is down) · `SEV-2` (if only primary backends are degraded) |
| **Trigger / Symptom** | GCP Service Health announces an incident in `europe-west9` (Paris), or probes to `europe-west9` time out / return `502`/`503`/`504`. |
| **Target RTO** | `<= 25s` automatic client API failover · `< 5 min` manual standby frontend URL distribution / DNS switch |
| **Required IAM** | `roles/run.viewer` (verification), `roles/run.admin` (scaling standby), `roles/cloudbuild.builds.editor` (cold-region evacuation) |

### 1. Impact & Automated Mitigations
- **Backend API Failover is Automatic:** Users who already loaded the web app (or can still reach `frontend` in `europe-west9`) automatically fail over `POST /api/v1/run-flights-search` and `POST /api/v1/run-conversational` to `europe-west1` via [`postWithRegionalFailover()`](../frontend/src/apiClient.js).
- **Frontend Entrypoint Switchover:** Because no Global External Application Load Balancer sits in front of the `.run.app` URLs yet, if the `europe-west9` `frontend` service itself is unreachable, share or repoint DNS to the pre-deployed warm `frontend` URL in `europe-west1` (`min_instances = 1`).

### 2. Preconditions
```bash
export PROJECT_ID="travel-agent-prod-512211"
export PRIMARY_REGION="europe-west9"
export SECONDARY_REGION="europe-west1"
```

### 3. Step-by-Step Execution

1. **Verify Warm Standby (`europe-west1`) health and retrieve standby URLs:**
   ```bash
   for SVC in flights-search-app conversational-app frontend; do
     URL=$(gcloud run services describe "${SVC}" --project="${PROJECT_ID}" --region="${SECONDARY_REGION}" --format="value(status.url)")
     echo "${SVC} (${SECONDARY_REGION}): ${URL}"
     curl -fsS "${URL}/healthz" && echo ""
     curl -fsS "${URL}/readyz" && echo ""
   done
   ```

2. **Pre-scale Warm Standby (`europe-west1`) `min-instances` from `1` to `3` to absorb 100% of production traffic without cold starts:**
   ```bash
   for SVC in flights-search-app conversational-app frontend; do
     gcloud run services update "${SVC}" \
       --min-instances=3 \
       --region="${SECONDARY_REGION}" \
       --project="${PROJECT_ID}"
   done
   ```

3. **If Primary `frontend` (`europe-west9`) is unreachable:** Direct users / update status page / CNAME to the `frontend` URL in `europe-west1` printed in Step 1 (its `/env-config.js` already targets `europe-west1` backends as primary).

4. **(Extreme Multi-Region Outage Only) Evacuate to a Cold-Standby GCP Region (e.g., `europe-west4` Netherlands):**
   If **both** `europe-west9` and `europe-west1` are impaired:
   ```bash
   REGION="europe-west4" SECONDARY_REGION="" ./deployment/deploy.sh prod
   ```

### 4. Verification Criteria
- `curl -fsS "<SECONDARY_FRONTEND_URL>/env-config.js"` shows `VITE_FLIGHTS_SEARCH_API_URL` and `VITE_CONVERSATIONAL_API_URL` pointing to `europe-west1`.
- Live E2E check against `europe-west1` passes:
  ```bash
  (cd conversational_app && CONVERSATIONAL_BASE_URL="<SECONDARY_CONV_URL>" python3 -m pytest tests/e2e/test_conversational.py -v)
  ```

### 5. Failback Procedure (Once `europe-west9` Recovers)
1. Run `./deployment/validate_dr.sh --env prod` to confirm `europe-west9` and `europe-west1` both pass health and RTO checks.
2. Run `./deployment/deploy.sh prod` to restore `secondary_min_instances = 1` cleanly from [`envs/prod.tfvars`](../deployment/terraform/envs/prod.tfvars).

---

## `RB-03`: Vertex AI Quota Exhaustion (`429`) or Primary Model Degradation — Emergency Model Swap

| Field | Value |
| :--- | :--- |
| **Severity** | `SEV-2` (if backup model is absorbing traffic, causing elevated latency) · `SEV-1` (if both primary & backup models fail) |
| **Trigger / Symptom** | Cloud Logging shows frequent `Failing over to backup model` warnings, `429 RESOURCE_EXHAUSTED`, `503 Service Unavailable`, or `500` responses when both models fail. |
| **Target MTTR** | `<= 5 min` (Cloud Run env override) · `<= 10 min` (Terraform `.tfvars` rollout) |
| **Required IAM** | `roles/run.admin` + `roles/iam.serviceAccountUser` on `travel-agent-runtime` |

### 1. Impact & Automated Mitigations
- When `gemini-3.5-flash-lite` hits `429` or `5xx`, the SDK first executes **5 exponential backoff retries** (`5s, 10s, 20s, 40s` = `~75s`), then fails over to `gemini-3.6-flash`. Users receive valid responses, **but latency increases to `75s+` per affected turn**. Promoting a healthy primary model eliminates that `75s` retry penalty immediately.

### 2. Preconditions
```bash
export PROJECT_ID="travel-agent-prod-512211"
```

### 3. Step-by-Step Execution

1. **Confirm which model and agent is failing in Cloud Logging:**
   ```bash
   gcloud logging read \
     'resource.type="cloud_run_revision" AND (textPayload:"Model error in agent" OR textPayload:"Failing over to backup model" OR textPayload:"also failed:")' \
     --project="${PROJECT_ID}" \
     --limit=25 \
     --format="table(timestamp, resource.labels.service_name, textPayload)"
   ```

2. **Emergency Fast-Path (`< 2 min`): Swap primary & distinct fallback model env vars directly on Cloud Run** *(remember: primary and fallback MUST remain distinct strings so `fallback_app` stays active!)*:
   ```bash
   NEW_PRIMARY="gemini-3.6-flash"
   NEW_FALLBACK="gemini-2.5-flash"

   for REG in europe-west9 europe-west1; do
     gcloud run services update flights-search-app \
       --update-env-vars="FLIGHTS_SEARCH_MODEL=${NEW_PRIMARY},FALLBACK_GEMINI_MODEL=${NEW_FALLBACK}" \
       --region="${REG}" --project="${PROJECT_ID}"

     gcloud run services update conversational-app \
       --update-env-vars="CONVERSATIONAL_MODEL=${NEW_PRIMARY},FALLBACK_GEMINI_MODEL=${NEW_FALLBACK}" \
       --region="${REG}" --project="${PROJECT_ID}"
   done
   ```
   *(Tip: If only `filter_smart` needs a stronger/different model, set `--update-env-vars="FILTER_SMART_MODEL=gemini-2.5-pro"` on `conversational-app` without changing the other 4 sub-agents.)*

3. **Persist in Git / Terraform:** Update `flights_search_model`, `conversational_model`, and `fallback_gemini_model` in [`deployment/terraform/envs/prod.tfvars`](../deployment/terraform/envs/prod.tfvars), commit, and deploy via `./deployment/deploy.sh prod`.

### 4. Verification Criteria
```bash
CONV_URL=$(gcloud run services describe conversational-app --project="${PROJECT_ID}" --region=europe-west9 --format="value(status.url)")
curl -fsS "${CONV_URL}/readyz" | python3 -m json.tool
```
- Confirm `"models"` shows `${NEW_PRIMARY}` and `"fallback_model"` shows `${NEW_FALLBACK}`.
- Confirm `total_latency` in `ADK Plugin Telemetry` logs returns below `15.0s`.

### 5. Follow-Up / Escalation
- If `429 RESOURCE_EXHAUSTED` persists across all models in `GEMINI_MODEL_LOCATION=global`, check **IAM & Admin → Quotas** in `travel-agent-prod-512211` for `aiplatform.googleapis.com` RPM/TPM quotas and submit a quota increase or check billing account health.

---

## `RB-04`: Terraform State Lock Contention or Corrupted `.tfstate` — Recovery

| Field | Value |
| :--- | :--- |
| **Severity** | `SEV-2` (blocks infrastructure/CD deployments; zero immediate impact on running Cloud Run containers) |
| **Trigger / Symptom** | Cloud Build Stage 2 or Stage 4 fails with `Error acquiring the state lock` (after `5m` `-lock-timeout=5m`) or invalid/corrupted `.tfstate` JSON. |
| **Target MTTR** | `<= 15 min` |
| **Required IAM** | `roles/storage.admin` on `gs://<PROJECT_ID>-tfstate` |

### 1. Impact & Automated Mitigations
- Running Cloud Run services are completely unaffected.
- GCS Object Versioning is enabled on `gs://<PROJECT_ID>-tfstate` by [`bootstrap.sh`](../deployment/bootstrap.sh), preserving every historical `.tfstate` generation.

### 2. Preconditions
```bash
export ENV_NAME="prod"                         # dev | staging | prod
export PROJECT_ID="travel-agent-prod-512211"   # travel-agent-511710 | travel-agent-staging-512211 | travel-agent-prod-512211
export TF_BUCKET="gs://${PROJECT_ID}-tfstate"
# Note: Cloud Build pipelines store state under prefix travel-agent/${ENV_NAME}
export STATE_URI="${TF_BUCKET}/travel-agent/${ENV_NAME}/default.tfstate"
```

### 3. Step-by-Step Execution

#### Scenario A: Stale State Lock (`default.tflock`) After a Cancelled/Crashed Cloud Build
1. **Verify NO Cloud Build job is currently running** in `${PROJECT_ID}`:
   ```bash
   gcloud builds list --ongoing --project="${PROJECT_ID}" --region="europe-west9"
   ```
   *(STOP if a build is still `WORKING`! Wait for it to finish or cancel it first.)*

2. **Inspect and remove the orphaned GCS lock object:**
   ```bash
   gcloud storage ls -l "${TF_BUCKET}/travel-agent/${ENV_NAME}/default.tflock" --project="${PROJECT_ID}"
   gcloud storage rm "${TF_BUCKET}/travel-agent/${ENV_NAME}/default.tflock" --project="${PROJECT_ID}"
   ```

#### Scenario B: Corrupted or Unintended Terraform State Mutation
1. **List all archived GCS object generations (`#<GENERATION_NUMBER>`):**
   ```bash
   gcloud storage ls -a "${STATE_URI}" --project="${PROJECT_ID}"
   ```
   *(If inspecting default/drill state objects as well, run `gcloud storage ls -a "${TF_BUCKET}/travel-agent/**"`.)*

2. **Download the candidate prior generation to a local temporary folder and validate its JSON structure** (`version >= 4`, non-empty `lineage`, valid `serial` and `resources` array):
   ```bash
   TMP_DIR="$(mktemp -d)"
   TARGET_GEN="<GENERATION_NUMBER>"
   gcloud storage cp "${STATE_URI}#${TARGET_GEN}" "${TMP_DIR}/candidate.tfstate" --project="${PROJECT_ID}"

   python3 -c '
   import json, sys
   s = json.load(open(sys.argv[1]))
   assert s["version"] >= 4 and s["lineage"] and isinstance(s["resources"], list)
   print(f"Valid tfstate: serial={s[\"serial\"]}, lineage={s[\"lineage\"]}, resources={len(s[\"resources\"])}")
   ' "${TMP_DIR}/candidate.tfstate"
   ```

3. **Promote the verified prior generation as the active live state** (this non-destructively creates a new latest generation while preserving all history):
   ```bash
   gcloud storage cp "${STATE_URI}#${TARGET_GEN}" "${STATE_URI}" --project="${PROJECT_ID}"
   rm -rf "${TMP_DIR}"
   ```

### 4. Verification Criteria
- Re-run `./deployment/deploy.sh ${ENV_NAME}` and confirm Stage 2 (`terraform-bootstrap-*`) and Stage 4 (`terraform-deploy-*`) acquire the lock and complete cleanly.

### 5. Follow-Up
- Run `./deployment/verify_backups.sh --local-self-test` (or `--env ${ENV_NAME}`) to confirm ongoing backup health.

---

## `RB-05`: Traffic Spike / Latency Saturation — Emergency Capacity Scaling

| Field | Value |
| :--- | :--- |
| **Severity** | `SEV-2` / `SEV-3` |
| **Trigger / Symptom** | Cloud Run active instance count reaches `max_instances` (`20` in `prod`), queuing delays cause `HTTP 429`/`503` at the Cloud Run ingress, or container memory nears `2Gi`. |
| **Target MTTR** | `<= 10 min` |
| **Required IAM** | `roles/run.admin` (instant override) + repository push access (`.tfvars` persistence) |

### 1. Impact & Preconditions
```bash
export PROJECT_ID="travel-agent-prod-512211"
```

### 2. Step-by-Step Execution

1. **Apply immediate Cloud Run scaling increase across primary and warm standby regions:**
   ```bash
   for REG in europe-west9 europe-west1; do
     for SVC in flights-search-app conversational-app; do
       gcloud run services update "${SVC}" \
         --min-instances=4 \
         --max-instances=50 \
         --cpu=4 --memory=4Gi \
         --region="${REG}" --project="${PROJECT_ID}"
     done
   done
   ```

2. **Persist updated capacity bounds in [`deployment/terraform/envs/prod.tfvars`](../deployment/terraform/envs/prod.tfvars):**
   ```hcl
   min_instances  = 4
   max_instances  = 50
   backend_cpu    = "4"
   backend_memory = "4Gi"
   ```
   Commit and run `./deployment/deploy.sh prod` once traffic stabilizes so future CD deployments do not revert your manual scaling override.

### 3. Verification Criteria
- Check `gcloud run services describe conversational-app --region=europe-west9 --project="${PROJECT_ID}" --format="yaml(spec.template.scaling,spec.template.containers[0].resources)"`.
- Monitor Vertex AI `429` rates ([`RB-03`](#rb-03-vertex-ai-quota-exhaustion-429-or-primary-model-degradation--emergency-model-swap))—increasing Cloud Run `max_instances` increases concurrent Gemini RPM!

---

## `RB-06`: Scheduled Multi-Region DR & Backup Verification Drills

| Field | Value |
| :--- | :--- |
| **Severity** | Routine Preventive Maintenance (escalate to `SEV-2` if a live `prod` drill fails) |
| **Cadence** | Weekly (`--probe-only`) · Monthly (Full live RTO drill + Backup restore drill) |
| **Scripts** | [`deployment/validate_dr.sh`](../deployment/validate_dr.sh), [`deployment/verify_backups.sh`](../deployment/verify_backups.sh) |
| **Required IAM** | `roles/run.viewer`, `roles/storage.objectViewer`, `roles/artifactregistry.reader` on target project |

### Step-by-Step Execution

1. **Offline Self-Check (Zero GCP Credentials Needed — Sanity-Checks Drill Logic):**
   ```bash
   ./deployment/validate_dr.sh --local-self-test
   ./deployment/verify_backups.sh --local-self-test
   ```

2. **Weekly Probe-Only Production DR Check (Zero Gemini Token Cost):**
   Verifies `/healthz=200`, `/readyz=200`, symmetric `/env-config.js` cross-region fallback URLs across Paris (`europe-west9`) and Belgium (`europe-west1`), and synthetic `127.0.0.1:1` → `europe-west1/readyz` failover RTO (`<= 25,000ms`):
   ```bash
   ./deployment/validate_dr.sh --env prod --probe-only
   ```

3. **Monthly Full Live Failover Drill (Includes Live Gemini Call on Warm Standby):**
   ```bash
   ./deployment/validate_dr.sh --env prod
   ```

4. **Monthly Non-Destructive Backup & Rollback Readiness Drill:**
   Verifies GCS versioning on `gs://travel-agent-prod-512211-tfstate`, restores the prior `.tfstate` generation to an isolated `/tmp` directory to validate schema/serial/lineage integrity, and verifies Artifact Registry image tag retention across both `europe-west9` and `europe-west1`:
   ```bash
   ./deployment/verify_backups.sh --env prod
   ```

### Verification Criteria
- Both scripts exit `0` and print `✅ Live Multi-Region DR & Failover Validation completed successfully!` and `✅ Infrastructure Backup & Restore Verification completed successfully!`.

---

## `RB-07`: IAM Drift Remediation & Default Service Account Hardening Audit

| Field | Value |
| :--- | :--- |
| **Severity** | Routine Quarterly Audit (or `SEV-2` if over-privileged default SAs are detected) |
| **Trigger / Symptom** | Security audit or manual console changes accidentally re-granting administrative roles to default Google Compute/Cloud Build service accounts. |
| **Required IAM** | `roles/resourcemanager.projectIamAdmin`, `roles/iam.serviceAccountAdmin` |

### Step-by-Step Execution

1. **Re-run the idempotent bootstrap hardener across all three environments:**
   ```bash
   ./deployment/bootstrap.sh all
   ```
   Step 5 of `bootstrap.sh` inspects project IAM bindings in `dev`, `staging`, and `prod` and strips any CI/CD admin roles found on `<PROJECT_NUMBER>@cloudbuild.gserviceaccount.com` or `<PROJECT_NUMBER>-compute@developer.gserviceaccount.com`.

2. **Audit live IAM bindings on runtime Service Accounts:**
   ```bash
   for PROJ in travel-agent-511710 travel-agent-staging-512211 travel-agent-prod-512211; do
     echo "=== ${PROJ} ==="
     gcloud projects get-iam-policy "${PROJ}" \
       --flatten="bindings[].members" \
       --filter="bindings.members:travel-agent-" \
       --format="table(bindings.members, bindings.role)"
   done
   ```

### Verification Criteria
- `travel-agent-frontend` holds **only** `roles/logging.logWriter`.
- `travel-agent-runtime` holds **only** `roles/aiplatform.user`, `roles/logging.logWriter`, and `roles/cloudtrace.agent`.

---

## `RB-08`: Intentional API Schema Change & OpenAPI 3.1 Snapshot Regeneration

| Field | Value |
| :--- | :--- |
| **Severity** | Routine Engineering Workflow |
| **Trigger / Symptom** | `tests/unit/test_api_versioning_and_contracts.py` fails locally or in `pr_checks.yaml` because live FastAPI OpenAPI specs diverged from committed `openapi.json`. |

### Step-by-Step Execution

1. **Verify Backward Compatibility Rules First:**
   - Never remove or change the type of existing fields on `/api/v1` endpoints without bumping major API routes.
   - Ensure request models preserve `model_config = ConfigDict(extra="ignore", ...)` and optional fields have safe defaults.
   - Ensure `Flight` fields remain 100% identical between [`flights_search_app/app/schema.py`](../flights_search_app/app/schema.py) and [`conversational_app/app/schema.py`](../conversational_app/app/schema.py).

2. **Regenerate deterministic OpenAPI 3.1 snapshots:**
   ```bash
   (cd flights_search_app && python3 -m app.export_openapi)
   (cd conversational_app && python3 -m app.export_openapi)
   ```

3. **Inspect the `git diff` on `openapi.json` and re-run contract unit tests:**
   ```bash
   git diff flights_search_app/openapi.json conversational_app/openapi.json
   (cd flights_search_app && python3 -m pytest tests/unit/test_api_versioning_and_contracts.py -v)
   (cd conversational_app && python3 -m pytest tests/unit/test_api_versioning_and_contracts.py -v)
   ```

4. **Update [`docs/api_documentation.md`](api_documentation.md)** if public fields, bounds, or endpoints changed, and commit `openapi.json` alongside your schema edit.

---

## `RB-09`: AI Quality Regression — Running the 7-Metric GEAP Eval & Loss Flywheel

| Field | Value |
| :--- | :--- |
| **Severity** | `SEV-3` / Pre-Release Quality Gate |
| **Trigger / Symptom** | User reports misrouted chat intents (`engage`), unneeded or missing Google Search calls (`filter_smart`), hallucinated/mutated flight prices, or evaluation prior to changing prompts or Gemini models. |
| **Required IAM** | Local ADC (`gcloud auth application-default login`) with `roles/aiplatform.user` |

### Step-by-Step Execution

1. **Activate the Python environment and run the 50-scenario 7-metric GEAP evaluation:**
   ```bash
   source .venv/bin/activate
   cd conversational_app

   python3 -m tests.eval.scripts.run_evaluation \
     --run-name "investigate_$(date +%Y%m%d)" \
     --description "Evaluate prompt/model quality across 50 synthetic scenarios"
   ```

2. **Check the generated summary and compare deltas against baseline:**
   - Inspect [`conversational_app/tests/eval/results/experiments_history.md`](../conversational_app/tests/eval/results/experiments_history.md) and the new timestamped folder's `eval_summary.md`.
   - Verify all 7 target thresholds:
     - `schema_and_contract_valid >= 0.95` (zero hallucinated flights, exact price immutability)
     - `multi_turn_task_success_v1 >= 0.80`
     - `multi_turn_trajectory_quality_v1 >= 0.80`
     - `tool_use_quality >= 0.80`
     - `coherence >= 0.80`
     - `conversation_plan_alignment >= 0.80`
     - `latency_seconds <= 15.0s`

3. **If any metric regressed, run automated LLM root-cause loss clustering:**
   ```bash
   python3 -m tests.eval.scripts.run_loss_analysis
   ```
   Inspect `loss_clusters.md` inside the run directory to pinpoint which sub-agent prompt (`engage/prompt.py`, `filter_smart/prompt.py`, etc.) caused the failure cluster, iterate on the prompt, and re-run Step 1 before deploying.
