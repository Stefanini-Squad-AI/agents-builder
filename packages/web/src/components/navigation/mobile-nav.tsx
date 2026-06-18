'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Menu } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { 
  Home,
  FolderOpen, 
  Lightbulb, 
  Settings,
  FileText,
  Zap
} from 'lucide-react'

// Global nav items
const globalNavItems = [
  {
    title: 'Dashboard',
    href: '/dashboard',
    icon: Home,
    description: 'Overview and quick stats'
  },
  {
    title: 'Projects',
    href: '/projects',
    icon: FolderOpen,
    description: 'Manage your AI agent projects'
  },
]

// Project-scoped nav items
const projectNavItems = [
  {
    title: 'Skills',
    path: 'skills',
    icon: Lightbulb,
    description: 'Reusable AI agent skills'
  },
  {
    title: 'Cards',
    path: 'cards',
    icon: FileText,
    description: 'Task cards and workflows'
  },
  {
    title: 'LLM Runs',
    path: 'llm-runs',
    icon: Zap,
    description: 'AI model execution logs'
  },
  {
    title: 'Settings',
    path: 'settings',
    icon: Settings,
    description: 'Configuration and preferences'
  },
]

export function MobileNav() {
  const pathname = usePathname()
  const [open, setOpen] = React.useState(false)
  
  // Extract project slug from pathname
  const projectMatch = pathname?.match(/^\/projects\/([^/]+)/)
  const projectSlug = projectMatch ? projectMatch[1] : null

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="sm" className="md:hidden">
          <Menu className="h-5 w-5" />
          <span className="sr-only">Toggle navigation menu</span>
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-[300px] sm:w-[400px]">
        <SheetHeader>
          <SheetTitle>Agents Workshop</SheetTitle>
          <SheetDescription>
            AI-powered tool for generating programming skills and workflows
          </SheetDescription>
        </SheetHeader>
        <nav className="flex flex-col space-y-2 mt-6">
          {/* Global nav items */}
          {globalNavItems.map((item) => {
            const isActive = pathname === item.href || pathname?.startsWith(item.href + '/')
            const Icon = item.icon
            
            return (
              <Link
                key={item.href}
                href={item.href as any}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-start space-x-3 rounded-md p-3 transition-colors hover:bg-accent hover:text-accent-foreground",
                  isActive ? "bg-accent text-accent-foreground" : "text-muted-foreground"
                )}
              >
                <Icon className="h-5 w-5 mt-0.5" />
                <div>
                  <div className="font-medium">{item.title}</div>
                  <div className="text-sm text-muted-foreground">{item.description}</div>
                </div>
              </Link>
            )
          })}
          
          {/* Project-scoped nav items */}
          {projectSlug && (
            <>
              <div className="text-xs font-medium text-muted-foreground px-3 pt-4">
                Current Project
              </div>
              {projectNavItems.map((item) => {
                const href = `/projects/${projectSlug}/${item.path}`
                const isActive = pathname?.includes(`/${item.path}`)
                const Icon = item.icon
                
                return (
                  <Link
                    key={item.path}
                    href={href as any}
                    onClick={() => setOpen(false)}
                    className={cn(
                      "flex items-start space-x-3 rounded-md p-3 transition-colors hover:bg-accent hover:text-accent-foreground",
                      isActive ? "bg-accent text-accent-foreground" : "text-muted-foreground"
                    )}
                  >
                    <Icon className="h-5 w-5 mt-0.5" />
                    <div>
                      <div className="font-medium">{item.title}</div>
                      <div className="text-sm text-muted-foreground">{item.description}</div>
                    </div>
                  </Link>
                )
              })}
            </>
          )}
        </nav>
      </SheetContent>
    </Sheet>
  )
}