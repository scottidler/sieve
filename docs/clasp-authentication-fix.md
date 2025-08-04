# Clasp Authentication Fix for GitHub Actions

## Problem Summary

The GitHub Actions workflow was failing with the error:
```
Error retrieving access token: TypeError: Cannot read properties of undefined (reading 'access_token')
```

This error occurs because the `.clasprc.json` file structure from `clasp login` doesn't match what clasp expects when authenticating in CI environments.

## Root Cause

After extensive research, the issue is that **clasp requires different authentication methods for CI/automated environments**:

1. **`clasp login`** creates a global authentication file suitable for interactive use
2. **`clasp login --creds <file>`** requires a GCP OAuth client credentials file for automated/CI use

The key insight comes from multiple sources showing that clasp has **two login modes**:
- **Global login**: `clasp login` (interactive, browser-based)
- **Local login**: `clasp login --creds <credentials.json>` (automated, uses GCP OAuth client)

## Sources

- [ChaddPortwine/AppsScript-CLASP](https://github.com/ChaddPortwine/AppsScript-CLASP) - Documents the "LOGIN TWICE" requirement
- [daikikatsuragawa/clasp-action](https://github.com/daikikatsuragawa/clasp-action) - Working GitHub Action showing required token structure
- [Stack Overflow: CLASP Local Login](https://stackoverflow.com/questions/60838607/clasp-local-login) - Explains GCP OAuth client setup
- [nikukyugamer/boilerplate-clasp](https://github.com/nikukyugamer/boilerplate-clasp) - Shows `.clasprc.json` sample structure

## Solution: Use GCP OAuth Client Credentials

Instead of using the output from `clasp login`, we need to create and use GCP OAuth 2.0 client credentials.

### Step 1: Create GCP OAuth 2.0 Client ID

1. **Go to Google Cloud Console**:
   - Navigate to: https://console.cloud.google.com/apis/credentials
   - Make sure you're in the correct project (or create a new one if needed)

2. **Create OAuth Client ID**:
   - Click **"+ CREATE CREDENTIALS"**
   - Select **"OAuth client ID"**

3. **Configure OAuth Consent Screen** (if not already done):
   - If prompted, click **"CONFIGURE CONSENT SCREEN"**
   - Choose **"External"** user type
   - Click **"CREATE"**
   - Fill in required fields:
     - **App name**: "Clasp CI/CD"
     - **User support email**: Your email
     - **Developer contact email**: Your email
   - Click **"SAVE AND CONTINUE"** through all steps
   - Add your email as a test user if needed

4. **Create the OAuth Client**:
   - Back on the credentials page, click **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
   - **Application type**: Select **"Desktop application"**
   - **Name**: "Clasp GitHub Actions"
   - Click **"CREATE"**

5. **Download Credentials**:
   - Click the **download button** (⬇️) next to your newly created OAuth client
   - Save the file (it will be named something like `client_secret_xxxxx.json`)

### Step 2: Extract Required Information

The downloaded JSON file will look like this:
```json
{
  "installed": {
    "client_id": "xxxxx.apps.googleusercontent.com",
    "project_id": "your-project-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "GOCSPX-xxxxx",
    "redirect_uris": ["http://localhost"]
  }
}
```

### Step 3: Perform Local Authentication

1. **Use the credentials file locally**:
   ```bash
   clasp login --creds /path/to/downloaded/client_secret.json
   ```

2. **This will create a proper `.clasprc.json`** in your project directory with the correct structure:
   ```json
   {
     "token": {
       "access_token": "ya29.xxxxx",
       "refresh_token": "1//xxxxx",
       "scope": "https://www.googleapis.com/auth/script.projects https://www.googleapis.com/auth/script.webapp.deploy https://www.googleapis.com/auth/logging.read https://www.googleapis.com/auth/service.management https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/script.deployments",
       "token_type": "Bearer",
       "expiry_date": 1234567890123
     },
     "oauth2ClientSettings": {
       "clientId": "xxxxx.apps.googleusercontent.com",
       "clientSecret": "GOCSPX-xxxxx",
       "redirectUri": "http://localhost"
     }
   }
   ```

### Step 4: Update GitHub Secrets

1. **Encode the authentication file**:
   ```bash
   base64 -w 0 ~/.clasprc.json
   ```
   (or use the `.clasprc.json` created in your project directory)

2. **Update GitHub Secrets**:
   - Go to your repository → **Settings** → **Secrets and variables** → **Actions**
   - Update both secrets with the **same base64-encoded value**:
     - `SIEVE_CLASP_TOKEN_HOME`
     - `SIEVE_CLASP_TOKEN_WORK`

### Step 5: Enable Required APIs

Make sure the following APIs are enabled in your Google Cloud Project:

1. **Google Apps Script API**:
   - Go to: https://console.cloud.google.com/apis/enableflow?apiid=script
   - Click **"ENABLE"**

2. **Google Drive API** (if needed):
   - Go to: https://console.cloud.google.com/apis/enableflow?apiid=drive
   - Click **"ENABLE"**

### Step 6: Verify OAuth Scopes

Ensure your Apps Script project (`appsscript.json`) includes the necessary OAuth scopes:

```json
{
  "timeZone": "America/New_York",
  "dependencies": {},
  "exceptionLogging": "STACKDRIVER",
  "runtimeVersion": "V8",
  "oauthScopes": [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/script.external_request"
  ]
}
```

## Key Differences from Previous Approach

1. **Authentication Method**: Using GCP OAuth client credentials instead of `clasp login` output
2. **Token Structure**: The proper `.clasprc.json` has nested `token` and `oauth2ClientSettings` objects
3. **Permissions**: OAuth client has the correct scopes for clasp operations
4. **Refresh Capability**: The refresh token allows automatic token renewal

## Testing

After updating the GitHub secrets, trigger a workflow to test:

```bash
echo "# Test OAuth client credentials" >> configs/home-config.yml
git add configs/home-config.yml
git commit -m "Test OAuth client credentials for clasp authentication"
git push
```

The workflow should now successfully authenticate and push to Google Apps Script.

## Troubleshooting

If you still encounter issues:

1. **Verify API is enabled**: Ensure Google Apps Script API is enabled in your GCP project
2. **Check OAuth scopes**: Make sure your `appsscript.json` has the required scopes
3. **Regenerate credentials**: Create a new OAuth client and repeat the process
4. **Check token expiry**: If tokens are old, re-run `clasp login --creds` locally

## References

- [Google Apps Script Clasp Documentation](https://github.com/google/clasp)
- [ChaddPortwine CLASP Setup Guide](https://github.com/ChaddPortwine/AppsScript-CLASP)
- [Stack Overflow: CLASP Local Login](https://stackoverflow.com/questions/60838607/clasp-local-login)
- [Working Clasp GitHub Actions Examples](https://github.com/daikikatsuragawa/clasp-action) 