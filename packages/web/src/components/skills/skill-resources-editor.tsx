'use client';

import { useState, useCallback } from 'react';
import {
  useCreateSkillResource,
  useUpdateSkillResource,
  useDeleteSkillResource,
} from '@/lib/api/queries';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { CodeEditor } from '@/components/ui/code-editor';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { SkillResourceView, SkillResourceLanguage } from '@/lib/api/types';
import { Plus, Trash2, Pencil, Loader2, FileCode } from 'lucide-react';

const LANGUAGE_OPTIONS: { value: SkillResourceLanguage; label: string }[] = [
  { value: SkillResourceLanguage.MARKDOWN, label: 'Markdown' },
  { value: SkillResourceLanguage.SQL, label: 'SQL' },
  { value: SkillResourceLanguage.YAML, label: 'YAML' },
  { value: SkillResourceLanguage.PYTHON, label: 'Python' },
  { value: SkillResourceLanguage.PLAIN, label: 'Plain Text' },
];

interface SkillResourcesEditorProps {
  projectSlug: string;
  skillSlug: string;
  resources: SkillResourceView[];
}

interface ResourceFormState {
  filename: string;
  content: string;
  language: SkillResourceLanguage;
}

const EMPTY_FORM: ResourceFormState = {
  filename: '',
  content: '',
  language: SkillResourceLanguage.MARKDOWN,
};

export function SkillResourcesEditor({
  projectSlug,
  skillSlug,
  resources,
}: SkillResourcesEditorProps) {
  // Mutations
  const createResource = useCreateSkillResource(projectSlug, skillSlug);
  const updateResource = useUpdateSkillResource(projectSlug, skillSlug);
  const deleteResource = useDeleteSkillResource(projectSlug, skillSlug);

  // Dialog state
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selectedResource, setSelectedResource] = useState<SkillResourceView | null>(null);

  // Form state
  const [formData, setFormData] = useState<ResourceFormState>(EMPTY_FORM);

  // Handle create
  const handleCreate = useCallback(async () => {
    if (!formData.filename.trim()) return;

    try {
      await createResource.mutateAsync({
        filename: formData.filename,
        content: formData.content,
        language: formData.language,
      });
      setCreateOpen(false);
      setFormData(EMPTY_FORM);
    } catch (error) {
      console.error('Failed to create resource:', error);
    }
  }, [formData, createResource]);

  // Handle edit
  const handleEdit = useCallback(async () => {
    if (!selectedResource || !formData.filename.trim()) return;

    try {
      await updateResource.mutateAsync({
        resourceId: selectedResource.id,
        request: {
          filename: formData.filename,
          content: formData.content,
          language: formData.language,
        },
      });
      setEditOpen(false);
      setSelectedResource(null);
      setFormData(EMPTY_FORM);
    } catch (error) {
      console.error('Failed to update resource:', error);
    }
  }, [selectedResource, formData, updateResource]);

  // Handle delete
  const handleDelete = useCallback(async () => {
    if (!selectedResource) return;

    try {
      await deleteResource.mutateAsync(selectedResource.id);
      setDeleteOpen(false);
      setSelectedResource(null);
    } catch (error) {
      console.error('Failed to delete resource:', error);
    }
  }, [selectedResource, deleteResource]);

  // Open edit dialog
  const openEditDialog = useCallback((resource: SkillResourceView) => {
    setSelectedResource(resource);
    setFormData({
      filename: resource.filename,
      content: resource.content,
      language: resource.language,
    });
    setEditOpen(true);
  }, []);

  // Open delete dialog
  const openDeleteDialog = useCallback((resource: SkillResourceView) => {
    setSelectedResource(resource);
    setDeleteOpen(true);
  }, []);

  const isLoading =
    createResource.isPending ||
    updateResource.isPending ||
    deleteResource.isPending;

  return (
    <div className="space-y-4">
      {/* Resources list */}
      {resources.length === 0 ? (
        <div className="text-center py-12 border rounded-lg border-dashed">
          <FileCode className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <p className="text-muted-foreground mb-4">No resources yet</p>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button variant="outline">
                <Plus className="mr-2 h-4 w-4" />
                Add Resource
              </Button>
            </DialogTrigger>
            <ResourceDialogContent
              title="Add Resource"
              description="Create a new resource file for this skill."
              formData={formData}
              setFormData={setFormData}
              onSubmit={handleCreate}
              isLoading={createResource.isPending}
              submitLabel="Create"
            />
          </Dialog>
        </div>
      ) : (
        <div className="space-y-2">
          {resources.map((resource) => (
            <div
              key={resource.id}
              className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <FileCode className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="font-medium">{resource.filename}</p>
                  <p className="text-sm text-muted-foreground">
                    {getLanguageLabel(resource.language)} •{' '}
                    {resource.content.length} chars
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => openEditDialog(resource)}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => openDeleteDialog(resource)}
                  className="text-destructive hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}

          {/* Add button at bottom */}
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="w-full mt-4">
                <Plus className="mr-2 h-4 w-4" />
                Add Resource
              </Button>
            </DialogTrigger>
            <ResourceDialogContent
              title="Add Resource"
              description="Create a new resource file for this skill."
              formData={formData}
              setFormData={setFormData}
              onSubmit={handleCreate}
              isLoading={createResource.isPending}
              submitLabel="Create"
            />
          </Dialog>
        </div>
      )}

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <ResourceDialogContent
          title="Edit Resource"
          description="Update the resource file."
          formData={formData}
          setFormData={setFormData}
          onSubmit={handleEdit}
          isLoading={updateResource.isPending}
          submitLabel="Save"
        />
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Resource</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{selectedResource?.filename}&quot;? This
              action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteResource.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// Helper to get language label
function getLanguageLabel(language: SkillResourceLanguage): string {
  const option = LANGUAGE_OPTIONS.find((o) => o.value === language);
  return option?.label || language;
}

// Shared dialog content component
function ResourceDialogContent({
  title,
  description,
  formData,
  setFormData,
  onSubmit,
  isLoading,
  submitLabel,
}: {
  title: string;
  description: string;
  formData: ResourceFormState;
  setFormData: (data: ResourceFormState) => void;
  onSubmit: () => void;
  isLoading: boolean;
  submitLabel: string;
}) {
  return (
    <DialogContent className="max-w-2xl">
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{description}</DialogDescription>
      </DialogHeader>
      <div className="space-y-4 py-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="filename">Filename</Label>
            <Input
              id="filename"
              value={formData.filename}
              onChange={(e) =>
                setFormData({ ...formData, filename: e.target.value })
              }
              placeholder="example.sql"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="language">Language</Label>
            <Select
              value={formData.language}
              onValueChange={(value) =>
                setFormData({
                  ...formData,
                  language: value as SkillResourceLanguage,
                })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LANGUAGE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="content">Content</Label>
          <CodeEditor
            value={formData.content}
            onChange={(value) => setFormData({ ...formData, content: value })}
            language={formData.language}
            placeholder="Enter resource content..."
            minHeight="200px"
            maxHeight="400px"
          />
        </div>
      </div>
      <DialogFooter>
        <Button onClick={onSubmit} disabled={isLoading || !formData.filename.trim()}>
          {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {submitLabel}
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}

export default SkillResourcesEditor;
