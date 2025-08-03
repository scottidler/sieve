// Core configuration types
export interface SieveConfig {
  account: AccountConfig;
  'message-filters': MessageFilter[];
  'state-filters': StateFilter[];
  threading: ThreadingConfig;
  company?: CompanyConfig;
  'quiet-hours'?: QuietHoursConfig;
  'emergency-keywords'?: string[];
}

export interface AccountConfig {
  name: string;
  email: string;
  'script-id': string;
}

export interface MessageFilter {
  name: string;
  to?: string[];
  cc?: string[];
  from?: string[] | FromConfig;
  labels?: string[];
  actions: FilterAction[];
}

export interface FromConfig {
  patterns: string[];
  'superiors-only'?: boolean;
}

export interface StateFilter {
  name: string;
  labels?: string[];
  'exclude-labels'?: string[];
  ttl: TTLConfig | 'keep';
  actions: StateAction[];
}

export interface TTLConfig {
  read: string;
  unread: string;
}

export interface FilterAction {
  type: 'star' | 'flag' | 'move';
  label?: string;
  destination?: string;
}

export interface StateAction {
  type: 'move' | 'delete';
  destination?: string;
}

export interface ThreadingConfig {
  enabled: boolean;
  'require-all-messages-aged': boolean;
  'recent-activity-threshold': string;
}

export interface CompanyConfig {
  domain: string;
  superiors: string[];
}



export interface QuietHoursConfig {
  enabled: boolean;
  start: string;
  end: string;
  timezone: string;
}

// Gmail API types (simplified for our needs)
export interface GmailThread {
  id: string;
  messages: GmailMessage[];
  snippet: string;
  historyId: string;
}

export interface GmailMessage {
  id: string;
  threadId: string;
  labelIds: string[];
  payload: MessagePayload;
  internalDate: string;
}

export interface MessagePayload {
  headers: MessageHeader[];
  body?: MessageBody;
}

export interface MessageHeader {
  name: string;
  value: string;
}

export interface MessageBody {
  data?: string;
  size: number;
}

// Runtime configuration (YAML keys converted to JS property names)
export interface RuntimeConfig {
  account: {
    name: string;
    email: string;
    script_id: string;
  };
  message_filters: Array<{
    name: string;
    to?: string[];
    cc?: string[];
    from?: string[] | {
      patterns: string[];
      superiors_only?: boolean;
    };
    labels?: string[];
    actions: FilterAction[];
  }>;
  state_filters: Array<{
    name: string;
    labels?: string[];
    exclude_labels?: string[];
    ttl: TTLConfig | 'keep';
    actions: StateAction[];
  }>;
  threading: {
    enabled: boolean;
    require_all_messages_aged: boolean;
    recent_activity_threshold: string;
  };
  company?: {
    domain: string;
    superiors: string[];
  };
  quiet_hours?: {
    enabled: boolean;
    start: string;
    end: string;
    timezone: string;
  };
  emergency_keywords?: string[];
}

// Processing results
export interface FilterResult {
  filter: string;
  thread: string;
  matchedMessages?: number;
  processedMessages?: number;
  action?: string;
}

export interface SieveExecutionResult {
  account: string;
  threadsProcessed: number;
  messageFiltersApplied: FilterResult[];
  stateFiltersApplied: FilterResult[];
  errors: string[];
  duration: number;
}