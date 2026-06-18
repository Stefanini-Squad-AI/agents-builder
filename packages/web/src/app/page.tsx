'use client'

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { ApiStatus } from "@/components/api-status"
import { ProjectsDemo } from "@/components/projects-demo"
import { useAuth } from "@/lib/auth/context"

export default function Home() {
  const { isAuthenticated, isInitialized } = useAuth()
  const router = useRouter()

  // Redirect authenticated users to dashboard
  useEffect(() => {
    if (isInitialized && isAuthenticated) {
      router.push('/dashboard')
    }
  }, [isAuthenticated, isInitialized, router])
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-6">
        <h1 className="text-4xl font-bold tracking-tight">
          Welcome to Agents Workshop
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl">
          An AI-powered tool for generating programming skills and Jira card workflows.
          Transform your project objectives into structured, actionable deliverables.
        </p>
        <div className="flex items-center justify-center">
          <ApiStatus />
        </div>
        <div className="flex gap-4">
          {isInitialized && (
            isAuthenticated ? (
              <Link href="/dashboard">
                <Button size="lg">
                  Go to Dashboard
                </Button>
              </Link>
            ) : (
              <Link href="/login">
                <Button size="lg">
                  Get Started
                </Button>
              </Link>
            )
          )}
          <Button variant="outline" size="lg">
            Learn More
          </Button>
        </div>
      </div>

      <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 bg-primary rounded-lg mx-auto flex items-center justify-center">
            <span className="text-primary-foreground font-bold">1</span>
          </div>
          <h3 className="text-lg font-semibold">Define Objectives</h3>
          <p className="text-muted-foreground">
            Describe your project goals and technical requirements
          </p>
        </div>
        
        <div className="text-center space-y-4">
          <div className="w-12 h-12 bg-primary rounded-lg mx-auto flex items-center justify-center">
            <span className="text-primary-foreground font-bold">2</span>
          </div>
          <h3 className="text-lg font-semibold">Generate Skills</h3>
          <p className="text-muted-foreground">
            AI creates reusable capabilities and expertise templates
          </p>
        </div>
        
        <div className="text-center space-y-4">
          <div className="w-12 h-12 bg-primary rounded-lg mx-auto flex items-center justify-center">
            <span className="text-primary-foreground font-bold">3</span>
          </div>
          <h3 className="text-lg font-semibold">Build Workflows</h3>
          <p className="text-muted-foreground">
            Export structured Jira cards and project blueprints
          </p>
        </div>
      </div>

      <div className="mt-16 max-w-2xl mx-auto">
        <h2 className="text-2xl font-semibold text-center mb-8">API Integration Demo</h2>
        <div className="grid gap-6">
          <ProjectsDemo />
        </div>
        <p className="text-center text-sm text-muted-foreground mt-4">
          The API client is ready to connect to your FastAPI backend at {process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}
        </p>
      </div>
    </div>
  )
}