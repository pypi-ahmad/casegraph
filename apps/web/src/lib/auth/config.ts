/**
 * Auth.js (next-auth v5) configuration for the CaseGraph platform.
 *
 * Uses a credentials provider backed by env-defined local users.
 * Session strategy is JWT (no database required).
 */

import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";

import { authenticateLocal } from "@/lib/auth/local-users";

import type { UserRole } from "@casegraph/agent-sdk";

declare module "next-auth" {
  interface User {
    role?: UserRole;
  }
  interface Session {
    user: {
      id: string;
      name: string;
      email: string;
      role: UserRole;
    };
  }
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  pages: {
    signIn: "/sign-in",
  },

  session: {
    strategy: "jwt",
    maxAge: 24 * 60 * 60, // 24 hours
  },

  providers: [
    Credentials({
      name: "Local credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const email = credentials?.email;
        const password = credentials?.password;
        if (typeof email !== "string" || typeof password !== "string") {
          return null;
        }

        const user = await authenticateLocal(email, password);
        if (!user) return null;

        return {
          id: user.id,
          name: user.name,
          email: user.email,
          role: user.role,
        };
      },
    }),
  ],

  callbacks: {
    jwt({ token, user }) {
      if (user) {
        const authToken = token as typeof token & { id?: string; role?: UserRole };
        authToken.id = user.id ?? undefined;
        authToken.role = user.role ?? "member";
      }
      return token;
    },
    session({ session, token }) {
      if (session.user) {
        const authToken = token as typeof token & { id?: string; role?: UserRole };
        session.user.id = authToken.id ?? "";
        session.user.role = authToken.role ?? "member";
      }
      return session;
    },
  },
});
