/**
 * Shared authentication contracts for the CaseGraph platform.
 *
 * These types define the minimal session/user shape used across
 * the frontend and (in the future) the backend API.  They are
 * intentionally small and extensible — roles, org membership, and
 * permissions will be layered on later.
 */

/** Unique user identifier. */
export type UserId = string;

/** Placeholder for future RBAC. */
export type UserRole = "admin" | "member";

/** Minimal user profile carried in the session. */
export interface SessionUser {
  id: UserId;
  name: string;
  email: string;
  role: UserRole;
}

/** Auth status metadata returned by capabilities / info endpoints. */
export interface AuthStatus {
  authenticated: boolean;
  user: SessionUser | null;
}
