import { SieveConfig, RuntimeConfig } from '../types';

// This will be injected during the build process by GitHub Actions
declare const SIEVE_CONFIG: SieveConfig | undefined;

export class ConfigLoader {
  /**
   * Load configuration - completely agnostic to account type
   * The config itself determines what account it's for
   */
  static load(): RuntimeConfig {
    const rawConfig = this.loadRawConfig();
    return this.convertToRuntimeConfig(rawConfig);
  }

  /**
   * Load the raw configuration
   * Config is embedded during the build process
   */
  private static loadRawConfig(): SieveConfig {
    if (typeof SIEVE_CONFIG !== 'undefined') {
      return SIEVE_CONFIG;
    }
    throw new Error('SIEVE_CONFIG not found - was it embedded during build?');
  }

  /**
   * Convert YAML-style config (with hyphens) to JavaScript runtime config (with underscores)
   * This handles the transformation described in the architecture doc
   */
  private static convertToRuntimeConfig(config: SieveConfig): RuntimeConfig {
    return {
      account: {
        name: config.account.name,
        email: config.account.email,
        script_id: config.account['script-id']
      },
      message_filters: config['message-filters'].map(filter => ({
        name: filter.name,
        ...(filter.to && { to: filter.to }),
        ...(filter.cc && { cc: filter.cc }),
        ...(filter.from && {
          from: Array.isArray(filter.from)
            ? filter.from
            : {
                patterns: filter.from.patterns,
                ...(filter.from['superiors-only'] !== undefined && { superiors_only: filter.from['superiors-only'] })
              }
        }),
        ...(filter.labels && { labels: filter.labels }),
        actions: filter.actions
      })),
      state_filters: config['state-filters'].map(filter => ({
        name: filter.name,
        ...(filter.labels && { labels: filter.labels }),
        ...(filter['exclude-labels'] && { exclude_labels: filter['exclude-labels'] }),
        ttl: filter.ttl,
        actions: filter.actions
      })),
      threading: {
        enabled: config.threading.enabled,
        require_all_messages_aged: config.threading['require-all-messages-aged'],
        recent_activity_threshold: config.threading['recent-activity-threshold']
      },
      ...(config.company && {
        company: {
          domain: config.company.domain,
          superiors: config.company.superiors
        }
      }),
            ...(config['quiet-hours'] && { 
        quiet_hours: {
          enabled: config['quiet-hours'].enabled,
          start: config['quiet-hours'].start,
          end: config['quiet-hours'].end,
          timezone: config['quiet-hours'].timezone
        }
      }),
      ...(config['emergency-keywords'] && { 
        emergency_keywords: config['emergency-keywords'] 
      })
    };
  }

  /**
   * Validate that the loaded configuration is complete and valid
   */
  static validateConfig(config: RuntimeConfig): void {
    if (!config.account?.name) {
      throw new Error('Account name is required');
    }

    if (!config.account?.email) {
      throw new Error('Account email is required');
    }

    if (!config.account?.script_id) {
      throw new Error('Account script-id is required');
    }

    // Validate message filters
    for (const filter of config.message_filters) {
      if (!filter.name) {
        throw new Error('Message filter name is required');
      }
      if (!filter.actions || filter.actions.length === 0) {
        throw new Error(`Message filter '${filter.name}' must have at least one action`);
      }
    }

    // Validate state filters
    for (const filter of config.state_filters) {
      if (!filter.name) {
        throw new Error('State filter name is required');
      }
      if (!filter.ttl) {
        throw new Error(`State filter '${filter.name}' must have TTL configuration`);
      }
      if (!filter.actions || filter.actions.length === 0) {
        throw new Error(`State filter '${filter.name}' must have at least one action`);
      }
    }

    console.log(`Configuration validated successfully for account: ${config.account.name}`);
  }
}