# CLASP Authentication Fix - The Real Solution

## Problem
`clasp` commands fail with:
```
User has not enabled the Apps Script API. Enable it by visiting https://script.google.com/home/usersettings then retry.
```

Even after enabling the toggle at script.google.com/home/usersettings, commands like `clasp create`, `clasp push`, and `clasp pull` continue to fail.

## Root Cause
**There are TWO different Apps Script API settings that both need to be enabled:**

1. **User-level setting**: `script.google.com/home/usersettings` (controls manual script execution)
2. **Project-level API**: Google Cloud Console API Library (controls programmatic access via clasp)

**The script.google.com toggle is NOT sufficient for clasp to work.**

## Solution

### Step 1: Enable User-Level Apps Script API
1. Go to https://script.google.com/home/usersettings
2. Make sure you're signed in with the correct Google account
3. Toggle "Google Apps Script API" to **ON**

### Step 2: Enable Project-Level Apps Script API (THE CRITICAL STEP)
1. Go to https://console.cloud.google.com/apis/library/script.googleapis.com
2. Make sure you're signed in with the same Google account
3. Select your Google Cloud project (or create one if needed)
4. Click **"ENABLE"** on the Apps Script API
5. If prompted, enable billing for your project

### Step 3: Re-authenticate clasp
```bash
clasp logout
clasp login
```
Complete the OAuth flow in your browser.

### Step 4: Test the fix
```bash
# Test with a simple create command
cd /tmp
mkdir clasp-test && cd clasp-test
clasp create "Test Project" --type standalone
```

If this works without errors, clasp is now properly configured.

## Verification
After following these steps, you should see:
- `clasp create` works without API errors
- `clasp push` works without 403 Forbidden errors  
- `clasp pull` retrieves files successfully

## Common Mistakes
- ❌ Only enabling the script.google.com/home/usersettings toggle
- ❌ Not enabling billing in Google Cloud Console (required for API access)
- ❌ Using different Google accounts between the two settings
- ❌ Not re-authenticating clasp after enabling the APIs

## Why This Happens
Google has two separate systems:
- **Apps Script Editor**: Uses the user-level toggle for manual script execution
- **Apps Script API**: Uses the project-level API for programmatic access (clasp, REST API, etc.)

Both must be enabled for clasp to function properly.

## Project-Specific Setup
Once clasp is working globally, return to your project:

```bash
cd /path/to/your/project
npm run build
echo y | clasp push
```

Your TypeScript files should now successfully push to Apps Script. 