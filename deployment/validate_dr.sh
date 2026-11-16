#!/usr/bin/env bash
# ==============================================================================
# Multi-Region Disaster Recovery (DR) & Regional Failover Validation Drill
#
# Validates active-passive / warm-standby readiness across Primary (europe-west9)
# and Warm Secondary (europe-west1), verifies symmetric cross-region URL wiring
# in /env-config.js, and executes a synthetic client-side primary-blackout
# failover drill measuring Recovery Time Objective (RTO).
#
# Usage:
#   ./deployment/validate_dr.sh --local-self-test
#   ./deployment/validate_dr.sh --env prod
#   ./deployment/validate_dr.sh --env prod --probe-only
# ==============================================================================
set -euo pipefail

MODE="gcp"
ENV_NAME="prod"
REGION="${REGION:-europe-west9}"
SECONDARY_REGION="${SECONDARY_REGION:-europe-west1}"
PROBE_ONLY="false"

PRIMARY_FLIGHTS_URL="${PRIMARY_FLIGHTS_URL:-}"
PRIMARY_CONV_URL="${PRIMARY_CONV_URL:-}"
PRIMARY_FRONTEND_URL="${PRIMARY_FRONTEND_URL:-}"
SECONDARY_FLIGHTS_URL="${SECONDARY_FLIGHTS_URL:-}"
SECONDARY_CONV_URL="${SECONDARY_CONV_URL:-}"
SECONDARY_FRONTEND_URL="${SECONDARY_FRONTEND_URL:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local-self-test)
      MODE="local-self-test"
      shift
      ;;
    --env)
      ENV_NAME="${2:?Missing value for --env}"
      shift 2
      ;;
    --probe-only)
      PROBE_ONLY="true"
      shift
      ;;
    --primary-flights-url)
      PRIMARY_FLIGHTS_URL="${2:?}"
      shift 2
      ;;
    --primary-conv-url)
      PRIMARY_CONV_URL="${2:?}"
      shift 2
      ;;
    --primary-frontend-url)
      PRIMARY_FRONTEND_URL="${2:?}"
      shift 2
      ;;
    --secondary-flights-url)
      SECONDARY_FLIGHTS_URL="${2:?}"
      shift 2
      ;;
    --secondary-conv-url)
      SECONDARY_CONV_URL="${2:?}"
      shift 2
      ;;
    --secondary-frontend-url)
      SECONDARY_FRONTEND_URL="${2:?}"
      shift 2
      ;;
    -h|--help)
      sed -n '2,13p' "$0"
      exit 0
      ;;
    *)
      echo "❌ Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

get_project_id() {
  case "$1" in
    dev)     echo "travel-agent-511710" ;;
    staging) echo "travel-agent-staging-512211" ;;
    prod)    echo "travel-agent-prod-512211" ;;
    *)
      echo "❌ Unknown environment: $1 (expected: dev | staging | prod)" >&2
      exit 1
      ;;
  esac
}

run_dr_assertions() {
  local p_flights="$1"
  local p_conv="$2"
  local p_front="$3"
  local s_flights="$4"
  local s_conv="$5"
  local s_front="$6"
  local probe_only="$7"
  local max_rto_ms="$8"

  python3 - "$p_flights" "$p_conv" "$p_front" "$s_flights" "$s_conv" "$s_front" "$probe_only" "$max_rto_ms" <<'PYEOF'
import json
import re
import sys
import time
import urllib.error
import urllib.request

(
    p_flights,
    p_conv,
    p_front,
    s_flights,
    s_conv,
    s_front,
    probe_only_str,
    max_rto_ms_str,
) = sys.argv[1:9]
probe_only = probe_only_str.lower() == "true"
max_rto_ms = float(max_rto_ms_str)


def http_get(url: str, timeout: float = 10.0) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8")


def parse_env_config(js_text: str) -> dict[str, str]:
    pairs = re.findall(r'([A-Z0-9_]+)\s*:\s*"([^"]*)"', js_text)
    return dict(pairs)


print("1️⃣  Probing /healthz and /readyz across Primary & Warm Secondary regions...")
endpoints = [
    ("Primary Flights Search", p_flights),
    ("Primary Conversational", p_conv),
    ("Primary Frontend", p_front),
    ("Secondary Flights Search", s_flights),
    ("Secondary Conversational", s_conv),
    ("Secondary Frontend", s_front),
]
for label, base_url in endpoints:
    for path in ("/healthz", "/readyz"):
        status, _ = http_get(f"{base_url.rstrip('/')}{path}")
        if status != 200:
            raise SystemExit(f"❌ {label} {path} returned HTTP {status} (expected 200)")
    print(f"   ✅ {label} ({base_url}) -> /healthz=200, /readyz=200")

print("2️⃣  Validating symmetric cross-region fallback wiring in /env-config.js...")
_, p_env_raw = http_get(f"{p_front.rstrip('/')}/env-config.js")
p_env = parse_env_config(p_env_raw)
assert p_env.get("VITE_FLIGHTS_SEARCH_API_URL") == p_flights, f"Primary env mismatch: {p_env}"
assert p_env.get("VITE_CONVERSATIONAL_API_URL") == p_conv, f"Primary env mismatch: {p_env}"
assert p_env.get("VITE_FLIGHTS_SEARCH_FALLBACK_API_URL") == s_flights, (
    f"Primary frontend missing warm secondary flights fallback URL: {p_env}"
)
assert p_env.get("VITE_CONVERSATIONAL_FALLBACK_API_URL") == s_conv, (
    f"Primary frontend missing warm secondary conversational fallback URL: {p_env}"
)
assert p_env["VITE_FLIGHTS_SEARCH_API_URL"] != p_env["VITE_FLIGHTS_SEARCH_FALLBACK_API_URL"], (
    "Primary and fallback Flights Search URLs must be distinct regions!"
)

_, s_env_raw = http_get(f"{s_front.rstrip('/')}/env-config.js")
s_env = parse_env_config(s_env_raw)
assert s_env.get("VITE_FLIGHTS_SEARCH_API_URL") == s_flights, f"Secondary env mismatch: {s_env}"
assert s_env.get("VITE_CONVERSATIONAL_API_URL") == s_conv, f"Secondary env mismatch: {s_env}"
assert s_env.get("VITE_FLIGHTS_SEARCH_FALLBACK_API_URL") == p_flights, (
    f"Secondary frontend missing cross-region flights fallback URL: {s_env}"
)
assert s_env.get("VITE_CONVERSATIONAL_FALLBACK_API_URL") == p_conv, (
    f"Secondary frontend missing cross-region conversational fallback URL: {s_env}"
)
print("   ✅ Symmetric cross-region /env-config.js wiring verified on both frontends")

print("3️⃣  Executing synthetic client-side primary-blackout failover drill (127.0.0.1:1 -> Warm Secondary)...")
blackhole_primary = "http://127.0.0.1:1"
target_path = "/readyz" if probe_only else "/run-conversational"
payload_bytes = (
    None
    if probe_only
    else json.dumps(
        {
            "user_message": "Hello",
            "conversational_history": [],
            "flights_search_input": {
                "origin": "Paris",
                "destination": "New York",
                "departure_date": "2026-05-10",
                "return_date": "2026-05-20",
                "passengers": 1,
            },
            "flights_input": [],
        }
    ).encode("utf-8")
)
method = "GET" if probe_only else "POST"
headers = {} if probe_only else {"Content-Type": "application/json"}

t0 = time.perf_counter()
failed_over = False
try:
    req = urllib.request.Request(
        f"{blackhole_primary}{target_path}",
        data=payload_bytes,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(req, timeout=2.0) as resp:
        if resp.status >= 500:
            raise urllib.error.HTTPError(req.full_url, resp.status, "5xx", resp.headers, None)
except Exception:
    failed_over = True
    fb_req = urllib.request.Request(
        f"{s_conv.rstrip('/')}{target_path}",
        data=payload_bytes,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(fb_req, timeout=25.0) as fb_resp:
        fb_status = fb_resp.status
        fb_body = fb_resp.read().decode("utf-8")

rto_ms = (time.perf_counter() - t0) * 1000.0
assert failed_over, "Expected primary blackhole endpoint to trigger regional failover"
assert fb_status == 200, f"Warm secondary failover returned HTTP {fb_status}: {fb_body}"
if not probe_only:
    parsed_fb = json.loads(fb_body)
    assert parsed_fb.get("status") == "success", f"Unexpected failover payload: {parsed_fb}"

assert rto_ms <= max_rto_ms, (
    f"Failover RTO {rto_ms:.1f}ms exceeded threshold {max_rto_ms:.1f}ms"
)
print(
    f"   ✅ Primary blackout failover succeeded via Warm Secondary in RTO={rto_ms:.1f}ms "
    f"(threshold <= {max_rto_ms:.0f}ms)"
)
PYEOF
}

if [[ "${MODE}" == "local-self-test" ]]; then
  echo "=============================================================================="
  echo "🧪 Running DR Validation Local Self-Test (Ephemeral Mock Primary & Secondary)"
  echo "=============================================================================="
  MOCK_INFO_FILE="$(mktemp)"
  SERVER_PID=""
  cleanup() {
    if [[ -n "${SERVER_PID}" ]]; then
      kill "${SERVER_PID}" >/dev/null 2>&1 || true
      wait "${SERVER_PID}" 2>/dev/null || true
    fi
    rm -f "${MOCK_INFO_FILE}"
  }
  trap cleanup EXIT

  python3 - "${MOCK_INFO_FILE}" <<'PYEOF' &
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
import threading
import time

info_path = sys.argv[1]
urls = {}


def make_handler(region_role: str):
    class MockCloudRunHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def do_GET(self):
            if self.path in ("/healthz", "/readyz"):
                body = json.dumps({"status": "ok", "role": region_role}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/env-config.js":
                if region_role == "primary":
                    cfg = (
                        'window.__ENV__ = {\n'
                        f'  VITE_FLIGHTS_SEARCH_API_URL: "{urls["p_base"]}",\n'
                        f'  VITE_CONVERSATIONAL_API_URL: "{urls["p_base"]}",\n'
                        f'  VITE_FLIGHTS_SEARCH_FALLBACK_API_URL: "{urls["s_base"]}",\n'
                        f'  VITE_CONVERSATIONAL_FALLBACK_API_URL: "{urls["s_base"]}"\n'
                        '};\n'
                    )
                else:
                    cfg = (
                        'window.__ENV__ = {\n'
                        f'  VITE_FLIGHTS_SEARCH_API_URL: "{urls["s_base"]}",\n'
                        f'  VITE_CONVERSATIONAL_API_URL: "{urls["s_base"]}",\n'
                        f'  VITE_FLIGHTS_SEARCH_FALLBACK_API_URL: "{urls["p_base"]}",\n'
                        f'  VITE_CONVERSATIONAL_FALLBACK_API_URL: "{urls["p_base"]}"\n'
                        '};\n'
                    )
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript")
                self.end_headers()
                self.wfile.write(cfg.encode("utf-8"))
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            _ = self.rfile.read(length) if length > 0 else b""
            if self.path == "/run-conversational":
                body = json.dumps(
                    {
                        "status": "success",
                        "results": {
                            "agent_decision": "continue",
                            "agent_response": f"Handled by {region_role} region.",
                        },
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

    return MockCloudRunHandler


p_srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler("primary"))
s_srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler("secondary"))
urls["p_base"] = f"http://127.0.0.1:{p_srv.server_address[1]}"
urls["s_base"] = f"http://127.0.0.1:{s_srv.server_address[1]}"

threading.Thread(target=p_srv.serve_forever, daemon=True).start()
threading.Thread(target=s_srv.serve_forever, daemon=True).start()

with open(info_path, "w", encoding="utf-8") as fh:
    json.dump(urls, fh)

while True:
    time.sleep(1)
PYEOF
  SERVER_PID=$!

  for _ in $(seq 1 30); do
    if [[ -s "${MOCK_INFO_FILE}" ]]; then
      break
    fi
    sleep 0.05
  done

  P_BASE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["p_base"])' "${MOCK_INFO_FILE}")"
  S_BASE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["s_base"])' "${MOCK_INFO_FILE}")"

  run_dr_assertions "${P_BASE}" "${P_BASE}" "${P_BASE}" "${S_BASE}" "${S_BASE}" "${S_BASE}" "false" "2000"
  echo "✅ DR validation local self-test passed!"
  exit 0
fi

PROJECT_ID="$(get_project_id "${ENV_NAME}")"
echo "=============================================================================="
echo "🌍 Validating Multi-Region DR Readiness [${ENV_NAME}] -> ${PROJECT_ID}"
echo "   Primary Region   : ${REGION}"
echo "   Secondary Region : ${SECONDARY_REGION}"
echo "=============================================================================="

resolve_service_url() {
  local svc_name="$1"
  local svc_region="$2"
  gcloud run services describe "${svc_name}" \
    --project="${PROJECT_ID}" \
    --region="${svc_region}" \
    --format="value(status.url)"
}

[[ -z "${PRIMARY_FLIGHTS_URL}" ]] && PRIMARY_FLIGHTS_URL="$(resolve_service_url "flights-search-app" "${REGION}")"
[[ -z "${PRIMARY_CONV_URL}" ]] && PRIMARY_CONV_URL="$(resolve_service_url "conversational-app" "${REGION}")"
[[ -z "${PRIMARY_FRONTEND_URL}" ]] && PRIMARY_FRONTEND_URL="$(resolve_service_url "frontend" "${REGION}")"
[[ -z "${SECONDARY_FLIGHTS_URL}" ]] && SECONDARY_FLIGHTS_URL="$(resolve_service_url "flights-search-app" "${SECONDARY_REGION}")"
[[ -z "${SECONDARY_CONV_URL}" ]] && SECONDARY_CONV_URL="$(resolve_service_url "conversational-app" "${SECONDARY_REGION}")"
[[ -z "${SECONDARY_FRONTEND_URL}" ]] && SECONDARY_FRONTEND_URL="$(resolve_service_url "frontend" "${SECONDARY_REGION}")"

run_dr_assertions \
  "${PRIMARY_FLIGHTS_URL}" \
  "${PRIMARY_CONV_URL}" \
  "${PRIMARY_FRONTEND_URL}" \
  "${SECONDARY_FLIGHTS_URL}" \
  "${SECONDARY_CONV_URL}" \
  "${SECONDARY_FRONTEND_URL}" \
  "${PROBE_ONLY}" \
  "25000"

echo "✅ Live Multi-Region DR & Failover Validation completed successfully!"
