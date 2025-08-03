import { RuntimeConfig, SieveExecutionResult } from './types';
import { ConfigLoader } from './config/loader';

/**
 * Main Sieve class for Gmail automation
 * Handles thread-aware email filtering and processing
 */
export class Sieve {
  private config: RuntimeConfig;
  private startTime: Date;

  constructor() {
    this.startTime = new Date();
    this.config = ConfigLoader.load();
    ConfigLoader.validateConfig(this.config);
  }

  /**
   * Main execution method - runs the complete sieve process
   */
  async run(): Promise<SieveExecutionResult> {
    const errors: string[] = [];

    try {
      console.log(`🔍 Starting Sieve for account: ${this.config.account.name}`);
      console.log(`📧 Email: ${this.config.account.email}`);
      console.log(`⚙️  Threading enabled: ${this.config.threading.enabled}`);

      // Check if we should skip execution (quiet hours)
      if (this.shouldSkipExecution()) {
        console.log('⏸️  Skipping execution due to quiet hours or other conditions');
        return this.createResult([], [], errors);
      }

      // For initial deployment testing, just fetch basic Gmail info
      const gmailInfo = await this.getGmailInfo();
      console.log(`📊 Gmail info: ${JSON.stringify(gmailInfo)}`);

      // TODO: Implement actual filtering logic
      console.log('✅ Sieve execution completed successfully');

      return this.createResult([], [], errors);

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error('❌ Sieve execution failed:', errorMessage);
      errors.push(errorMessage);

      // Send error notification if configured
      await this.sendErrorNotification(error);

      return this.createResult([], [], errors);
    }
  }

  /**
   * Get basic Gmail information for deployment testing
   */
  private async getGmailInfo(): Promise<{ labelCount: number; inboxCount: number }> {
    try {
      // Get all labels
      const labelsResponse = Gmail.Users?.Labels?.list('me');
      const labelCount = labelsResponse?.labels?.length || 0;

      // Get inbox thread count (limited to avoid quota issues)
      const threadsResponse = Gmail.Users?.Threads?.list('me', {
        q: 'in:inbox',
        maxResults: 10
      });
      const inboxCount = threadsResponse?.threads?.length || 0;

      return { labelCount, inboxCount };
    } catch (error) {
      console.warn('Failed to get Gmail info:', error);
      return { labelCount: 0, inboxCount: 0 };
    }
  }

  /**
   * Check if execution should be skipped based on configuration
   */
  private shouldSkipExecution(): boolean {
    const quietHours = this.config.quiet_hours;

    if (!quietHours?.enabled) {
      return false;
    }

    try {
      const now = new Date();
      const currentHour = now.getHours();
      const startHour = parseInt(quietHours.start.split(':')[0] || '9');
      const endHour = parseInt(quietHours.end.split(':')[0] || '17');

      // Simple hour-based check (ignoring timezone for now)
      return currentHour >= startHour && currentHour < endHour;
    } catch (error) {
      console.warn('Failed to check quiet hours:', error);
      return false;
    }
  }

  /**
   * Send error notification via email
   */
  private async sendErrorNotification(error: unknown): Promise<void> {
    try {
      const errorMessage = error instanceof Error ? error.message : String(error);
      const stackTrace = error instanceof Error ? error.stack : 'No stack trace available';

      const subject = `🚨 Sieve Error - ${this.config.account.name}`;
      const body = `
Sieve automation error occurred:

Account: ${this.config.account.name} (${this.config.account.email})
Time: ${new Date().toISOString()}
Error: ${errorMessage}

Stack trace:
${stackTrace}

This is an automated notification from the Sieve Gmail automation system.
      `.trim();

      // Send to the account owner
      MailApp.sendEmail({
        to: this.config.account.email,
        subject: subject,
        body: body
      });

      console.log('📧 Error notification sent');
    } catch (notificationError) {
      console.error('Failed to send error notification:', notificationError);
    }
  }

  /**
   * Create execution result object
   */
  private createResult(
    messageResults: any[],
    stateResults: any[],
    errors: string[]
  ): SieveExecutionResult {
    const duration = new Date().getTime() - this.startTime.getTime();

    return {
      account: this.config.account.name,
      threadsProcessed: 0, // Will be updated when we implement actual processing
      messageFiltersApplied: messageResults,
      stateFiltersApplied: stateResults,
      errors,
      duration
    };
  }
}