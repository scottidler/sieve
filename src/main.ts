import { Sieve } from './sieve';

/**
 * Main entry point for Google Apps Script
 * This function will be called by Apps Script triggers
 */
function main(): void {
  const sieve = new Sieve();
  sieve.run().then(result => {
    console.log('Sieve execution completed:', JSON.stringify(result, null, 2));
  }).catch(error => {
    console.error('Sieve execution failed:', error);
  });
}

/**
 * Manual trigger function for testing
 */
function runSieve(): void {
  main();
}

/**
 * Test function to verify deployment
 */
function testDeployment(): void {
  console.log('🚀 Sieve deployment test successful!');
  console.log('📅 Timestamp:', new Date().toISOString());

  try {
    const sieve = new Sieve();
    console.log('✅ Sieve instance created successfully');
  } catch (error) {
    console.error('❌ Failed to create Sieve instance:', error);
  }
}

// Make functions available globally for Apps Script
declare const global: any;
global.main = main;
global.runSieve = runSieve;
global.testDeployment = testDeployment;