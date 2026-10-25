import { initDb } from './repos/freellmapi/server/dist/db/index.js';
import { initEncryptionKey, encrypt } from './repos/freellmapi/server/dist/lib/crypto.js';

const db = initDb();
initEncryptionKey(db);

const keylessPlatforms = [
  { platform: 'kilo', label: 'Kilo Anonymous (Free)' },
  { platform: 'ovh', label: 'OVH AI Endpoints (Free)' },
  { platform: 'aihorde', label: 'AI Horde (Free)' }
];

for (const p of keylessPlatforms) {
  const existing = db.prepare('SELECT id FROM api_keys WHERE platform = ?').get(p.platform);
  if (!existing) {
    const enc = encrypt('no-key');
    db.prepare(`
      INSERT INTO api_keys (platform, label, encrypted_key, iv, auth_tag, status, enabled)
      VALUES (?, ?, ?, ?, ?, 'healthy', 1)
    `).run(p.platform, p.label, enc.encrypted, enc.iv, enc.authTag);
    console.log(`[+] Added keyless provider: ${p.platform}`);
  } else {
    db.prepare("UPDATE api_keys SET status = 'healthy', enabled = 1 WHERE platform = ?").run(p.platform);
    console.log(`[✓] Updated keyless provider: ${p.platform}`);
  }
}

console.log('All keyless providers configured successfully in database.');
