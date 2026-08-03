const sqlite3 = require('better-sqlite3');
const fs = require('fs');
const path = require('path');

const dbPath = path.join(process.cwd(), '.boukensha', 'events.db');
console.log(`Checking database: ${dbPath}`);

if (!fs.existsSync(dbPath)) {
  console.error('Database not found');
  process.exit(1);
}

try {
  const db = new sqlite3(dbPath);

  // Check event counts by phase
  console.log('\nEvents by phase:');
  const phases = db.prepare(`
    SELECT phase, COUNT(*) as count, COUNT(CASE WHEN tools_sent IS NOT NULL THEN 1 END) as with_tools_sent
    FROM events
    WHERE session_id = '20260803T220918Z-7975a5d3'
    GROUP BY phase
  `).all();

  for (const row of phases) {
    console.log(`  ${row.phase.padEnd(15)} count=${String(row.count).padStart(4)}  with_tools_sent=${String(row.with_tools_sent).padStart(4)}`);
  }

  // Check sample prompt event
  console.log('\nSample prompt event:');
  const prompt = db.prepare(`
    SELECT details FROM events
    WHERE session_id = '20260803T220918Z-7975a5d3' AND phase = 'prompt'
    LIMIT 1
  `).get();

  if (prompt) {
    const event = JSON.parse(prompt.details);
    console.log(`  tool_count: ${event.tool_count}`);
  }

  // Check sample response event
  console.log('\nSample response event:');
  const response = db.prepare(`
    SELECT tools_sent, details FROM events
    WHERE session_id = '20260803T220918Z-7975a5d3' AND phase = 'response'
    LIMIT 1
  `).get();

  if (response) {
    const event = JSON.parse(response.details);
    console.log(`  tools_sent (column): ${response.tools_sent}`);
    console.log(`  tools_sent (json):   ${event.tools_sent}`);
  }

  db.close();
} catch (err) {
  console.error('Error:', err.message);
  process.exit(1);
}
