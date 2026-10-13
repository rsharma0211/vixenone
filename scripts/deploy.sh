#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

DRY_RUN="${DRY_RUN:-0}"

# Parse command line flags
COMMAND=""
for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=1
      ;;
    *)
      if [ -z "$COMMAND" ]; then
        COMMAND="$arg"
      fi
      ;;
  esac
done

if [ -z "$COMMAND" ]; then
  echo "Usage: $0 [--dry-run] <config|build-api|migrate|deploy-api|build-web|bundle-check|deploy-web|smoke|seed|deploy>" >&2
  exit 1
fi

load_config() {
  if [ ! -f "$ENV_FILE" ]; then
    echo "Error: Root .env file not found at ${ENV_FILE}" >&2
    exit 1
  fi

  while IFS='=' read -r key val || [ -n "$key" ]; do
    key=$(echo "$key" | tr -d '\r' | xargs 2>/dev/null || echo "$key" | tr -d '\r')
    [[ "$key" =~ ^#.* ]] && continue
    [ -z "$key" ] && continue
    if [[ "$key" == PROD_* ]]; then
      if [ -z "${!key+x}" ]; then
        val=$(echo "$val" | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
        export "$key=$val"
      fi
    fi
  done < "$ENV_FILE"

  MISSING=()
  for var in \
    PROD_PROJECT_ID \
    PROD_REGION \
    PROD_ARTIFACT_REPO \
    PROD_SQL_CONNECTION_NAME \
    PROD_SERVICE_ACCOUNT \
    PROD_BUCKET \
    PROD_GEMINI_MODEL \
    PROD_FIREBASE_API_KEY \
    PROD_FIREBASE_AUTH_DOMAIN \
    PROD_FIREBASE_PROJECT_ID; do
    if [ -z "${!var:-}" ]; then
      MISSING+=("$var")
    fi
  done

  if [ ${#MISSING[@]} -gt 0 ]; then
    echo "Error: Missing required production configuration variables in .env:" >&2
    for m in "${MISSING[@]}"; do
      echo "  - $m" >&2
    done
    exit 1
  fi

  COMMIT_SHA=$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo "latest")
  IMAGE_URI="${PROD_REGION}-docker.pkg.dev/${PROD_PROJECT_ID}/${PROD_ARTIFACT_REPO}/vixenone-api:${COMMIT_SHA}"
}

run_cloud_cmd() {
  if [ "$DRY_RUN" = "1" ]; then
    echo "[dry-run] $*"
  else
    echo "==> Running: $*"
    if [ "$1" = "gcloud" ] && ! command -v gcloud >/dev/null 2>&1; then
      "${REPO_ROOT}/scripts/cloud-tools.sh" "$@"
    elif [ "$1" = "firebase" ] && ! command -v firebase >/dev/null 2>&1; then
      "${REPO_ROOT}/scripts/cloud-tools.sh" "$@"
    else
      "$@"
    fi
  fi
}

step_config() {
  load_config
  echo "Production configuration:"
  echo "  PROD_PROJECT_ID:           ${PROD_PROJECT_ID}"
  echo "  PROD_REGION:               ${PROD_REGION}"
  echo "  PROD_ARTIFACT_REPO:        ${PROD_ARTIFACT_REPO}"
  echo "  PROD_SQL_CONNECTION_NAME:  ${PROD_SQL_CONNECTION_NAME}"
  echo "  PROD_SERVICE_ACCOUNT:      ${PROD_SERVICE_ACCOUNT}"
  echo "  PROD_BUCKET:               ${PROD_BUCKET}"
  echo "  PROD_GEMINI_MODEL:         ${PROD_GEMINI_MODEL}"
  echo "  PROD_FIREBASE_API_KEY:     [configured]"
  echo "  PROD_FIREBASE_AUTH_DOMAIN: ${PROD_FIREBASE_AUTH_DOMAIN}"
  echo "  PROD_FIREBASE_PROJECT_ID:  ${PROD_FIREBASE_PROJECT_ID}"
}

step_build_api() {
  load_config

  # Refuse if git working tree has uncommitted changes (tracked or untracked in codebase)
  cd "${REPO_ROOT}"
  UNCOMMITTED=$(git status --porcelain | grep -v '^[?]\{2\} dataset/' || true)
  if [ -n "$UNCOMMITTED" ]; then
    if [ "$DRY_RUN" = "1" ]; then
      echo "[dry-run] Git working tree check: uncommitted changes detected (real deploy will refuse)."
    else
      echo "Refusal: Git working tree has uncommitted changes. Commit or stash them before deploying." >&2
      exit 1
    fi
  fi

  echo "Building production API image with Cloud Build (tag: ${COMMIT_SHA})..."
  run_cloud_cmd gcloud builds submit \
    --project "${PROD_PROJECT_ID}" \
    --region "${PROD_REGION}" \
    --tag "${IMAGE_URI}" \
    backend
}

step_migrate() {
  load_config
  echo "Deploying Cloud Run prepare job (mode: migrate)..."
  run_cloud_cmd gcloud run jobs deploy vixenone-prepare \
    --image "${IMAGE_URI}" \
    --args="prepare,migrate" \
    --service-account "${PROD_SERVICE_ACCOUNT}" \
    --region "${PROD_REGION}" \
    --project "${PROD_PROJECT_ID}" \
    --set-cloudsql-instances "${PROD_SQL_CONNECTION_NAME}" \
    --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,DATABASE_URL=DATABASE_URL:latest" \
    --set-env-vars "ENV=production,STORAGE_BACKEND=gcs,STORAGE_BUCKET_NAME=${PROD_BUCKET},FIREBASE_PROJECT_ID=${PROD_FIREBASE_PROJECT_ID},GEMINI_MODEL=${PROD_GEMINI_MODEL}" \
    --max-retries=0 \
    --task-timeout=10m

  echo "Executing Cloud Run prepare job and waiting for completion..."
  run_cloud_cmd gcloud run jobs execute vixenone-prepare \
    --project "${PROD_PROJECT_ID}" \
    --region "${PROD_REGION}" \
    --wait
}

step_deploy_api() {
  load_config
  echo "Deploying Cloud Run service 'vixenone-api'..."
  run_cloud_cmd gcloud run deploy vixenone-api \
    --image "${IMAGE_URI}" \
    --service-account "${PROD_SERVICE_ACCOUNT}" \
    --region "${PROD_REGION}" \
    --project "${PROD_PROJECT_ID}" \
    --set-cloudsql-instances "${PROD_SQL_CONNECTION_NAME}" \
    --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,DATABASE_URL=DATABASE_URL:latest" \
    --set-env-vars "ENV=production,STORAGE_BACKEND=gcs,STORAGE_BUCKET_NAME=${PROD_BUCKET},FIREBASE_PROJECT_ID=${PROD_FIREBASE_PROJECT_ID},GEMINI_MODEL=${PROD_GEMINI_MODEL}" \
    --no-cpu-throttling \
    --min-instances=1 \
    --max-instances=1 \
    --memory=1Gi \
    --timeout=300s \
    --allow-unauthenticated
}

step_build_web() {
  load_config
  echo "Building production frontend in one-off web container..."
  if [ "$DRY_RUN" = "1" ]; then
    echo "[dry-run] rm -rf ${REPO_ROOT}/frontend/dist"
    echo "[dry-run] docker compose run --rm --no-deps -T -e VITE_FIREBASE_API_KEY=\"***\" -e VITE_FIREBASE_AUTH_DOMAIN=\"${PROD_FIREBASE_AUTH_DOMAIN}\" -e VITE_FIREBASE_PROJECT_ID=\"${PROD_FIREBASE_PROJECT_ID}\" -e VITE_FIREBASE_AUTH_EMULATOR_HOST=\"\" -e VITE_API_BASE_URL=\"\" web npm run build"
    return 0
  fi

  rm -rf "${REPO_ROOT}/frontend/dist"
  cd "${REPO_ROOT}"
  docker compose run --rm --no-deps -T \
    -e VITE_FIREBASE_API_KEY="${PROD_FIREBASE_API_KEY}" \
    -e VITE_FIREBASE_AUTH_DOMAIN="${PROD_FIREBASE_AUTH_DOMAIN}" \
    -e VITE_FIREBASE_PROJECT_ID="${PROD_FIREBASE_PROJECT_ID}" \
    -e VITE_FIREBASE_AUTH_EMULATOR_HOST="" \
    -e VITE_API_BASE_URL="" \
    web npm run build
}

step_bundle_check() {
  load_config
  echo "Checking built bundle in frontend/dist..."
  if [ "$DRY_RUN" = "1" ]; then
    echo "[dry-run] Bundle check: verify PROD_FIREBASE_API_KEY presence and reject forbidden tokens in frontend/dist"
    return 0
  fi

  DIST_DIR="${REPO_ROOT}/frontend/dist"
  if [ ! -d "$DIST_DIR" ] || [ -z "$(ls -A "$DIST_DIR" 2>/dev/null)" ]; then
    echo "Bundle check FAILED: Build directory ${DIST_DIR} not found or empty. Run build-web first." >&2
    exit 1
  fi

  # Rule 1: PROD_FIREBASE_API_KEY must be present in the bundle
  if grep -q -r -F "$PROD_FIREBASE_API_KEY" "$DIST_DIR"; then
    echo "  [PASS] Production Firebase API key present in bundle."
  else
    echo "Bundle check FAILED: Production Firebase API key not found in built bundle." >&2
    exit 1
  fi

  # Rule 2: Prohibited test tokens and localhost references
  FORBIDDEN_TOKENS=(
    "dummy-key"
    "test-key"
    "fake-api-key"
    "localhost:8000"
    "localhost:9099"
  )

  FORBIDDEN_FOUND=0
  for token in "${FORBIDDEN_TOKENS[@]}"; do
    if grep -q -r -F "$token" "$DIST_DIR"; then
      echo "Bundle check FAILED: Forbidden token '$token' found in built bundle." >&2
      FORBIDDEN_FOUND=1
    fi
  done

  if [ "$FORBIDDEN_FOUND" -ne 0 ]; then
    echo "Bundle check ABORTED: One or more forbidden tokens detected in bundle." >&2
    exit 1
  fi

  echo "  [PASS] No forbidden test tokens or localhost URLs found in bundle."
  echo "Bundle check PASSED."
}

step_deploy_web() {
  step_build_web
  step_bundle_check
  load_config
  echo "Deploying frontend to Firebase Hosting..."
  run_cloud_cmd firebase deploy --only hosting --project "${PROD_PROJECT_ID}"
}

step_smoke() {
  load_config
  HEALTH_URL="https://${PROD_PROJECT_ID}.web.app/api/health"
  ME_URL="https://${PROD_PROJECT_ID}.web.app/api/me"

  if [ "$DRY_RUN" = "1" ]; then
    echo "[dry-run] curl -s -o /dev/null -w \"%{http_code}\" \"${HEALTH_URL}\" (verify HTTP 200)"
    echo "[dry-run] curl -s -o /dev/null -w \"%{http_code}\" \"${ME_URL}\" (verify HTTP 401 without token)"
  else
    echo "Smoke check: GET ${HEALTH_URL}"
    HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_URL}")
    HEALTH_BODY=$(curl -s "${HEALTH_URL}")
    echo "  Status: ${HEALTH_STATUS}"
    echo "  Body:   ${HEALTH_BODY}"
    if [ "$HEALTH_STATUS" != "200" ]; then
      echo "Smoke check failed: expected HTTP 200 on ${HEALTH_URL}, got ${HEALTH_STATUS}" >&2
      exit 1
    fi

    echo "Smoke check: GET ${ME_URL} (unauthenticated)"
    ME_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${ME_URL}")
    ME_BODY=$(curl -s "${ME_URL}")
    echo "  Status: ${ME_STATUS}"
    echo "  Body:   ${ME_BODY}"
    if [ "$ME_STATUS" != "401" ]; then
      echo "Smoke check failed: expected HTTP 401 on ${ME_URL}, got ${ME_STATUS}" >&2
      exit 1
    fi
    echo "Smoke check PASSED: /api/health returned 200 and unauthenticated /api/me returned 401."
  fi
}

step_seed() {
  load_config
  if [ "$DRY_RUN" = "1" ]; then
    echo "[dry-run] Confirmation check: require typing project id '${PROD_PROJECT_ID}' from terminal"
    echo "[dry-run] gcloud run jobs execute vixenone-prepare --project \"${PROD_PROJECT_ID}\" --region \"${PROD_REGION}\" --args=\"prepare,seed\" --wait"
    return 0
  fi

  if ! [ -e /dev/tty ] || ! (exec 3</dev/tty) 2>/dev/null; then
    echo "Error: No terminal available for confirmation prompt. Aborting." >&2
    exit 1
  fi

  echo "WARNING: Running seed will wipe demo-user evaluations in project '${PROD_PROJECT_ID}'."
  echo -n "Type the project id '${PROD_PROJECT_ID}' to confirm: "
  read -r CONFIRM_PROJECT </dev/tty
  if [ "$CONFIRM_PROJECT" != "$PROD_PROJECT_ID" ]; then
    echo "Aborting: confirmation '${CONFIRM_PROJECT}' did not match '${PROD_PROJECT_ID}'." >&2
    exit 1
  fi

  echo "Executing prepare job in mode seed..."
  run_cloud_cmd gcloud run jobs execute vixenone-prepare \
    --project "${PROD_PROJECT_ID}" \
    --region "${PROD_REGION}" \
    --args="prepare,seed" \
    --wait
}

step_deploy() {
  step_config
  step_build_api
  step_migrate
  step_deploy_api
  step_deploy_web
  step_smoke
}

case "$COMMAND" in
  config)
    step_config
    ;;
  build-api)
    step_build_api
    ;;
  migrate)
    step_migrate
    ;;
  deploy-api)
    step_build_api
    step_migrate
    step_deploy_api
    ;;
  build-web)
    step_build_web
    ;;
  bundle-check)
    step_bundle_check
    ;;
  deploy-web)
    step_deploy_web
    ;;
  smoke)
    step_smoke
    ;;
  seed)
    step_seed
    ;;
  deploy)
    step_deploy
    ;;
  *)
    echo "Unknown command: $COMMAND" >&2
    exit 1
    ;;
esac
