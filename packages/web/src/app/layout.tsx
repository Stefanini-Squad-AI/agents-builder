import type { Metadata } from "next"
import "./globals.css"

import { ThemeProvider } from "@/components/theme-provider"
import { ThemeToggle } from "@/components/theme-toggle"
import { QueryProvider } from "@/components/providers/query-provider"
import { AuthProvider } from "@/components/providers/auth-provider"
import { HeaderAuth } from "@/components/auth/header-auth"
import { MainNav } from "@/components/navigation/main-nav"
import { MobileNav } from "@/components/navigation/mobile-nav"
import { NavigationProgress } from "@/components/navigation/navigation-progress"
import { WorkerStatusIndicator } from "@/components/navigation/worker-status-indicator"
import { Toaster } from "@/components/ui/sonner"

export const metadata: Metadata = {
  title: "Agents Workshop",
  description: "AI-powered tool for generating programming skills and Jira workflows",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <QueryProvider>
            <AuthProvider>
              <NavigationProgress />
              <div className="relative flex min-h-screen flex-col">
                <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                  <div className="container flex h-14 items-center justify-between">
                    <div className="flex items-center space-x-6">
                      <div className="flex items-center space-x-2">
                        <MobileNav />
                        <a href="/" className="text-lg font-semibold hover:opacity-80 transition-opacity">
                          Agents Workshop
                        </a>
                      </div>
                      <div className="hidden md:flex">
                        <MainNav />
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <WorkerStatusIndicator />
                      <HeaderAuth />
                      <ThemeToggle />
                    </div>
                  </div>
                </header>
                <main className="flex-1">{children}</main>
                <footer className="border-t py-6 md:py-0">
                  <div className="container flex flex-col items-center justify-center gap-4 md:h-14 md:flex-row">
                  </div>
                </footer>
              </div>
              <Toaster />
            </AuthProvider>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}