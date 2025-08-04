# Clasp Authentication Troubleshooting - Complete History

## Problem Summary

**Primary Error**: `Error retrieving access token: TypeError: Cannot read properties of undefined (reading 'access_token')`

This error occurs consistently when GitHub Actions attempts to use clasp to push code to Google Apps Script, despite multiple different authentication approaches and configurations.

## System Configuration

- **Project**: Sieve Gmail automation system
- **Technology Stack**: TypeScript, Google Apps Script, GitHub Actions, clasp CLI
- **Target**: Deploy to Google Apps Script for Gmail automation
- **GitHub Repository**: scottidler/sieve
- **Affected Workflows**: 
  - `.github/workflows/deploy-home.yml`
  - `.github/workflows/deploy-work.yml`

## Authentication Methods Attempted

### 1. Standard `clasp login` Approach (FAILED)

**Method**: Used output from `clasp login` command
**Steps Taken**:
1. Ran `clasp login` locally
2. Copied contents of `~/.clasprc.json`
3. Base64 encoded the content: `base64 -w 0 ~/.clasprc.json`
4. Added to GitHub Secrets as `SIEVE_CLASP_TOKEN_HOME`

**Result**: Failed with access token error
**Token Structure**: 
```json
{
  "tokens": {
    "default": {
      "access_token": "...",
      "refresh_token": "...",
      "token_type": "Bearer",
      "expiry_date": 1234567890
    }
  }
}
```

### 2. OAuth Client Credentials Approach (FAILED)

**Method**: Created GCP OAuth 2.0 Client ID and used `clasp login --creds`
**Detailed Steps**:

#### Step 2.1: Create GCP OAuth 2.0 Client ID
1. Navigated to Google Cloud Console: https://console.cloud.google.com/apis/credentials
2. Selected existing project (or created new one)
3. Clicked **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
4. Configured OAuth Consent Screen:
   - User type: **External**
   - App name: "Clasp CI/CD"
   - User support email: scott.a.idler@gmail.com
   - Developer contact email: scott.a.idler@gmail.com
5. Created OAuth Client:
   - Application type: **Desktop application**
   - Name: "Clasp GitHub Actions"
6. Downloaded credentials file (format: `client_secret_xxxxx.json`)

#### Step 2.2: OAuth Client Credentials File Structure
Downloaded file contained:
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

#### Step 2.3: Local Authentication with OAuth Credentials
1. Ran: `clasp login --creds /path/to/client_secret_xxxxx.json`
2. Completed browser-based OAuth flow
3. Generated `.clasprc.json` with structure:
```json
{
  "tokens": {
    "default": {
      "client_id": "972766819723-s97pb1ldo9L41vC9pvgZhtgcOr01t1.apps.googleusercontent.com",
      "client_secret": "GOCSPX-0N5RreTNJGuhnZdOjpD6cR",
      "type": "authorized_user",
      "refresh_token": "1//06f5GuHh-ZbdUCgYIARAAGAYSNwF-L9IrEtJn...",
      "access_token": "ya29.A0AS3H6NzQuFUcSEOxj_b-qF6yKOKBz..."
    }
  }
}
```

#### Step 2.4: Update GitHub Secrets
1. Base64 encoded the new `.clasprc.json`: `base64 -w 0 ~/.clasprc.json`
2. Updated GitHub Secrets:
   - `SIEVE_CLASP_TOKEN_HOME`
   - `SIEVE_CLASP_TOKEN_WORK`

**Result**: Still failed with same access token error

### 3. API Enablement Verification (COMPLETED)

**APIs Enabled in Google Cloud Project**:
- Google Apps Script API: ✅ Enabled
- Google Drive API: ✅ Enabled  
- Gmail API: ✅ Enabled

**Verification Steps**:
1. Navigated to https://console.cloud.google.com/apis/enableflow?apiid=script
2. Confirmed Google Apps Script API was enabled
3. Checked other related APIs

### 4. OAuth Scopes Verification (COMPLETED)

**appsscript.json Configuration**:
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

## GitHub Actions Workflow Modifications Attempted

### 1. Authentication File Location Variations

**Locations Tried**:
- `~/.clasprc.json` (standard location)
- `~/.config/clasp/.clasprc.json` (alternative location)
- `./.clasprc.json` (project directory)

**Workflow Code**:
```yaml
- name: Setup clasp authentication (CORRECT LOCATION)
  run: |
    echo "Setting up clasp authentication in ~/.clasprc.json..."
    echo '${{ secrets.SIEVE_CLASP_TOKEN_HOME }}' | base64 -d > ~/.clasprc.json
    
    # Also try putting it in the global location as backup
    mkdir -p ~/.config/clasp
    cp ~/.clasprc.json ~/.config/clasp/.clasprc.json || true
    
    # And try the project directory as another backup
    cp ~/.clasprc.json ./.clasprc.json || true
```

### 2. Clasp Version Pinning

**Versions Tested**:
- Latest version (2.5.0) - FAILED
- Version 2.4.2 (known stable) - FAILED

**Workflow Code**:
```yaml
- name: Install specific clasp version
  run: |
    echo "Installing specific clasp version to avoid OAuth compatibility issues"
    npm install -g @google/clasp@2.4.2
```

### 3. Enhanced Debugging

**Debug Information Collected**:
- File existence verification
- File size verification  
- Complete file contents display
- JSON validation
- Token structure analysis (both old and new formats)
- OAuth client settings verification
- Clasp version verification
- `clasp whoami` authentication test

**Latest Debug Output**:
```
Clasp version: 2.4.2
Auth file exists: -rw-r--r-- 1 runner docker 642 Aug 4 02:06 /home/runner/.clasprc.json
Project file exists: -rw-r--r-- 1 runner docker 92 Aug 4 02:06 .clasp.json
Clasp status: Not ignored files:
└─ dist/config-embed.js
└─ dist/config/loader.js  
└─ dist/main.js
└─ dist/sieve.js
└─ dist/types/index.js
```

## Current Error Analysis

### Latest Error Details
```
Error retrieving access token: TypeError: Cannot read properties of undefined (reading 'access_token')
=== CLASP PUSH FAILED - DEBUGGING ===
Exit code: 0
Clasp version: 2.4.2
Auth file exists: -rw-r--r-- 1 runner docker 642 Aug 4 02:06 /home/runner/.clasprc.json
Project file exists: -rw-r--r-- 1 runner docker 92 Aug 4 02:06 .clasp.json
```

### Token Structure Verification
The authentication file contains the correct OAuth client credentials structure:
```json
{
  "tokens": {
    "default": {
      "client_id": "972766819723-s97pb1ldo9L41vC9pvgZhtgcOr01t1.apps.googleusercontent.com",
      "client_secret": "GOCSPX-0N5RreTNJGuhnZdOjpD6cR",
      "type": "authorized_user", 
      "refresh_token": "1//06f5GuHh-ZbdUCgYIARAAGAYSNwF-L9IrEtJn...",
      "access_token": "ya29.A0AS3H6NzQuFUcSEOxj_b-qF6yKOKBz..."
    }
  }
}
```

## Research and External References

### 1. Known Issues Found
- **Google OAuth Changes 2024/2025**: Multiple sources indicate Google made significant OAuth authentication changes affecting third-party applications
- **Clasp Compatibility Issues**: Evidence suggests newer clasp versions have compatibility problems with Google's OAuth changes
- **CI/CD Environment Differences**: Some sources indicate clasp behaves differently in CI environments vs local development

### 2. Alternative Solutions Researched
- **Service Account Authentication**: Considered but not applicable for Apps Script personal projects
- **Different OAuth Client Types**: Tried Desktop application type (recommended for clasp)
- **Manual Token Refresh**: Considered implementing custom token refresh logic

## Project Configuration Files

### 1. Google Apps Script Configuration
**File**: `appsscript.json`
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

### 2. Clasp Project Configuration
**File**: `.clasp.json` (generated in workflow)
```json
{
  "scriptId": "${{ secrets.SIEVE_HOME_SCRIPT_ID }}",
  "rootDir": "./dist"
}
```

### 3. GitHub Secrets Configuration
**Required Secrets**:
- `SIEVE_CLASP_TOKEN_HOME`: Base64-encoded `.clasprc.json` content
- `SIEVE_CLASP_TOKEN_WORK`: Base64-encoded `.clasprc.json` content  
- `SIEVE_HOME_SCRIPT_ID`: Google Apps Script project ID for home account
- `SIEVE_WORK_SCRIPT_ID`: Google Apps Script project ID for work account

## Workflow File Current State

### deploy-home.yml (Latest Version)
```yaml
name: Deploy Home Gmail Sieve

on:
  push:
    branches: [main]
    paths:
      - 'src/**'
      - 'configs/home-config.yml'
      - '.github/workflows/deploy-home.yml'
      - 'package.json'
      - 'tsconfig.json'
      - 'appsscript.json'
  workflow_dispatch:

jobs:
  deploy-home:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'

      - name: Install dependencies
        run: npm install

      - name: Build TypeScript
        run: npm run build

      - name: Embed configuration
        run: |
          echo "Embedding configuration..."
          npm install js-yaml
          node -e "
            const yaml = require('js-yaml');
            const fs = require('fs');
            const config = yaml.load(fs.readFileSync('configs/home-config.yml', 'utf8'));
            const jsContent = 'const SIEVE_CONFIG = ' + JSON.stringify(config, null, 2) + ';';
            fs.writeFileSync('dist/config-embed.js', jsContent);
            console.log('Configuration embedded successfully');
          "

      - name: Install specific clasp version
        run: |
          echo "Installing specific clasp version to avoid OAuth compatibility issues"
          npm install -g @google/clasp@2.4.2

      - name: Setup clasp authentication (CORRECT LOCATION)
        run: |
          echo "Setting up clasp authentication in ~/.clasprc.json..."
          echo '${{ secrets.SIEVE_CLASP_TOKEN_HOME }}' | base64 -d > ~/.clasprc.json
          
          # Also try putting it in the global location as backup
          mkdir -p ~/.config/clasp
          cp ~/.clasprc.json ~/.config/clasp/.clasprc.json || true
          
          # And try the project directory as another backup
          cp ~/.clasprc.json ./.clasprc.json || true
          
      - name: Debug clasp authentication setup  
        run: |
          echo "=== Debugging clasp authentication ==="
          echo "Check if ~/.clasprc.json exists:"
          ls -la ~/.clasprc.json || echo "File does not exist"
          echo ""
          echo "File size:"
          wc -c ~/.clasprc.json || echo "Cannot get file size"
          echo ""
          echo "FULL FILE CONTENTS:"
          echo "--- START OF ~/.clasprc.json ---"
          cat ~/.clasprc.json || echo "Cannot read file"
          echo ""
          echo "--- END OF ~/.clasprc.json ---"
          echo ""
          echo "JSON validation:"
          jq . ~/.clasprc.json || echo "JSON validation failed"
          echo ""
          echo "Check NEW token structure (OAuth client):"
          jq '.token.access_token' ~/.clasprc.json || echo "Cannot find .token.access_token"
          echo ""
          echo "Check OLD token structure (global login):"
          jq '.tokens.default.access_token' ~/.clasprc.json || echo "Cannot find .tokens.default.access_token"
          echo ""
          echo "Check oauth2ClientSettings:"
          jq '.oauth2ClientSettings' ~/.clasprc.json || echo "Cannot find oauth2ClientSettings"
          echo ""
          echo "Clasp version:"
          clasp --version || echo "Clasp not found"
          echo ""
          echo "Check all possible clasp auth file locations:"
          ls -la ~/.clasprc.json 2>/dev/null || echo "~/.clasprc.json not found"
          ls -la ~/.config/clasp/.clasprc.json 2>/dev/null || echo "~/.config/clasp/.clasprc.json not found"
          ls -la ./.clasprc.json 2>/dev/null || echo "./.clasprc.json not found"
          echo ""
          echo "Try clasp whoami to test authentication:"
          clasp whoami || echo "clasp whoami failed"

      - name: Create clasp config
        run: |
          echo '{"scriptId":"${{ secrets.SIEVE_HOME_SCRIPT_ID }}","rootDir":"./dist"}' > .clasp.json

      - name: Test clasp authentication first
        run: |
          echo "=== TESTING CLASP AUTH BEFORE PUSH ==="
          echo "Clasp status:"
          clasp status || echo "STATUS FAILED"
          echo ""
          echo "Current directory contents:"
          ls -la
          echo ""
          echo ".clasp.json contents:"
          cat .clasp.json || echo "NO .clasp.json"
          echo ""
          
      - name: Push to Google Apps Script
        run: |
          echo "Pushing to Home Apps Script..."
          echo "=== FULL CLASP PUSH OUTPUT ==="
          clasp push --force 2>&1 || {
            echo "=== CLASP PUSH FAILED - DEBUGGING ==="
            echo "Exit code: $?"
            echo "Clasp version: $(clasp --version)"
            echo "Auth file exists: $(ls -la ~/.clasprc.json)"
            echo "Project file exists: $(ls -la .clasp.json)"
            echo "Clasp status: $(clasp status 2>&1)"
            exit 1
          }

      - name: Deploy new version
        run: |
          echo "Deploying new version..."
          clasp deploy --description "Deploy $(date '+%Y-%m-%d %H:%M:%S')"

      - name: Test deployment
        run: |
          echo "Testing deployment..."
          clasp run --function testDeployment
        continue-on-error: true

      - name: Notify success
        if: success()
        run: |
          echo "✅ Home Sieve deployment successful!"
          echo "📧 Account: scott.a.idler@gmail.com"
          echo "🆔 Script ID: ${{ secrets.SIEVE_HOME_SCRIPT_ID }}"
```

## Unresolved Questions

1. **Why does the same OAuth client credentials work locally but fail in GitHub Actions?**
2. **Is there a difference in how clasp handles authentication in CI environments vs local development?**
3. **Are there additional Google Cloud Platform settings or permissions required for CI/CD authentication?**
4. **Could the issue be related to the GitHub Actions runner environment or network restrictions?**
5. **Is there a different authentication method specifically recommended for CI/CD deployments to Google Apps Script?**

## Next Steps to Try

1. **Test with Service Account**: Although typically not used for personal Apps Script projects, investigate if service account authentication works better in CI environments
2. **Manual Token Management**: Implement custom token refresh logic instead of relying on clasp's built-in authentication
3. **Alternative Deployment Method**: Research other methods to deploy to Google Apps Script from CI/CD (e.g., direct API calls)
4. **Local vs CI Environment Comparison**: Set up detailed logging to compare exactly what differs between local successful authentication and CI failure
5. **Google Support**: Consider reaching out to Google Apps Script support for CI/CD authentication guidance

## Impact

This authentication issue is blocking the entire CI/CD pipeline for the Sieve Gmail automation system. Manual deployment is currently required, which defeats the purpose of the automated deployment system.

## Contact Information

- **Primary Developer**: Scott Idler
- **Email**: scott.a.idler@gmail.com  
- **Repository**: https://github.com/scottidler/sieve
- **Issue Date**: August 2025 