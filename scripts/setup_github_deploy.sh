#!/usr/bin/env bash
# One-time setup so .github/workflows/deploy.yml can sign in to Google Cloud with no stored key
# (Workload Identity Federation: GitHub's OIDC token is exchanged for a short-lived Google token).
#
#   DRY_RUN=1 bash scripts/setup_github_deploy.sh   # print the commands only
#   bash scripts/setup_github_deploy.sh             # run them (needs a gcloud login with owner/IAM admin on the project)
#
# Creates (skipping anything that already exists):
#   - service account grantha-deployer, with rights on the one VM only (no project-wide roles)
#   - workload identity pool + provider `github`, accepting tokens only from this repository's `production` environment
# Then prints the repository variables to set under Settings -> Secrets and variables -> Actions -> Variables.
set -euo pipefail

PROJECT=${GRANTHA_PROJECT:-project-dab42af9-0f52-4527-b40}
ZONE=${GRANTHA_ZONE:-us-central1-a}
VM=${GRANTHA_VM:-grantha-worker-eng}
REPO=${GITHUB_REPO:-rohannes64/Grantha-Heritage-Tracker}
POOL=github
PROVIDER=github
SA="grantha-deployer@$PROJECT.iam.gserviceaccount.com"

run() { echo "+ $*"; [ -n "${DRY_RUN:-}" ] || "$@"; }
exists() { "$@" >/dev/null 2>&1; }

NUM=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')

run gcloud services enable iamcredentials.googleapis.com sts.googleapis.com --project "$PROJECT"

exists gcloud iam service-accounts describe "$SA" --project "$PROJECT" ||
  run gcloud iam service-accounts create grantha-deployer --project "$PROJECT" \
      --display-name "GitHub Actions deploy of the Grantha app"

# deploy_vm.sh needs to: read the VM (its IP), copy a file and SSH in (gcloud puts a key in the VM's metadata),
# then sudo systemctl restart. instanceAdmin on this one instance covers the metadata change.
run gcloud compute instances add-iam-policy-binding "$VM" --zone "$ZONE" --project "$PROJECT" \
    --member "serviceAccount:$SA" --role roles/compute.instanceAdmin.v1
# Changing metadata of a VM that runs as a service account requires acting as that account.
VM_SA=$(gcloud compute instances describe "$VM" --zone "$ZONE" --project "$PROJECT" --format='value(serviceAccounts[0].email)')
if [ -n "$VM_SA" ]; then
  run gcloud iam service-accounts add-iam-policy-binding "$VM_SA" --project "$PROJECT" \
      --member "serviceAccount:$SA" --role roles/iam.serviceAccountUser
fi

exists gcloud iam workload-identity-pools describe "$POOL" --project "$PROJECT" --location global ||
  run gcloud iam workload-identity-pools create "$POOL" --project "$PROJECT" --location global \
      --display-name "GitHub Actions"

exists gcloud iam workload-identity-pools providers describe "$PROVIDER" --project "$PROJECT" --location global \
       --workload-identity-pool "$POOL" ||
  run gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --project "$PROJECT" --location global \
      --workload-identity-pool "$POOL" \
      --issuer-uri https://token.actions.githubusercontent.com \
      --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.environment=assertion.environment,attribute.ref=assertion.ref" \
      --attribute-condition "assertion.repository == '$REPO' && assertion.environment == 'production'"

run gcloud iam service-accounts add-iam-policy-binding "$SA" --project "$PROJECT" \
    --role roles/iam.workloadIdentityUser \
    --member "principalSet://iam.googleapis.com/projects/$NUM/locations/global/workloadIdentityPools/$POOL/attribute.repository/$REPO"

cat <<EOF

Done. Set these repository variables (Settings -> Secrets and variables -> Actions -> Variables; they are not secrets):
  GCP_WIF_PROVIDER = projects/$NUM/locations/global/workloadIdentityPools/$POOL/providers/$PROVIDER
  GCP_DEPLOY_SA    = $SA
  GCP_PROJECT      = $PROJECT
  GCP_ZONE         = $ZONE
  GCP_VM           = $VM
Then create the environment "production" (Settings -> Environments), add yourself as a required reviewer,
and limit it to the main branch. Test with Actions -> Deploy -> Run workflow -> "Only smoke-test" first.
EOF
