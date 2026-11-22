#!/usr/bin/env bash
# Tek komutla Google Cloud Run + GCS 24 saatlik Lifecycle kurulumu
# Kullanım: PROJECT_ID=likya-studios REGION=europe-west1 bash deploy_cloudrun.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?PROJECT_ID env gerekli}"
REGION="${REGION:-europe-west1}"
SERVICE="${SERVICE:-likya-crosspost-api}"
BUCKET="${GCS_BUCKET_NAME:-likya-temp-videos-${PROJECT_ID}}"

echo "1) GCS geçici video bucket + 24 saatlik otomatik silme kuralı ayarlanıyor..."
gcloud storage buckets create "gs://${BUCKET}" --project="${PROJECT_ID}" --location="${REGION}" 2>/dev/null || true
gcloud storage buckets update "gs://${BUCKET}" --lifecycle-file=gcs_lifecycle.json

echo "2) Cloud Run servisi derlenip yayına alınıyor..."
gcloud run deploy "${SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --source=. \
  --allow-unauthenticated \
  --timeout=300 \
  --memory=1Gi \
  --set-env-vars="GCS_BUCKET_NAME=${BUCKET},USE_GCS_SIGNED_URL=true"

echo "TAMAM! Cloud Run URL'sini panelin '⚙️ Ayarlar' sekmesine yapıştırabilirsiniz."
