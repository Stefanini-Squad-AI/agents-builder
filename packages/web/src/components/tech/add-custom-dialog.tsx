'use client';

import { useState, useCallback } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, X } from 'lucide-react';
import { TechChoiceRole } from '@/lib/api/types';

const addCustomSchema = z.object({
  name: z
    .string()
    .min(1, 'Name is required')
    .max(100, 'Name must be 100 characters or less')
    .regex(/^[a-zA-Z0-9\s\-_.+#]+$/, 'Only letters, numbers, spaces, and common symbols allowed'),
  description: z
    .string()
    .max(500, 'Description must be 500 characters or less')
    .optional(),
  role: z.nativeEnum(TechChoiceRole).default(TechChoiceRole.TARGET),
  tags: z.array(z.string()).optional(),
  notes: z.string().max(500).optional(),
});

type AddCustomFormData = z.infer<typeof addCustomSchema>;

interface AddCustomDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  dimensionName: string;
  dimensionSlug: string;
  onSubmit: (data: {
    name: string;
    description?: string;
    role: TechChoiceRole;
    tags?: string[];
    notes?: string;
  }) => Promise<void>;
  isSubmitting?: boolean;
}

const roleOptions = [
  { value: TechChoiceRole.TARGET, label: 'Target - Primary technology to use' },
  { value: TechChoiceRole.LEGACY, label: 'Legacy - Existing technology to migrate from' },
  { value: TechChoiceRole.OPTIONAL, label: 'Optional - Can be used if needed' },
  { value: TechChoiceRole.MUST_AVOID, label: 'Must Avoid - Do not use in project' },
];

/**
 * Dialog for adding custom tech items to a dimension.
 */
export function AddCustomDialog({
  open,
  onOpenChange,
  dimensionName,
  dimensionSlug,
  onSubmit,
  isSubmitting,
}: AddCustomDialogProps) {
  const [tagInput, setTagInput] = useState('');
  
  const form = useForm<AddCustomFormData>({
    resolver: zodResolver(addCustomSchema),
    defaultValues: {
      name: '',
      description: '',
      role: TechChoiceRole.TARGET,
      tags: [],
      notes: '',
    },
  });

  const tags = form.watch('tags') || [];

  const handleAddTag = useCallback(() => {
    const trimmed = tagInput.trim().toLowerCase();
    if (trimmed && !tags.includes(trimmed)) {
      form.setValue('tags', [...tags, trimmed]);
      setTagInput('');
    }
  }, [tagInput, tags, form]);

  const handleRemoveTag = useCallback((tag: string) => {
    form.setValue('tags', tags.filter(t => t !== tag));
  }, [tags, form]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddTag();
    }
  }, [handleAddTag]);

  const handleSubmit = async (data: AddCustomFormData) => {
    try {
      await onSubmit({
        name: data.name.trim(),
        description: data.description?.trim(),
        role: data.role,
        tags: data.tags?.length ? data.tags : undefined,
        notes: data.notes?.trim(),
      });
      form.reset();
      onOpenChange(false);
    } catch (error) {
      // Error is handled by the mutation
    }
  };

  const handleClose = () => {
    form.reset();
    setTagInput('');
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add Custom Technology</DialogTitle>
          <DialogDescription>
            Add a custom technology to <strong>{dimensionName}</strong>.
            It will be available only for this project.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name *</FormLabel>
                  <FormControl>
                    <Input 
                      placeholder="e.g., My Custom Framework" 
                      {...field} 
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea 
                      placeholder="Brief description of this technology..."
                      rows={2}
                      {...field} 
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="role"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Role *</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    defaultValue={field.value}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select role" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {roleOptions.map(option => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="space-y-2">
              <FormLabel>Tags</FormLabel>
              <div className="flex gap-2">
                <Input
                  placeholder="Add a tag..."
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleAddTag}
                  disabled={!tagInput.trim()}
                >
                  Add
                </Button>
              </div>
              {tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {tags.map(tag => (
                    <Badge key={tag} variant="secondary" className="gap-1">
                      {tag}
                      <button
                        type="button"
                        onClick={() => handleRemoveTag(tag)}
                        className="hover:text-destructive"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
              <FormDescription>
                Optional tags to help categorize this technology
              </FormDescription>
            </div>

            <FormField
              control={form.control}
              name="notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Notes</FormLabel>
                  <FormControl>
                    <Textarea 
                      placeholder="Why you're adding this technology..."
                      rows={2}
                      {...field} 
                    />
                  </FormControl>
                  <FormDescription>
                    Optional notes for your team
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter className="gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={handleClose}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                )}
                Add Technology
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

export default AddCustomDialog;
