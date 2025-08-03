# Sieve - Gmail Automation System

A TypeScript-based Gmail automation system using Google Apps Script with intelligent filtering, thread-aware processing, and multi-account support.

## Features

- **Thread-aware processing**: Proper Gmail thread handling using native APIs
- **Multi-account support**: Separate instances for home and work accounts
- **Intelligent filtering**: Message-based and state-based (age-off) filtering rules
- **Superior detection**: Special handling for company hierarchy emails
- **GitHub deployment**: Automated CI/CD pipeline with dual account deployment
- **Configuration-driven**: YAML-based rule definitions

## Quick Start

### 1. Install Dependencies

```bash
npm install
```

### 2. Setup Google Apps Script Projects

1. Go to [Google Apps Script](https://script.google.com)
2. Create two new projects:
   - "Sieve - Home Gmail"
   - "Sieve - Work Gmail"
3. Note the Script IDs from the URLs

### 3. Setup Clasp Authentication

```bash
# Install clasp globally
npm install -g @google/clasp

# Login to Google account
clasp login

# This creates ~/.clasprc.json with your authentication
```

### 4. Configure GitHub Secrets

Add these secrets to your GitHub repository:

```
SIEVE_CLASP_TOKEN_HOME=<contents of ~/.clasprc.json>
SIEVE_CLASP_TOKEN_WORK=<contents of ~/.clasprc.json>
SIEVE_HOME_SCRIPT_ID=<your home script ID>
SIEVE_WORK_SCRIPT_ID=<your work script ID>
```

### 5. Update Configuration Files

Edit the configuration files:
- `configs/home-config.yml` - Home Gmail rules
- `configs/work-config.yml` - Work Gmail rules

Replace the placeholder script IDs and email addresses with your actual values.

### 6. Deploy

Push to main branch - GitHub Actions will automatically deploy to both accounts:

```bash
git add .
git commit -m "Initial sieve setup"
git push origin main
```

## Development

### Local Development

```bash
# Build TypeScript
npm run build

# Watch for changes
npm run watch

# Lint code
npm run lint

# Format code
npm run format
```

### Manual Deployment

```bash
# Deploy to home account
npm run deploy:home

# Deploy to work account
npm run deploy:work
```

### Testing

```bash
# Run tests
npm test

# Test deployment (run this in Apps Script console)
testDeployment()

# Manual sieve run (run this in Apps Script console)
runSieve()
```

## Configuration

### Home Account (`configs/home-config.yml`)

- Family/friend priority detection
- Newsletter management
- Relaxed age-off rules (7d read, 21d unread)
- 24h recent activity threshold

### Work Account (`configs/work-config.yml`)

- Company superior detection
- Direct message prioritization
- Aggressive age-off rules (5d read, 14d unread)
- Quiet hours during business hours
- Emergency keyword bypass

## Architecture

- **TypeScript**: Type-safe development with Google Apps Script types
- **Dual Deployment**: Separate GitHub workflows for each account
- **YAML Configuration**: Human-readable rule definitions
- **Thread-Aware**: Processes entire email threads consistently
- **Error Handling**: Automatic error notifications via email

## File Structure

```
sieve/
├── src/
│   ├── main.ts              # Apps Script entry point
│   ├── sieve.ts             # Main Sieve class
│   ├── config/
│   │   └── loader.ts        # Configuration loading
│   └── types/
│       └── index.ts         # TypeScript definitions
├── configs/
│   ├── home-config.yml      # Home Gmail rules
│   └── work-config.yml      # Work Gmail rules
├── .github/workflows/
│   ├── deploy-home.yml      # Home deployment
│   └── deploy-work.yml      # Work deployment
└── docs/
    └── architecture.md      # Detailed architecture
```

## Troubleshooting

### Deployment Issues

1. **Authentication Failed**: Ensure clasp tokens are valid in GitHub secrets
2. **Script ID Not Found**: Verify script IDs are correct in configs and secrets
3. **Permission Denied**: Check that Gmail API is enabled in Apps Script projects

### Runtime Issues

1. **Config Not Found**: Check that CONFIG_TYPE property is set correctly
2. **Gmail API Errors**: Verify OAuth scopes in `appsscript.json`
3. **Quota Exceeded**: Reduce batch sizes or add delays between operations

### Getting Help

- Check the [Architecture Documentation](docs/architecture.md)
- Review GitHub Actions logs for deployment issues
- Check Google Apps Script execution logs for runtime issues

## License

MIT License - see LICENSE file for details.
# Test trigger
