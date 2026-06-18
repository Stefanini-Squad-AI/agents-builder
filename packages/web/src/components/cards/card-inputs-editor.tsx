'use client';

import { useState } from 'react';
import {
  useCardInputs,
  useCreateCardInput,
  useUpdateCardInput,
  useDeleteCardInput,
} from '@/lib/api/queries';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
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
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { CardInputKind, CardInputView } from '@/lib/api/types';
import { Plus, Pencil, Trash2, Loader2 } from 'lucide-react';

const INPUT_KIND_OPTIONS: { value: CardInputKind; label: string; description: string }[] = [
  { value: CardInputKind.SKILL_RESOURCE, label: 'Skill Resource', description: 'Reference to a skill resource file' },
  { value: CardInputKind.ARTIFACT, label: 'Artifact', description: 'Project artifact file' },
  { value: CardInputKind.EXTERNAL, label: 'External', description: 'External file or URL' },
];

interface CardInputsEditorProps {
  projectSlug: string;
  cardId: string;
}

export function CardInputsEditor({ projectSlug, cardId }: CardInputsEditorProps) {
  const { data: inputs, isLoading } = useCardInputs(projectSlug, cardId);
  const createInput = useCreateCardInput(projectSlug, cardId);
  const updateInput = useUpdateCardInput(projectSlug, cardId);
  const deleteInput = useDeleteCardInput(projectSlug, cardId);

  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [editingInput, setEditingInput] = useState<CardInputView | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Add Input
            </Button>
          </DialogTrigger>
          <InputDialog
            title="Add Input"
            description="Add a new input to this card."
            onSubmit={async (data) => {
              await createInput.mutateAsync(data);
              setIsAddDialogOpen(false);
            }}
            isPending={createInput.isPending}
          />
        </Dialog>
      </div>

      {inputs && inputs.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Kind</TableHead>
              <TableHead>Path</TableHead>
              <TableHead>Label</TableHead>
              <TableHead className="w-[100px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {inputs.map((input) => (
              <TableRow key={input.id}>
                <TableCell>
                  <span className="inline-flex items-center rounded-md bg-muted px-2 py-1 text-xs font-medium">
                    {INPUT_KIND_OPTIONS.find((o) => o.value === input.kind)?.label || input.kind}
                  </span>
                </TableCell>
                <TableCell className="font-mono text-sm">{input.path}</TableCell>
                <TableCell>{input.label || '-'}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <Dialog
                      open={editingInput?.id === input.id}
                      onOpenChange={(open) => setEditingInput(open ? input : null)}
                    >
                      <DialogTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <Pencil className="h-4 w-4" />
                        </Button>
                      </DialogTrigger>
                      <InputDialog
                        title="Edit Input"
                        description="Update this input."
                        initialData={input}
                        onSubmit={async (data) => {
                          await updateInput.mutateAsync({ inputId: input.id, data });
                          setEditingInput(null);
                        }}
                        isPending={updateInput.isPending}
                      />
                    </Dialog>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Delete Input</AlertDialogTitle>
                          <AlertDialogDescription>
                            Are you sure you want to delete this input? This action cannot be undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={() => deleteInput.mutate(input.id)}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                          >
                            Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <div className="text-center py-8 text-muted-foreground">
          No inputs defined. Add inputs to specify resources required for this card.
        </div>
      )}
    </div>
  );
}

interface InputDialogProps {
  title: string;
  description: string;
  initialData?: CardInputView;
  onSubmit: (data: { kind: CardInputKind; path: string; label?: string; order_no?: number }) => Promise<void>;
  isPending: boolean;
}

function InputDialog({ title, description, initialData, onSubmit, isPending }: InputDialogProps) {
  const [formData, setFormData] = useState({
    kind: initialData?.kind || CardInputKind.SKILL_RESOURCE,
    path: initialData?.path || '',
    label: initialData?.label || '',
    order_no: initialData?.order_no || 0,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmit({
      kind: formData.kind,
      path: formData.path,
      label: formData.label || undefined,
      order_no: formData.order_no,
    });
  };

  return (
    <DialogContent>
      <form onSubmit={handleSubmit}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="kind">Kind</Label>
            <Select
              value={formData.kind}
              onValueChange={(value) => setFormData((prev) => ({ ...prev, kind: value as CardInputKind }))}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {INPUT_KIND_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    <div className="flex flex-col">
                      <span>{option.label}</span>
                      <span className="text-xs text-muted-foreground">{option.description}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="path">Path</Label>
            <Input
              id="path"
              value={formData.path}
              onChange={(e) => setFormData((prev) => ({ ...prev, path: e.target.value }))}
              placeholder="e.g., skill:my-skill/resource.sql or artifacts/schema.json"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="label">Label (optional)</Label>
            <Input
              id="label"
              value={formData.label}
              onChange={(e) => setFormData((prev) => ({ ...prev, label: e.target.value }))}
              placeholder="Descriptive label for this input"
            />
          </div>
        </div>
        <DialogFooter>
          <Button type="submit" disabled={isPending || !formData.path}>
            {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {initialData ? 'Update' : 'Add'}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}
