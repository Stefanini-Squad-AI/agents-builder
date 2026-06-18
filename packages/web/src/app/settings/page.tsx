'use client'

import React, { useState, useEffect } from 'react'
import { useAuth } from '@/lib/auth/context'
import { useRouteProtection } from '@/lib/auth/hooks'
import { useLlmProviders, useTestLlmProvider } from '@/lib/api/queries'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { 
  User, 
  Shield, 
  Bot, 
  Palette, 
  CheckCircle2, 
  XCircle, 
  Loader2,
  Zap,
  AlertCircle 
} from 'lucide-react'

export default function SettingsPage() {
  useRouteProtection() // Ensure user is authenticated
  const { user } = useAuth()

  // LLM settings state
  const [selectedProvider, setSelectedProvider] = useState<string>('anthropic')
  const [selectedModel, setSelectedModel] = useState<string>('claude-sonnet-4-5')
  const [temperature, setTemperature] = useState<number>(0.2)

  // Queries
  const { data: providers, isLoading: isLoadingProviders } = useLlmProviders()
  const testProvider = useTestLlmProvider()

  // Get models for selected provider
  const currentProvider = providers?.find(p => p.provider === selectedProvider)
  const availableModels = currentProvider?.models || []

  // Update model when provider changes
  useEffect(() => {
    if (currentProvider && availableModels.length > 0) {
      const modelExists = availableModels.some(m => m.id === selectedModel)
      if (!modelExists) {
        setSelectedModel(availableModels[0].id)
      }
    }
  }, [selectedProvider, currentProvider, availableModels, selectedModel])

  const handleTestConnection = () => {
    testProvider.mutate({ provider: selectedProvider, model: selectedModel })
  }

  if (!user) {
    return null // Will redirect via useRouteProtection
  }

  return (
    <div className="container mx-auto py-8 space-y-8">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account settings and preferences
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* LLM Configuration - Full Width */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-5 w-5" />
              LLM Configuration
            </CardTitle>
            <CardDescription>
              Configure the AI model used for generating skills, cards, and suggestions
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid gap-6 md:grid-cols-2">
              {/* Provider Selection */}
              <div className="space-y-2">
                <Label htmlFor="llmProvider">Provider</Label>
                <Select 
                  value={selectedProvider} 
                  onValueChange={setSelectedProvider}
                  disabled={isLoadingProviders}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {providers?.map((provider) => (
                      <SelectItem key={provider.provider} value={provider.provider}>
                        <div className="flex items-center gap-2">
                          {provider.available ? (
                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                          ) : (
                            <XCircle className="h-4 w-4 text-red-500" />
                          )}
                          <span>{provider.name}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {currentProvider && !currentProvider.available && (
                  <p className="text-sm text-yellow-600 flex items-center gap-1">
                    <AlertCircle className="h-3 w-3" />
                    {currentProvider.status_message}
                  </p>
                )}
              </div>

              {/* Model Selection */}
              <div className="space-y-2">
                <Label htmlFor="llmModel">Model</Label>
                <Select 
                  value={selectedModel} 
                  onValueChange={setSelectedModel}
                  disabled={isLoadingProviders || availableModels.length === 0}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select model" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableModels.map((model) => (
                      <SelectItem key={model.id} value={model.id}>
                        <div className="flex flex-col">
                          <span>{model.name}</span>
                          {model.description && (
                            <span className="text-xs text-muted-foreground">
                              {model.description}
                            </span>
                          )}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Temperature Slider */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label>Temperature</Label>
                <span className="text-sm font-mono bg-muted px-2 py-1 rounded">
                  {temperature.toFixed(2)}
                </span>
              </div>
              <Slider
                value={[temperature]}
                onValueChange={(value: number[]) => setTemperature(value[0])}
                min={0}
                max={1}
                step={0.05}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Deterministic (0.0)</span>
                <span>Creative (1.0)</span>
              </div>
            </div>

            <Separator />

            {/* Test Connection */}
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <h4 className="text-sm font-medium">Test Connection</h4>
                <p className="text-sm text-muted-foreground">
                  Verify the selected provider is accessible with your credentials
                </p>
              </div>
              <div className="flex items-center gap-3">
                {testProvider.isSuccess && (
                  <div className="flex items-center gap-1 text-green-600">
                    <CheckCircle2 className="h-4 w-4" />
                    <span className="text-sm">
                      Connected
                      {testProvider.data?.latency_ms && ` (${testProvider.data.latency_ms}ms)`}
                    </span>
                  </div>
                )}
                {testProvider.isError && (
                  <div className="flex items-center gap-1 text-red-600">
                    <XCircle className="h-4 w-4" />
                    <span className="text-sm">Failed</span>
                  </div>
                )}
                <Button 
                  variant="outline" 
                  onClick={handleTestConnection}
                  disabled={testProvider.isPending}
                >
                  {testProvider.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Zap className="mr-2 h-4 w-4" />
                  )}
                  Test
                </Button>
              </div>
            </div>

            {testProvider.data && !testProvider.data.available && testProvider.data.error_message && (
              <div className="p-3 bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-300 rounded-lg text-sm">
                {testProvider.data.error_message}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Profile Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5" />
              Profile Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" value={user.name || ''} disabled />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" value={user.email} disabled />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <Badge variant="secondary">{user.role}</Badge>
            </div>
            <div className="space-y-2">
              <Label>Tenant ID</Label>
              <Badge variant="outline">{user.tenant_id}</Badge>
            </div>
            <Button disabled>
              Edit Profile (Coming Soon)
            </Button>
          </CardContent>
        </Card>

        {/* Security Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Security
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Password</Label>
              <div className="flex gap-2">
                <Input type="password" value="••••••••" disabled />
                <Button variant="outline" disabled>
                  Change
                </Button>
              </div>
            </div>
            <Separator />
            <div className="space-y-2">
              <Label>Two-Factor Authentication</Label>
              <p className="text-sm text-muted-foreground">
                Add an extra layer of security to your account
              </p>
              <Button variant="outline" disabled>
                Enable 2FA (Coming Soon)
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Appearance Settings */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Palette className="h-5 w-5" />
              Appearance
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <Label>Theme</Label>
                <p className="text-sm text-muted-foreground">
                  Theme is controlled by the toggle in the header
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled>
                  Light
                </Button>
                <Button variant="outline" size="sm" disabled>
                  Dark
                </Button>
                <Button variant="outline" size="sm" disabled>
                  System
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Danger Zone */}
      <Card className="border-destructive">
        <CardHeader>
          <CardTitle className="text-destructive">Danger Zone</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <h4 className="font-medium">Delete Account</h4>
            <p className="text-sm text-muted-foreground">
              Permanently delete your account and all associated data. This action cannot be undone.
            </p>
            <Button variant="destructive" disabled>
              Delete Account (Coming Soon)
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}