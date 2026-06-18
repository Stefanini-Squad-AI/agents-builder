import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type { ProjectView } from '@/lib/api/types'

interface ProjectStore {
  // Current project being viewed/edited
  currentProject: ProjectView | null
  setCurrentProject: (project: ProjectView | null) => void

  // Projects list state
  projects: ProjectView[]
  setProjects: (projects: ProjectView[]) => void
  addProject: (project: ProjectView) => void
  updateProject: (id: string, updates: Partial<ProjectView>) => void
  removeProject: (id: string) => void

  // UI state
  isCreating: boolean
  setIsCreating: (creating: boolean) => void
  
  isEditing: boolean
  setIsEditing: (editing: boolean) => void

  // Search and filters
  searchTerm: string
  setSearchTerm: (term: string) => void

  statusFilter: string
  setStatusFilter: (status: string) => void
}

export const useProjectStore = create<ProjectStore>()(
  devtools(
    (set, get) => ({
      // Current project
      currentProject: null,
      setCurrentProject: (project) => set({ currentProject: project }, false, 'setCurrentProject'),

      // Projects list
      projects: [],
      setProjects: (projects) => set({ projects }, false, 'setProjects'),
      
      addProject: (project) => {
        const { projects } = get()
        set({ projects: [project, ...projects] }, false, 'addProject')
      },
      
      updateProject: (id, updates) => {
        const { projects, currentProject } = get()
        const updatedProjects = projects.map(p => 
          p.id === id ? { ...p, ...updates } : p
        )
        const updatedCurrentProject = currentProject?.id === id 
          ? { ...currentProject, ...updates }
          : currentProject
        
        set({ 
          projects: updatedProjects, 
          currentProject: updatedCurrentProject 
        }, false, 'updateProject')
      },
      
      removeProject: (id) => {
        const { projects, currentProject } = get()
        const filteredProjects = projects.filter(p => p.id !== id)
        const updatedCurrentProject = currentProject?.id === id ? null : currentProject
        
        set({ 
          projects: filteredProjects, 
          currentProject: updatedCurrentProject 
        }, false, 'removeProject')
      },

      // UI state
      isCreating: false,
      setIsCreating: (creating) => set({ isCreating: creating }, false, 'setIsCreating'),
      
      isEditing: false,
      setIsEditing: (editing) => set({ isEditing: editing }, false, 'setIsEditing'),

      // Search and filters
      searchTerm: '',
      setSearchTerm: (term) => set({ searchTerm: term }, false, 'setSearchTerm'),

      statusFilter: 'all',
      setStatusFilter: (status) => set({ statusFilter: status }, false, 'setStatusFilter'),
    }),
    {
      name: 'project-store',
    }
  )
)