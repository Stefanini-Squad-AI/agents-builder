'use client';

import { useMemo } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  MCPCatalogEntry,
  MCPConfigCreate,
  MCPConfigUpdate,
  MCPConfigView,
} from '@/lib/api/types';
import { Lock, Unlock, KeyRound } from 'lucide-react';

interface DynamicMcpFormProps {
  entry: MCPCatalogEntry;
  mode: 'create' | 'edit';
  /** Existing config (mode=edit only). Secrets are masked. */
  existing?: MCPConfigView;
  onSubmit: (
    payload: MCPConfigCreate | MCPConfigUpdate,
    enabled: boolean
  ) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

/**
 * Build a Zod schema from the catalog entry's env_vars + config_fields.
 *
 * - Required string envs must be non-empty in CREATE mode.
 * - In EDIT mode, secret env fields can be left blank (means "keep existing").
 *   Non-secret env fields can also be left blank (backend will reject if
 *   they were never set, but the FE shape is the same).
 * - config_fields are typed as string in the form; we coerce on submit.
 */
function buildSchema(entry: MCPCatalogEntry, mode: 'create' | 'edit') {
  const envShape: Record<string, z.ZodTypeAny> = {};
  for (const [key, def] of Object.entries(entry.env_vars)) {
    let s = z.string();
    if (def.required && mode === 'create') {
      s = s.min(1, `${def.label} is required`);
    }
    envShape[key] = s.optional().default('');
  }

  const cfgShape: Record<string, z.ZodTypeAny> = {};
  for (const [key, def] of Object.entries(entry.config_fields)) {
    if (def.type === 'boolean') {
      cfgShape[key] = z.boolean().optional().default(false);
      continue;
    }

    let s: z.ZodTypeAny = z.string();
    if (def.type === 'number') {
      s = z
        .string()
        .refine(
          (v) => v === '' || !Number.isNaN(Number(v)),
          `${def.label} must be a number`
        );
    } else if (def.type === 'url') {
      s = z
        .string()
        .refine(
          (v) => v === '' || /^https?:\/\//.test(v),
          `${def.label} must start with http:// or https://`
        );
    }
    if (def.required && mode === 'create') {
      s = (s as z.ZodString).min(1, `${def.label} is required`);
    }
    cfgShape[key] = s.optional().default(def.default ?? '');
  }

  return z.object({
    env_vars: z.object(envShape),
    config_fields: z.object(cfgShape),
    enabled: z.boolean().default(true),
  });
}

export function DynamicMcpForm({
  entry,
  mode,
  existing,
  onSubmit,
  onCancel,
  isSubmitting,
}: DynamicMcpFormProps) {
  const schema = useMemo(() => buildSchema(entry, mode), [entry, mode]);
  type FormValues = z.infer<typeof schema>;

  const defaultEnvVars = useMemo(() => {
    const out: Record<string, string> = {};
    for (const key of Object.keys(entry.env_vars)) {
      // In edit mode, leave blank — user fills only what they want to change.
      out[key] = '';
    }
    return out;
  }, [entry.env_vars]);

  const defaultConfigFields = useMemo(() => {
    const out: Record<string, string | boolean> = {};
    for (const [key, def] of Object.entries(entry.config_fields)) {
      if (def.type === 'boolean') {
        const cur = existing?.config_fields[key];
        out[key] = typeof cur === 'boolean' ? cur : false;
      } else {
        const cur = existing?.config_fields[key];
        out[key] = cur !== undefined && cur !== null ? String(cur) : def.default ?? '';
      }
    }
    return out;
  }, [entry.config_fields, existing]);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      env_vars: defaultEnvVars,
      config_fields: defaultConfigFields,
      enabled: existing?.enabled ?? true,
    } as FormValues,
  });

  function handleSubmit(values: FormValues) {
    // Coerce config_fields based on entry definitions
    const coerced: Record<string, string | number | boolean> = {};
    for (const [key, def] of Object.entries(entry.config_fields)) {
      const v = (values.config_fields as Record<string, unknown>)[key];
      if (def.type === 'number') {
        if (typeof v === 'string' && v !== '') coerced[key] = Number(v);
      } else if (def.type === 'boolean') {
        coerced[key] = Boolean(v);
      } else if (typeof v === 'string' && v !== '') {
        coerced[key] = v;
      }
    }

    // Filter out empty env_vars in edit mode (means "keep existing")
    const cleanedEnv: Record<string, string> = {};
    for (const [key, v] of Object.entries(values.env_vars)) {
      if (typeof v === 'string' && v !== '') cleanedEnv[key] = v;
    }

    if (mode === 'create') {
      const payload: MCPConfigCreate = {
        mcp_key: entry.key,
        env_vars: cleanedEnv,
        config_fields: coerced,
        enabled: values.enabled,
      };
      onSubmit(payload, values.enabled);
    } else {
      const payload: MCPConfigUpdate = {
        env_vars: Object.keys(cleanedEnv).length > 0 ? cleanedEnv : undefined,
        config_fields: Object.keys(coerced).length > 0 ? coerced : undefined,
        enabled: values.enabled,
      };
      onSubmit(payload, values.enabled);
    }
  }

  const envEntries = Object.entries(entry.env_vars);
  const cfgEntries = Object.entries(entry.config_fields);

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-5">
        {envEntries.length > 0 && (
          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Environment variables</h3>
            {envEntries.map(([key, def]) => (
              <FormField
                key={key}
                control={form.control}
                name={`env_vars.${key}` as const}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="flex items-center gap-2">
                      {def.label}
                      {def.required && (
                        <span className="text-destructive">*</span>
                      )}
                      {def.secret ? (
                        <Lock className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
                      ) : (
                        <Unlock className="h-3.5 w-3.5 text-muted-foreground" />
                      )}
                      <code className="ml-auto text-xs text-muted-foreground">
                        {key}
                      </code>
                    </FormLabel>
                    <FormControl>
                      <Input
                        type={def.secret ? 'password' : 'text'}
                        placeholder={
                          mode === 'edit'
                            ? def.secret
                              ? '(unchanged — leave blank to keep)'
                              : '(leave blank to keep current value)'
                            : def.hint || def.label
                        }
                        autoComplete={def.secret ? 'new-password' : 'off'}
                        {...field}
                        value={typeof field.value === 'string' ? field.value : ''}
                      />
                    </FormControl>
                    {def.hint && (
                      <FormDescription>{def.hint}</FormDescription>
                    )}
                    <FormMessage />
                  </FormItem>
                )}
              />
            ))}
          </section>
        )}

        {cfgEntries.length > 0 && (
          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Configuration</h3>
            {cfgEntries.map(([key, def]) => (
              <FormField
                key={key}
                control={form.control}
                name={`config_fields.${key}` as const}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="flex items-center gap-2">
                      {def.label}
                      {def.required && (
                        <span className="text-destructive">*</span>
                      )}
                      <code className="ml-auto text-xs text-muted-foreground">
                        {key}
                      </code>
                    </FormLabel>
                    <FormControl>
                      {def.type === 'boolean' ? (
                        <div className="flex items-center gap-2 rounded-md border bg-background px-3 py-2">
                          <Checkbox
                            id={`cfg-${key}`}
                            checked={Boolean(field.value)}
                            onCheckedChange={(v) => field.onChange(Boolean(v))}
                          />
                          <label
                            htmlFor={`cfg-${key}`}
                            className="text-sm leading-none"
                          >
                            {def.hint || 'Enabled'}
                          </label>
                        </div>
                      ) : (
                        <Input
                          type={def.type === 'number' ? 'number' : 'text'}
                          placeholder={def.hint || def.label}
                          {...field}
                          value={
                            field.value === undefined || field.value === null
                              ? ''
                              : String(field.value)
                          }
                        />
                      )}
                    </FormControl>
                    {def.hint && def.type !== 'boolean' && (
                      <FormDescription>{def.hint}</FormDescription>
                    )}
                    <FormMessage />
                  </FormItem>
                )}
              />
            ))}
          </section>
        )}

        {entry.has_secrets && (
          <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-200">
            <KeyRound className="mt-0.5 h-4 w-4 text-amber-600 dark:text-amber-400" />
            <span>
              Secrets are encrypted at rest. They&apos;re only decrypted when
              you export <code>mcp.json</code>.
            </span>
          </div>
        )}

        <FormField
          control={form.control}
          name="enabled"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center gap-3 space-y-0 rounded-md border bg-background p-3">
              <FormControl>
                <Checkbox
                  checked={Boolean(field.value)}
                  onCheckedChange={(v) => field.onChange(Boolean(v))}
                />
              </FormControl>
              <div className="space-y-0.5">
                <FormLabel className="text-sm font-medium">
                  Enabled
                </FormLabel>
                <FormDescription className="text-xs">
                  Disabled MCPs aren&apos;t included in the exported{' '}
                  <code>mcp.json</code>.
                </FormDescription>
              </div>
            </FormItem>
          )}
        />

        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting
              ? mode === 'create'
                ? 'Configuring…'
                : 'Saving…'
              : mode === 'create'
                ? 'Configure MCP'
                : 'Save changes'}
          </Button>
        </div>
      </form>
    </Form>
  );
}
