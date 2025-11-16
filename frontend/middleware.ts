import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
    const token = request.cookies.get("token")?.value;
    const { pathname } = request.nextUrl;

    if (pathname.startsWith("/chat")) {
        if (!token) {
            return NextResponse.redirect(new URL("/login", request.url));
        }
    }

    if (pathname === "/login" || pathname === "/register") {
        if (token) {
            return NextResponse.redirect(new URL("/chat", request.url));
        }
    }

    return NextResponse.next();
}

export const config = {
    matcher: ["/chat/:path*", "/login", "/register"],
};
