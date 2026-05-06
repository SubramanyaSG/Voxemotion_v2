# 🚀 VoxEmotion — Complete Azure App Service Deployment Guide

---

## 📋 What Was Changed From Your Original GitHub Project

| File | Change | Why |
|------|--------|-----|
| `app.py` | Updated | Fixed IP detection for Azure proxy (`X-Forwarded-For`), added Azure Blob model downloader, `SESSION_COOKIE_SECURE=True` on Azure |
| `config.py` | Updated | Removed `D:\...` Windows hardcoded `DATASET_ROOT`, added `AZURE_DEPLOYMENT` flag, Azure Blob env vars, port changed to `8000` |
| `requirements.txt` | Updated | Added `gunicorn` (required by Azure) and `azure-storage-blob` |
| `utils/dataset.py` | Updated | Graceful empty-DataFrame fallback when dataset is absent |
| `startup.sh` | **NEW** | Azure startup script — runs gunicorn correctly |
| `.github/workflows/azure-deploy.yml` | **NEW** | Auto-deploys to Azure on every `git push` to main |
| `.env.example` | Updated | Added Azure-specific variables |
| `.gitignore` | Updated | Excludes dataset, outputs, secrets |

### Files you keep EXACTLY as-is from your GitHub repo:
`models/synthesizer.py`, `models/emotion_model.py`, `utils/auth.py`,
`utils/text_utils.py`, `utils/audio.py`, `train.py`,
`templates/login.html`, `templates/index.html`, `templates/reset_password.html`,
`static/css/`, `static/js/`

---

## 🏗️ PART 1 — Azure Account Setup (One-time)

### Step 1.1 — Create Free Azure Account
1. Go to **https://azure.microsoft.com/free**
2. Sign up — you get **$200 free credits for 30 days** + always-free services
3. Verify your identity with a credit card (not charged unless you upgrade)

### Step 1.2 — Install Azure CLI (on your Windows PC)
```powershell
# Run in PowerShell as Administrator
winget install Microsoft.AzureCLI
```
Then restart your terminal and verify:
```bash
az --version
```

### Step 1.3 — Login to Azure CLI
```bash
az login
# A browser window opens — sign in with your Azure account
```

---

## 📦 PART 2 — Merge the Azure Files Into Your Project

### Step 2.1 — Copy files from this ZIP into your existing project folder

From this ZIP, copy these files into your `Voxemotion_v2` project folder:
```
app.py                          ← REPLACE existing
config.py                       ← REPLACE existing
requirements.txt                ← REPLACE existing
startup.sh                      ← NEW — add this
.env.example                    ← REPLACE existing
.gitignore                      ← REPLACE existing
utils/dataset.py                ← REPLACE existing
utils/__init__.py               ← ADD if missing
models/__init__.py              ← ADD if missing
outputs/.gitkeep                ← ADD if missing
.github/workflows/azure-deploy.yml  ← NEW — add this
```

**Keep these unchanged from your repo:**
```
models/synthesizer.py           ← DO NOT TOUCH
models/emotion_model.py         ← DO NOT TOUCH
models/waveglow_weights.pth     ← Keep (already in your repo)
models/tacotron2_weights.pth    ← Keep (already in your repo)
models/emotion_best.pth         ← Keep (already in your repo)
utils/auth.py                   ← DO NOT TOUCH
utils/text_utils.py             ← DO NOT TOUCH
utils/audio.py                  ← DO NOT TOUCH
templates/                      ← DO NOT TOUCH
static/                         ← DO NOT TOUCH
train.py                        ← DO NOT TOUCH
```

---

## ☁️ PART 3 — Create Azure App Service

### Step 3.1 — Create a Resource Group
```bash
az group create --name voxemotion-rg --location centralindia
# centralindia is closest to Mysuru — good choice for you
```

### Step 3.2 — Create App Service Plan (Free tier)
```bash
az appservice plan create \
  --name voxemotion-plan \
  --resource-group voxemotion-rg \
  --sku B1 \
  --is-linux
```
> ⚠️ **Important**: Use **B1** (Basic, ~$13/month) not Free tier.
> Free tier (F1) has only 60 CPU minutes/day — Tacotron2 will time out on F1.
> B1 gives you dedicated compute for model loading.

### Step 3.3 — Create the Web App
```bash
az webapp create \
  --name voxemotion \
  --resource-group voxemotion-rg \
  --plan voxemotion-plan \
  --runtime "PYTHON:3.10"
```
Your app URL will be: **https://voxemotion.azurewebsites.net**

> If `voxemotion` is taken, use `voxemotion-sg` or `voxemotion-app` etc.

### Step 3.4 — Set the Startup Command
```bash
az webapp config set \
  --name voxemotion \
  --resource-group voxemotion-rg \
  --startup-file "gunicorn --bind=0.0.0.0:8000 --timeout=600 --workers=1 --threads=2 app:app"
```

---

## ⚙️ PART 4 — Configure Environment Variables on Azure

Run these commands one by one — replace placeholder values with your real values:

```bash
az webapp config appsettings set \
  --name voxemotion \
  --resource-group voxemotion-rg \
  --settings \
    FLASK_SECRET_KEY="paste_any_64_char_random_string_here" \
    AZURE_DEPLOYMENT="true" \
    APP_BASE_URL="https://voxemotion.azurewebsites.net" \
    DATASET_ROOT="" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true" \
    WEBSITE_RUN_FROM_PACKAGE="0"
```

Optionally add email settings:
```bash
az webapp config appsettings set \
  --name voxemotion \
  --resource-group voxemotion-rg \
  --settings \
    SMTP_EMAIL="support.voxemotion@gmail.com" \
    SMTP_APP_PASSWORD="your_gmail_app_password"
```

---

## 🚀 PART 5 — Deploy Your Code

### Option A — Deploy via GitHub Actions (Recommended — Auto-deploy on push)

#### Step 5A.1 — Get your Publish Profile
```bash
az webapp deployment list-publishing-profiles \
  --name voxemotion \
  --resource-group voxemotion-rg \
  --xml > publish_profile.xml
```
Open `publish_profile.xml` — copy ALL its contents.

#### Step 5A.2 — Add GitHub Secrets
1. Go to your GitHub repo: `https://github.com/SubramanyaSG/Voxemotion_v2`
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** — add these two:
   - Name: `AZURE_WEBAPP_NAME` → Value: `voxemotion`
   - Name: `AZURE_PUBLISH_PROFILE` → Value: paste entire contents of `publish_profile.xml`

#### Step 5A.3 — Push to GitHub
```bash
cd your_project_folder
git add .
git commit -m "Azure deployment ready"
git push origin main
```
GitHub Actions will automatically deploy to Azure. Watch progress at:
`https://github.com/SubramanyaSG/Voxemotion_v2/actions`

---

### Option B — Deploy Directly via Azure CLI (Faster for first deploy)

```bash
cd your_project_folder

# Zip your project (exclude venv and dataset)
# On Windows PowerShell:
Compress-Archive -Path * -DestinationPath deploy.zip -Force

# Deploy the zip
az webapp deployment source config-zip \
  --name voxemotion \
  --resource-group voxemotion-rg \
  --src deploy.zip
```

---

## 🔍 PART 6 — Monitor & Debug

### View live logs
```bash
az webapp log tail --name voxemotion --resource-group voxemotion-rg
```

### View deployment logs in browser
```
https://voxemotion.scm.azurewebsites.net/api/logstream
```

### SSH into the running container
```bash
az webapp ssh --name voxemotion --resource-group voxemotion-rg
```

### Common Errors & Fixes

| Error in logs | Fix |
|---------------|-----|
| `ModuleNotFoundError: gunicorn` | Check requirements.txt has `gunicorn==21.2.0` |
| `Address already in use` | Startup command must use port `8000` |
| `Application Error 500 on /` | Check logs — likely model load failure |
| `Model file not found` | Verify `.pth` files are in `models/` folder and pushed to GitHub |
| `DATASET_ROOT not found` | Normal — inference mode works fine without dataset |
| Timeout during first load | Expected — Tacotron2 takes 60–90s to load. Increase timeout |
| `SessionCookie SameSite` warning | Harmless — already fixed in updated app.py |

---

## 🗂️ PART 7 — Optional: Azure Blob Storage for Model Files

If your model `.pth` files are too large for GitHub (>100MB each):

### Step 7.1 — Create Storage Account
```bash
az storage account create \
  --name voxemotionmodels \
  --resource-group voxemotion-rg \
  --sku Standard_LRS \
  --location centralindia

az storage container create \
  --name voxemotion-models \
  --account-name voxemotionmodels \
  --public-access off
```

### Step 7.2 — Upload model files to Blob
```bash
az storage blob upload-batch \
  --account-name voxemotionmodels \
  --destination voxemotion-models \
  --source ./models \
  --pattern "*.pth"
```

### Step 7.3 — Get connection string
```bash
az storage account show-connection-string \
  --name voxemotionmodels \
  --resource-group voxemotion-rg \
  --query connectionString
```

### Step 7.4 — Add to Azure App Settings
```bash
az webapp config appsettings set \
  --name voxemotion \
  --resource-group voxemotion-rg \
  --settings \
    AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=voxemotionmodels;..." \
    AZURE_BLOB_CONTAINER="voxemotion-models"
```
Now the app will automatically download models from Blob at startup.

---

## ✅ Final Checklist Before Going Live

- [ ] All `.pth` model files are in `models/` folder (or set up Azure Blob)
- [ ] `FLASK_SECRET_KEY` is set in Azure App Settings
- [ ] `AZURE_DEPLOYMENT=true` is set
- [ ] `APP_BASE_URL` matches your actual Azure URL
- [ ] Startup command is set to gunicorn
- [ ] GitHub Actions secrets are configured (if using auto-deploy)

---

## 🌐 Your App Will Be Live At:
```
https://voxemotion.azurewebsites.net
```
(or whatever name you chose in Step 3.3)

---
*Support: support_voxemotion@gmail.com*
