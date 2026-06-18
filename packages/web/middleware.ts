import { NextRequest, NextResponse } from 'next/server';
import { jwtDecode } from 'jwt-decode';

// Define which routes require authentication
const protectedRoutes = [
  '/dashboard',
  '/projects',
  '/profile',
  '/settings',
];

// Define public routes that should redirect to dashboard if authenticated
const publicRoutes = [
  '/login',
  '/register',
  '/forgot-password',
];

// Routes that are always accessible
const alwaysAccessible = [
  '/',
  '/api',
  '/_next',
  '/favicon.ico',
  '/robots.txt',
];

function isTokenValid(token: string): boolean {
  try {
    const decoded = jwtDecode<{ exp: number }>(token);
    const now = Math.floor(Date.now() / 1000);
    return decoded.exp > now;
  } catch {
    return false;
  }
}

function isProtectedRoute(pathname: string): boolean {
  return protectedRoutes.some(route => pathname.startsWith(route));
}

function isPublicRoute(pathname: string): boolean {
  return publicRoutes.some(route => pathname.startsWith(route));
}

function isAlwaysAccessible(pathname: string): boolean {
  return alwaysAccessible.some(route => pathname.startsWith(route));
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Skip middleware for always accessible routes
  if (isAlwaysAccessible(pathname)) {
    return NextResponse.next();
  }

  // Get auth token from cookies
  const token = request.cookies.get('auth_token')?.value;
  const isAuthenticated = token && isTokenValid(token);

  // Protected routes - require authentication
  if (isProtectedRoute(pathname)) {
    if (!isAuthenticated) {
      const returnUrl = encodeURIComponent(pathname + request.nextUrl.search);
      const loginUrl = new URL('/login', request.url);
      loginUrl.searchParams.set('returnUrl', returnUrl);
      
      return NextResponse.redirect(loginUrl);
    }
  }

  // Public routes - redirect to dashboard if authenticated
  if (isPublicRoute(pathname)) {
    if (isAuthenticated) {
      return NextResponse.redirect(new URL('/dashboard', request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!api|_next/static|_next/image|favicon.ico).*)',
  ],
};