'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { 
  Home,
  FolderOpen, 
  Lightbulb, 
  Settings,
  FileText,
  Zap
} from 'lucide-react'

// Global nav items (always show)
const globalNavItems = [
  {
    title: 'Dashboard',
    href: '/dashboard',
    icon: Home,
  },
  {
    title: 'Projects',
    href: '/projects',
    icon: FolderOpen,
  },
]

// Project-scoped nav items (show when in a project)
const projectNavItems = [
  {
    title: 'Skills',
    path: 'skills',
    icon: Lightbulb,
  },
  {
    title: 'Cards',
    path: 'cards',
    icon: FileText,
  },
  {
    title: 'LLM Runs',
    path: 'llm-runs',
    icon: Zap,
  },
  {
    title: 'Settings',
    path: 'settings',
    icon: Settings,
  },
]

export function MainNav() {
  const pathname = usePathname()
  
  // Extract project slug from pathname if we're in a project
  const projectMatch = pathname?.match(/^\/projects\/([^/]+)/)
  const projectSlug = projectMatch ? projectMatch[1] : null

  return (
    <nav className="flex items-center space-x-6 text-sm font-medium">
      {/* Global nav items */}
      {globalNavItems.map((item) => {
        const isActive = pathname === item.href || pathname?.startsWith(item.href + '/')
        const Icon = item.icon
        
        return (
          <Link
            key={item.href}
            href={item.href as any}
            className={cn(
              "flex items-center space-x-1 transition-colors hover:text-foreground/80",
              isActive ? "text-foreground" : "text-foreground/60"
            )}
          >
            <Icon className="h-4 w-4" />
            <span className="hidden sm:inline-block">{item.title}</span>
          </Link>
        )
      })}
      
      {/* Project-scoped nav items - only show when in a project */}
      {projectSlug && projectNavItems.map((item) => {
        const href = `/projects/${projectSlug}/${item.path}`
        const isActive = pathname?.includes(`/${item.path}`)
        const Icon = item.icon
        
        return (
          <Link
            key={item.path}
            href={href as any}
            className={cn(
              "flex items-center space-x-1 transition-colors hover:text-foreground/80",
              isActive ? "text-foreground" : "text-foreground/60"
            )}
          >
            <Icon className="h-4 w-4" />
            <span className="hidden sm:inline-block">{item.title}</span>
          </Link>
        )
      })}
    </nav>
  )
}