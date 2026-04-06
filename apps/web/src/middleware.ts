import { auth } from "@/lib/auth/config";
import { NextResponse } from "next/server";

/**
 * Middleware that protects internal pages behind authentication.
 *
 * Public routes: /, /sign-in, /api/auth/*
 * Everything else requires an active session.
 */

const PUBLIC_PATHS = new Set(["/", "/sign-in"]);

export default auth((req) => {
  const { pathname } = req.nextUrl;

  // Always allow auth API routes
  if (pathname.startsWith("/api/auth")) {
    return NextResponse.next();
  }

  // Allow explicitly public pages
  if (PUBLIC_PATHS.has(pathname)) {
    return NextResponse.next();
  }

  // Redirect unauthenticated users to sign-in
  if (!req.auth?.user) {
    const signIn = new URL("/sign-in", req.url);
    signIn.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(signIn);
  }

  return NextResponse.next();
});

export const config = {
  matcher: [
    /*
     * Run middleware on all routes except Next.js internals and static assets.
     */
    "/((?!_next/static|_next/image|favicon\\.ico).*)",
  ],
};
