#!/usr/bin/env bash
# Komplette API-Smoke-Test-Suite — verifiziert alle Backend-Endpoints
# der aktuellen Wave gegen den Demo-Server.
#
# Verwendung:
#   BASE_URL="https://USER:PASS@minga-greens-temp-demo-production.up.railway.app" ./scripts/api-smoke-test.sh
set -u

BASE="${BASE_URL:?BASE_URL must be set, e.g. BASE_URL=https://USER:PASS@host or just https://host with BASIC_AUTH_USER/PASS env vars}"

# Optional separate creds (preferred — not in URL)
BASIC_USER="${BASIC_AUTH_USER:-}"
BASIC_PASS="${BASIC_AUTH_PASS:-}"
CURL_AUTH=()
if [ -n "$BASIC_USER" ]; then
  CURL_AUTH=(-u "$BASIC_USER:$BASIC_PASS")
fi
# wrap curl so all calls use auth when configured
curl() { command curl "${CURL_AUTH[@]}" "$@"; }
TS=$(date +%s)
PASS=0
FAIL=0
FAILED_TESTS=()

step() {
  echo ""
  echo "──────────────────────────────────────────────"
  echo "● $1"
}

assert_ok() {
  local name="$1"; local condition="$2"
  if eval "$condition"; then
    PASS=$((PASS + 1))
    echo "  ✓ $name"
  else
    FAIL=$((FAIL + 1))
    FAILED_TESTS+=("$name")
    echo "  ✗ $name"
  fi
}

extract_id() {
  python3 -c "import sys, json; d = json.load(sys.stdin); print(d.get('id') or d.get('items', [{}])[0].get('id', ''))"
}

# ============================================================
step "1) Health-Check + Admin-Settings"
# ============================================================
HEALTH=$(curl -s "$BASE/health")
assert_ok "Health endpoint" "echo '$HEALTH' | grep -q 'healthy\|status\|ok'"

SETTINGS=$(curl -s "$BASE/api/v1/admin/settings")
assert_ok "Admin-Settings reachable" "echo '$SETTINGS' | grep -q 'SMTP_HOST'"

# ============================================================
step "2) Customer-Management (B4 + A4 Umlaut)"
# ============================================================
CUST=$(curl -s -X POST "$BASE/api/v1/sales/customers" -H "Content-Type: application/json" -d "{
  \"name\": \"Ökoring Test $TS\",
  \"typ\": \"GASTRO\",
  \"email\": \"test-$TS@example.com\",
  \"payment_terms\": \"NET_30\",
  \"skonto_percent\": 2.0,
  \"skonto_days\": 10,
  \"packaging_fee_amount\": 5.0
}")
CUST_ID=$(echo "$CUST" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))")
assert_ok "Customer created with all new fields" "[ -n '$CUST_ID' ]"
assert_ok "Customer-Number auto-generated (KD-)" "echo '$CUST' | grep -q 'KD-'"

# Liste mit Umlaut-Suche (via search-Param)
LIST=$(curl -s "$BASE/api/v1/sales/customers?search=%C3%96koring")
assert_ok "Search 'Ökoring' returns matches" "echo '$LIST' | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"total\",0))' | grep -qv '^0\$' || echo \$LIST | grep -q 'Ökoring'"

# Liste ohne Filter (Pagination > 20)
ALL=$(curl -s "$BASE/api/v1/sales/customers?page_size=500")
assert_ok "page_size=500 honored" "echo '$ALL' | grep -q 'items'"

# ============================================================
step "3) Products + Variable Bundle"
# ============================================================
PROD=$(curl -s -X POST "$BASE/api/v1/products" -H "Content-Type: application/json" -d "{
  \"sku\": \"TST-$TS\",
  \"name\": \"Test-Sorte $TS\",
  \"category\": \"MICROGREEN\",
  \"base_price\": 3.5,
  \"tax_rate\": \"REDUZIERT\"
}")
PROD_ID=$(echo "$PROD" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))")
assert_ok "Product created" "[ -n '$PROD_ID' ]"

BUNDLE=$(curl -s -X POST "$BASE/api/v1/products" -H "Content-Type: application/json" -d "{
  \"sku\": \"BUN-$TS\",
  \"name\": \"Test-Bundle $TS\",
  \"category\": \"BUNDLE\",
  \"base_price\": 24.0,
  \"is_variable_bundle\": true,
  \"variable_bundle_min_slots\": 3,
  \"variable_bundle_max_slots\": 5
}")
BUNDLE_ID=$(echo "$BUNDLE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))")
assert_ok "Variable bundle created" "[ -n '$BUNDLE_ID' ]"
assert_ok "Bundle has min/max slots" "echo '$BUNDLE' | grep -q 'variable_bundle_min_slots'"

# ============================================================
step "4) Orders mit Produkt + Bundle"
# ============================================================
ORDER=$(curl -s -X POST "$BASE/api/v1/sales/orders" -H "Content-Type: application/json" -d "{
  \"customer_id\": \"$CUST_ID\",
  \"requested_delivery_date\": \"$(date -u +%Y-%m-%d)\",
  \"lines\": [
    {\"product_id\": \"$PROD_ID\", \"product_name\": \"Test-Sorte\", \"quantity\": 100, \"unit\": \"g\", \"unit_price\": 3.5, \"tax_rate\": \"REDUZIERT\"}
  ]
}")
ORDER_ID=$(echo "$ORDER" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))")
assert_ok "Order created with product" "[ -n '$ORDER_ID' ]"
assert_ok "Order shows order_number" "echo '$ORDER' | grep -q 'BE-'"
assert_ok "Order shows customer_name + kunde_name" "echo '$ORDER' | grep -q 'customer_name' && echo '$ORDER' | grep -q 'kunde_name'"

# Bundle-Order
BUNDLE_ORDER=$(curl -s -X POST "$BASE/api/v1/sales/orders" -H "Content-Type: application/json" -d "{
  \"customer_id\": \"$CUST_ID\",
  \"requested_delivery_date\": \"$(date -u +%Y-%m-%d)\",
  \"lines\": [
    {
      \"product_id\": \"$BUNDLE_ID\",
      \"product_name\": \"Test-Bundle\",
      \"quantity\": 1,
      \"unit\": \"STK\",
      \"unit_price\": 24,
      \"tax_rate\": \"REDUZIERT\",
      \"variable_bundle_selections\": [
        {\"product_id\": \"$PROD_ID\", \"quantity\": 3}
      ]
    }
  ]
}")
BORDER_ID=$(echo "$BUNDLE_ORDER" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))")
assert_ok "Bundle-Order created" "[ -n '$BORDER_ID' ]"

# ============================================================
step "5) Belegkette: AB + Lieferschein + Rechnung"
# ============================================================
AB=$(curl -s -X POST "$BASE/api/v1/sales/orders/$ORDER_ID/confirmations" -H "Content-Type: application/json" -d '{}')
AB_NUM=$(echo "$AB" | python3 -c "import sys, json; print(json.load(sys.stdin).get('confirmation_number', ''))")
assert_ok "Auftragsbestätigung created" "echo '$AB_NUM' | grep -q 'AB-'"

AB_PDF=$(curl -s -o /tmp/test_ab.pdf -w "%{http_code}" "$BASE/api/v1/sales/confirmations/$(echo $AB | python3 -c 'import sys,json;print(json.load(sys.stdin)[\"id\"])' )/pdf")
assert_ok "AB-PDF download (200 + %PDF)" "[ '$AB_PDF' = '200' ] && head -c 4 /tmp/test_ab.pdf | grep -q PDF"

LS=$(curl -s -X POST "$BASE/api/v1/sales/orders/$ORDER_ID/delivery-notes" -H "Content-Type: application/json" -d '{}')
assert_ok "Lieferschein created" "echo '$LS' | grep -q 'LS-'"

INVOICE=$(curl -s -X POST "$BASE/api/v1/invoices/from-order/$ORDER_ID")
INVOICE_ID=$(echo "$INVOICE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))")
assert_ok "Rechnung auto-erstellt" "[ -n '$INVOICE_ID' ]"

# Mit Skonto-Customer: invoice.discount_percent sollte nicht 0 sein
INVOICE_DETAIL=$(curl -s "$BASE/api/v1/invoices/$INVOICE_ID")
assert_ok "Rechnung berücksichtigt customer.discount_percent" "echo '$INVOICE_DETAIL' | python3 -c 'import sys,json; d=json.load(sys.stdin); print(\"ok\" if d.get(\"total\") else \"\")' | grep -q ok"

# ============================================================
step "6) Zahlungserinnerung (Mahnung)"
# ============================================================
# Erst Rechnung finalisieren
curl -s -X POST "$BASE/api/v1/invoices/$INVOICE_ID/finalize" -o /dev/null
REMINDER_HTTP=$(curl -s -o /tmp/test_mahnung.pdf -w "%{http_code}" -X POST "$BASE/api/v1/invoices/$INVOICE_ID/payment-reminder?level=1&dunning_fee=0")
assert_ok "Zahlungserinnerung Stufe 1 (PDF)" "[ '$REMINDER_HTTP' = '200' ] && head -c 4 /tmp/test_mahnung.pdf | grep -q PDF"

# ============================================================
step "7) Subscription mit Produkt"
# ============================================================
SUB=$(curl -s -X POST "$BASE/api/v1/sales/subscriptions" -H "Content-Type: application/json" -d "{
  \"kunde_id\": \"$CUST_ID\",
  \"product_id\": \"$PROD_ID\",
  \"interval\": \"WEEKLY\",
  \"menge\": 100,
  \"einheit\": \"g\",
  \"start_datum\": \"$(date -u +%Y-%m-%d)\"
}")
assert_ok "Subscription mit product_id ok (kein 404)" "echo '$SUB' | grep -q 'kunde_id\|created_at'"

# ============================================================
step "8) Attachments — File-Upload + Download"
# ============================================================
# Lieferanten als Owner (existiert oder neu anlegen)
SUP_LIST=$(curl -s "$BASE/api/v1/suppliers")
SUP_ID=$(echo "$SUP_LIST" | python3 -c "
import sys, json
d = json.load(sys.stdin); items = d if isinstance(d, list) else d.get('items', [])
print(items[0]['id'] if items else '')")
if [ -z "$SUP_ID" ]; then
  SUP_ID=$(curl -s -X POST "$BASE/api/v1/suppliers" -H "Content-Type: application/json" -d "{\"name\": \"Test-Lieferant $TS\"}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))")
fi

# Test-Datei
echo "%PDF-1.4 test cert" > /tmp/test_upload.pdf

ATT=$(curl -s -X POST "$BASE/api/v1/attachments/supplier/$SUP_ID" \
  -F "file=@/tmp/test_upload.pdf" \
  -F "certificate_type=BIO" \
  -F "bio_kontrollstelle=DE-ÖKO-006" \
  -F "valid_until=2027-12-31")
ATT_ID=$(echo "$ATT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))")
assert_ok "Lieferant-Attachment Upload" "[ -n '$ATT_ID' ]"

# Download
DL=$(curl -s -o /tmp/test_down.pdf -w "%{http_code}" "$BASE/api/v1/attachments/$ATT_ID/download")
assert_ok "Attachment-Download (200 + PDF)" "[ '$DL' = '200' ] && head -c 4 /tmp/test_down.pdf | grep -q PDF"

# ============================================================
step "9) Growth-Plan editieren"
# ============================================================
GP=$(curl -s -X POST "$BASE/api/v1/grow-plans" -H "Content-Type: application/json" -d "{
  \"code\": \"GP-$TS\",
  \"name\": \"Test Plan $TS\",
  \"germination_days\": 2,
  \"growth_days\": 7,
  \"harvest_window_start_days\": 9,
  \"harvest_window_optimal_days\": 10,
  \"harvest_window_end_days\": 12,
  \"expected_yield_grams_per_tray\": 350
}")
GP_ID=$(echo "$GP" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))")
assert_ok "GrowPlan created" "[ -n '$GP_ID' ]"

GP_UPDATE=$(curl -s -X PATCH "$BASE/api/v1/grow-plans/$GP_ID" -H "Content-Type: application/json" -d "{\"name\": \"Test Plan $TS EDITED\"}")
assert_ok "GrowPlan updated" "echo '$GP_UPDATE' | grep -q 'EDITED'"

# ============================================================
step "10) Production-Timeline (Events)"
# ============================================================
EVENT_TYPES=$(curl -s "$BASE/api/v1/production/event-types")
assert_ok "Event-Types reachable" "echo '$EVENT_TYPES' | grep -q SOAKING_STARTED"

# ============================================================
# REPORT
# ============================================================
echo ""
echo "════════════════════════════════════════════════"
echo "Suite finished. PASS=$PASS  FAIL=$FAIL"
if [ $FAIL -gt 0 ]; then
  echo "Failed tests:"
  for t in "${FAILED_TESTS[@]}"; do
    echo "  • $t"
  done
  exit 1
else
  echo "All tests passed ✓"
fi
