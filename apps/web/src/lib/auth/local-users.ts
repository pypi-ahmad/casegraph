/**
 * Local user bootstrap — reads credentials from environment variables.
 *
 * Format (one-indexed, add more by bumping the index):
 *   AUTH_USER_1_EMAIL=admin@local.dev
 *   AUTH_USER_1_PASSWORD_HASH=<bcrypt hash>
 *   AUTH_USER_1_NAME=Admin
 *   AUTH_USER_1_ROLE=admin
 *
 * Generate a hash:  node -e "import('bcryptjs').then(b=>b.hash('changeme',10).then(console.log))"
 *
 * If no users are configured the credentials provider will reject all logins.
 */

import { compare } from "bcryptjs";

export interface LocalUser {
  id: string;
  email: string;
  name: string;
  role: "admin" | "member";
  passwordHash: string;
}

/** Scan env vars for AUTH_USER_<n>_* entries. */
function loadLocalUsers(): LocalUser[] {
  const users: LocalUser[] = [];
  for (let i = 1; i <= 10; i++) {
    const email = process.env[`AUTH_USER_${i}_EMAIL`];
    const hash = process.env[`AUTH_USER_${i}_PASSWORD_HASH`];
    const name = process.env[`AUTH_USER_${i}_NAME`] ?? `User ${i}`;
    const role = (process.env[`AUTH_USER_${i}_ROLE`] ?? "admin") as "admin" | "member";
    if (email && hash) {
      users.push({ id: `local-${i}`, email, name, role, passwordHash: hash });
    }
  }
  return users;
}

let _cache: LocalUser[] | null = null;

function getLocalUsers(): LocalUser[] {
  if (_cache === null) {
    _cache = loadLocalUsers();
  }
  return _cache;
}

/** Authenticate against env-defined local users. Returns the user or null. */
export async function authenticateLocal(
  email: string,
  password: string,
): Promise<Omit<LocalUser, "passwordHash"> | null> {
  const users = getLocalUsers();
  const match = users.find((u) => u.email.toLowerCase() === email.toLowerCase());
  if (!match) return null;

  const ok = await compare(password, match.passwordHash);
  if (!ok) return null;

  const { passwordHash: _, ...safe } = match;
  return safe;
}
