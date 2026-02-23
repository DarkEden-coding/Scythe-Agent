import { useState } from 'react';
import {
  Check,
  ChevronDown,
  ChevronRight,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
  Wrench,
  X,
} from 'lucide-react';
import { useMcp } from '@/api/hooks';
import { cn } from '@/utils/cn';
import type { MCPServer, MCPTool } from '@/api/types';

interface MCPSettingsPanelProps {
  readonly footer?: React.ReactNode;
}

const TRANSPORT_OPTIONS = ['stdio', 'http'] as const;

type EnvEntry = { key: string; value: string };
type StdioConfig = { command: string; args: string[]; env: EnvEntry[] };
type HttpConfig = { url: string; headers: { key: string; value: string }[] };

function parseEnv(rawEnv: unknown): EnvEntry[] {
  if (!rawEnv || typeof rawEnv !== 'object') return [];
  const entries: EnvEntry[] = [];
  for (const [k, v] of Object.entries(rawEnv)) {
    if (k && v != null) entries.push({ key: String(k), value: String(v) });
  }
  return entries;
}

function parseConfigJson(
  configJson: string,
  transport: string,
): StdioConfig | HttpConfig {
  try {
    const raw = JSON.parse(configJson.trim() || '{}');
    if (!raw || typeof raw !== 'object') return defaultConfig(transport);
    if (transport === 'stdio') {
      const args = Array.isArray(raw.args) ? raw.args.map(String) : [];
      const env = parseEnv(raw.env);
      return { command: String(raw.command ?? 'npx'), args, env };
    }
    const headers: { key: string; value: string }[] = [];
    const h = raw.headers;
    if (h && typeof h === 'object') {
      for (const [k, v] of Object.entries(h)) {
        if (k && v != null) {
          const val = typeof v === 'string' ? v : JSON.stringify(v);
          headers.push({ key: String(k), value: val });
        }
      }
    }
    return { url: String(raw.url ?? ''), headers };
  } catch {
    return defaultConfig(transport);
  }
}

function defaultConfig(transport: string): StdioConfig | HttpConfig {
  if (transport === 'stdio') {
    return {
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-filesystem', '/path'],
      env: [],
    };
  }
  return { url: '', headers: [] };
}

function normalizeTransport(transport: string): (typeof TRANSPORT_OPTIONS)[number] {
  if (transport === 'stdio' || transport === 'http') return transport;
  if (transport === 'sse' || transport === 'streamable-http') return 'http';
  return 'stdio';
}

function configToJson(config: StdioConfig | HttpConfig, transport: string): string {
  if (transport === 'stdio') {
    const c = config as StdioConfig;
    const env: Record<string, string> = {};
    for (const { key, value } of c.env) {
      if (key.trim()) env[key.trim()] = value;
    }
    return JSON.stringify({
      command: c.command,
      args: c.args.filter(Boolean),
      ...(Object.keys(env).length > 0 && { env }),
    });
  }
  const c = config as HttpConfig;
  const headers: Record<string, string> = {};
  for (const { key, value } of c.headers) {
    if (key.trim()) headers[key.trim()] = value;
  }
  return JSON.stringify({ url: c.url.trim(), headers });
}

function StdioConfigFields({
  config,
  onChange,
  idPrefix,
}: Readonly<{
  config: StdioConfig;
  onChange: (c: StdioConfig) => void;
  idPrefix: string;
}>) {
  return (
    <div className="space-y-3">
      <div>
        <label htmlFor={`${idPrefix}-command`} className="block text-xs font-medium text-gray-400 mb-1">
          Command (npx or uvx)
        </label>
        <input
          id={`${idPrefix}-command`}
          value={config.command}
          onChange={(e) => onChange({ ...config, command: e.target.value })}
          placeholder="npx"
          className="w-full px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500/50 font-mono"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">Args</label>
        <div className="space-y-2">
          {config.args.map((arg, i) => (
            <div key={`${idPrefix}-arg-${i}`} className="flex gap-2">
              <input
                value={arg}
                onChange={(e) => {
                  const next = [...config.args];
                  next[i] = e.target.value;
                  onChange({ ...config, args: next });
                }}
                placeholder={`arg ${i + 1}`}
                className="flex-1 px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500/50 font-mono"
              />
              <button
                type="button"
                onClick={() => {
                  const next = config.args.filter((_, j) => j !== i);
                  onChange({ ...config, args: next });
                }}
                className="p-2 text-gray-400 hover:text-red-400 rounded"
                aria-label="Remove arg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => onChange({ ...config, args: [...config.args, ''] })}
            className="text-xs text-cyan-400 hover:text-cyan-300"
          >
            + Add arg
          </button>
        </div>
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">Environment variables</label>
        <div className="space-y-2">
          {config.env.map((e, i) => (
            <div key={`${idPrefix}-env-${i}-${e.key || 'new'}`} className="flex gap-2">
              <input
                value={e.key}
                onChange={(ev) => {
                  const next = [...config.env];
                  next[i] = { ...next[i], key: ev.target.value };
                  onChange({ ...config, env: next });
                }}
                placeholder="VAR_NAME"
                className="w-40 px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500/50 font-mono"
              />
              <input
                value={e.value}
                onChange={(ev) => {
                  const next = [...config.env];
                  next[i] = { ...next[i], value: ev.target.value };
                  onChange({ ...config, env: next });
                }}
                placeholder="Value"
                className="flex-1 px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500/50"
              />
              <button
                type="button"
                onClick={() => {
                  const next = config.env.filter((_, j) => j !== i);
                  onChange({ ...config, env: next });
                }}
                className="p-2 text-gray-400 hover:text-red-400 rounded"
                aria-label="Remove env var"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() =>
              onChange({ ...config, env: [...config.env, { key: '', value: '' }] })
            }
            className="text-xs text-cyan-400 hover:text-cyan-300"
          >
            + Add env var
          </button>
        </div>
      </div>
    </div>
  );
}

function HttpConfigFields({
  config,
  onChange,
  idPrefix,
}: Readonly<{
  config: HttpConfig;
  onChange: (c: HttpConfig) => void;
  idPrefix: string;
}>) {
  return (
    <div className="space-y-3">
      <div>
        <label htmlFor={`${idPrefix}-url`} className="block text-xs font-medium text-gray-400 mb-1">
          URL
        </label>
        <input
          id={`${idPrefix}-url`}
          type="url"
          value={config.url}
          onChange={(e) => onChange({ ...config, url: e.target.value })}
          placeholder="https://mcp.example.com/mcp"
          className="w-full px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500/50"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">Headers</label>
        <div className="space-y-2">
          {config.headers.map((h, i) => (
            <div key={`${idPrefix}-h-${i}-${h.key || 'new'}`} className="flex gap-2">
              <input
                value={h.key}
                onChange={(e) => {
                  const next = [...config.headers];
                  next[i] = { ...next[i], key: e.target.value };
                  onChange({ ...config, headers: next });
                }}
                placeholder="Header name"
                className="w-32 px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500/50"
              />
              <input
                value={h.value}
                onChange={(e) => {
                  const next = [...config.headers];
                  next[i] = { ...next[i], value: e.target.value };
                  onChange({ ...config, headers: next });
                }}
                placeholder="Value"
                className="flex-1 px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500/50"
              />
              <button
                type="button"
                onClick={() => {
                  const next = config.headers.filter((_, j) => j !== i);
                  onChange({ ...config, headers: next });
                }}
                className="p-2 text-gray-400 hover:text-red-400 rounded"
                aria-label="Remove header"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => onChange({ ...config, headers: [...config.headers, { key: '', value: '' }] })}
            className="text-xs text-cyan-400 hover:text-cyan-300"
          >
            + Add header
          </button>
        </div>
      </div>
    </div>
  );
}

export function MCPSettingsPanel({ footer }: MCPSettingsPanelProps) {
  const {
    servers,
    loading,
    refreshing,
    error,
    createServer,
    updateServer,
    deleteServer,
    setServerEnabled,
    setToolEnabled,
    refreshTools,
  } = useMcp();

  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [addForm, setAddForm] = useState({
    name: '',
    transport: 'stdio' as (typeof TRANSPORT_OPTIONS)[number],
    config: defaultConfig('stdio') as StdioConfig | HttpConfig,
  });
  const [editForm, setEditForm] = useState<{
    name: string;
    transport: (typeof TRANSPORT_OPTIONS)[number];
    config: StdioConfig | HttpConfig;
  }>({ name: '', transport: 'stdio', config: defaultConfig('stdio') });

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const isAddConfigValid = () => {
    if (addForm.transport === 'stdio') {
      const c = addForm.config as StdioConfig;
      return !!addForm.name.trim() && !!c.command.trim();
    }
    const c = addForm.config as HttpConfig;
    return !!addForm.name.trim() && !!c.url.trim();
  };

  const handleAdd = async () => {
    setAddError(null);
    if (!isAddConfigValid()) {
      setAddError('Name and required config fields are missing');
      return;
    }
    const configJson = configToJson(addForm.config, addForm.transport);
    const res = await createServer({
      name: addForm.name.trim(),
      transport: addForm.transport,
      configJson,
    });
    if (res.ok) {
      setAdding(false);
      setAddError(null);
      setAddForm({ name: '', transport: 'stdio', config: defaultConfig('stdio') });
    }
  };

  const handleEdit = async (serverId: string) => {
    const s = servers.find((x) => x.id === serverId);
    if (!s) return;
    const configJson = configToJson(editForm.config, editForm.transport);
    const res = await updateServer(serverId, {
      name: editForm.name || undefined,
      transport: editForm.transport || undefined,
      configJson,
    });
    if (res.ok) {
      setEditingId(null);
    }
  };

  const handleDelete = async (serverId: string) => {
    if (!globalThis.confirm('Delete this MCP server? Cached tools will be removed.')) return;
    const res = await deleteServer(serverId);
    if (res.ok) {
      setEditingId(null);
      setExpandedIds((prev) => {
        const next = new Set(prev);
        next.delete(serverId);
        return next;
      });
    }
  };

  const startEdit = (s: MCPServer) => {
    setEditingId(s.id);
    const config = parseConfigJson(s.configJson, s.transport);
    setEditForm({
      name: s.name,
      transport: normalizeTransport(s.transport),
      config,
    });
  };

  const onAddTransportChange = (transport: (typeof TRANSPORT_OPTIONS)[number]) => {
    setAddForm((f) => ({
      ...f,
      transport,
      config: defaultConfig(transport),
    }));
  };

  const onEditTransportChange = (transport: (typeof TRANSPORT_OPTIONS)[number]) => {
    setEditForm((f) => ({
      ...f,
      transport,
      config: defaultConfig(transport),
    }));
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-300">MCP Servers</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => refreshTools()}
              disabled={refreshing || loading}
              className={cn(
                'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                'bg-gray-800/50 hover:bg-gray-700/50 text-gray-200 border border-gray-600/50',
                'disabled:opacity-50 disabled:cursor-not-allowed',
              )}
              title="Discover tools from all enabled servers"
            >
              {refreshing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              Refresh Tools
            </button>
            <button
              onClick={() => setAdding(true)}
              disabled={loading || adding}
              className={cn(
                'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                'bg-cyan-500 hover:bg-cyan-600 text-white',
                'disabled:opacity-50 disabled:cursor-not-allowed',
              )}
            >
              <Plus className="w-4 h-4" />
              Add Server
            </button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-lg">
            <X className="w-4 h-4 text-red-400 shrink-0" />
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        {adding && (
          <div className="p-4 bg-gray-800/30 rounded-lg border border-gray-700/50 space-y-3">
            <h4 className="text-sm font-medium text-gray-200">New MCP Server</h4>
            {addError && (
              <div className="flex items-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg">
                <X className="w-4 h-4 text-red-400 shrink-0" />
                <p className="text-sm text-red-300">{addError}</p>
              </div>
            )}
            <div>
              <label htmlFor="add-mcp-name" className="block text-xs font-medium text-gray-400 mb-1">
                Name
              </label>
              <input
                id="add-mcp-name"
                value={addForm.name}
                onChange={(e) => {
                  setAddForm((f) => ({ ...f, name: e.target.value }));
                  setAddError(null);
                }}
                placeholder="e.g. my-mcp-server"
                className="w-full px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500/50"
              />
            </div>
            <div>
              <label htmlFor="add-mcp-transport" className="block text-xs font-medium text-gray-400 mb-1">
                Transport
              </label>
              <select
                id="add-mcp-transport"
                value={addForm.transport}
                onChange={(e) => onAddTransportChange(e.target.value as (typeof TRANSPORT_OPTIONS)[number])}
                className="w-full px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 text-sm focus:outline-none focus:border-cyan-500/50"
              >
                {TRANSPORT_OPTIONS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <span className="block text-xs font-medium text-gray-400 mb-2">Config</span>
              {addForm.transport === 'stdio' ? (
                <StdioConfigFields
                  config={addForm.config as StdioConfig}
                  onChange={(c) => setAddForm((f) => ({ ...f, config: c }))}
                  idPrefix="add"
                />
              ) : (
                <HttpConfigFields
                  config={addForm.config as HttpConfig}
                  onChange={(c) => setAddForm((f) => ({ ...f, config: c }))}
                  idPrefix="add"
                />
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleAdd}
                disabled={loading || !isAddConfigValid()}
                className={cn(
                  'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium',
                  'bg-cyan-500 hover:bg-cyan-600 text-white',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                )}
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                Add
              </button>
              <button
                onClick={() => {
                  setAdding(false);
                  setAddError(null);
                }}
                className="px-3 py-2 rounded-lg text-sm font-medium border border-gray-600/50 text-gray-300 hover:bg-gray-700/50"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {loading && !servers.length ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-gray-500" />
          </div>
        ) : (
          <div className="space-y-2">
            {servers.map((server) => (
              <div
                key={server.id}
                className="border border-gray-700/50 rounded-lg overflow-hidden bg-gray-800/20"
              >
                <div className="flex items-center gap-2 px-4 py-3">
                  <button
                    onClick={() => toggleExpanded(server.id)}
                    className="p-1 text-gray-400 hover:text-gray-200 rounded"
                  >
                    {expandedIds.has(server.id) ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                  </button>
                  <div
                    className={cn(
                      'w-2.5 h-2.5 rounded-full shrink-0',
                      !server.enabled
                        ? 'bg-gray-600'
                        : server.tools.length > 0
                          ? 'bg-green-500'
                          : 'bg-amber-500',
                    )}
                    title={
                      !server.enabled
                        ? 'Disabled'
                        : server.tools.length > 0
                          ? 'Connected'
                          : 'No tools (check config or refresh)'
                    }
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-200 truncate">{server.name}</p>
                    <p className="text-xs text-gray-500">
                      {server.transport}
                      {server.lastConnectedAt && (
                        <> · Last connected {new Date(server.lastConnectedAt).toLocaleString()}</>
                      )}
                    </p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={server.enabled}
                      onChange={(e) => setServerEnabled(server.id, e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-9 h-5 bg-gray-600 peer-focus:ring-2 peer-focus:ring-cyan-500/30 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-cyan-500" />
                    <span className="ms-2 text-xs text-gray-400" aria-hidden>Enabled</span>
                  </label>
                  <button
                    onClick={() => startEdit(server)}
                    className="p-1.5 text-gray-400 hover:text-gray-200 hover:bg-gray-700/50 rounded"
                    title="Edit"
                  >
                    <Wrench className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(server.id)}
                    className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-gray-700/50 rounded"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                {editingId === server.id && (
                  <div className="px-4 pb-4 pt-0 border-t border-gray-700/30 mt-0 space-y-3">
                    <h4 className="text-xs font-medium text-gray-400 pt-3">Edit Server</h4>
                    <div>
                      <label htmlFor="edit-mcp-name" className="block text-xs text-gray-500 mb-1">
                        Name
                      </label>
                      <input
                        id="edit-mcp-name"
                        value={editForm.name}
                        onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                        className="w-full px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 text-sm"
                      />
                    </div>
                    <div>
                      <label htmlFor="edit-mcp-transport" className="block text-xs text-gray-500 mb-1">
                        Transport
                      </label>
                      <select
                        id="edit-mcp-transport"
                        value={editForm.transport}
                        onChange={(e) =>
                          onEditTransportChange(e.target.value as (typeof TRANSPORT_OPTIONS)[number])
                        }
                        className="w-full px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 text-sm"
                      >
                        {TRANSPORT_OPTIONS.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <span className="block text-xs text-gray-500 mb-2">Config</span>
                      {editForm.transport === 'stdio' ? (
                        <StdioConfigFields
                          config={editForm.config as StdioConfig}
                          onChange={(c) => setEditForm((f) => ({ ...f, config: c }))}
                          idPrefix="edit"
                        />
                      ) : (
                        <HttpConfigFields
                          config={editForm.config as HttpConfig}
                          onChange={(c) => setEditForm((f) => ({ ...f, config: c }))}
                          idPrefix="edit"
                        />
                      )}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleEdit(server.id)}
                        disabled={loading}
                        className="px-3 py-2 rounded-lg text-sm bg-cyan-500 hover:bg-cyan-600 text-white disabled:opacity-50"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="px-3 py-2 rounded-lg text-sm border border-gray-600/50 text-gray-300"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {expandedIds.has(server.id) && (
                  <div className="px-4 pb-4 border-t border-gray-700/30">
                    <h4 className="text-xs font-medium text-gray-400 pt-3 mb-2">
                      Tools ({server.tools.length})
                    </h4>
                    {server.tools.length === 0 ? (
                      <p className="text-xs text-gray-500">
                        No tools cached. Click Refresh Tools to discover.
                      </p>
                    ) : (
                      <ul className="space-y-1.5">
                        {server.tools.map((tool) => (
                          <ToolRow
                            key={tool.id}
                            tool={tool}
                            onToggle={(enabled) => setToolEnabled(tool.id, enabled)}
                          />
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {!loading && !servers.length && !adding && (
          <p className="text-sm text-gray-500 py-8 text-center">
            No MCP servers configured. Add one to connect MCP tools.
          </p>
        )}
      </div>

      {footer && (
        <div className="shrink-0 px-6 py-4 border-t border-gray-700/50 bg-gray-800/20">
          {footer}
        </div>
      )}
    </div>
  );
}

function ToolRow({
  tool,
  onToggle,
}: Readonly<{
  tool: MCPTool;
  onToggle: (enabled: boolean) => void;
}>) {
  return (
    <li className="flex items-center gap-3 py-1.5 px-2 rounded bg-gray-900/30">
      <label className="relative inline-flex items-center cursor-pointer shrink-0">
        <input
          type="checkbox"
          checked={tool.enabled}
          onChange={(e) => onToggle(e.target.checked)}
          className="sr-only peer"
          aria-label={`Enable ${tool.toolName}`}
        />
        <div className="w-7 h-4 bg-gray-600 peer-focus:ring-2 peer-focus:ring-cyan-500/30 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-cyan-500" />
      </label>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-mono text-gray-200 truncate">{tool.toolName}</p>
        {tool.description && (
          <p className="text-xs text-gray-500 truncate">{tool.description}</p>
        )}
      </div>
    </li>
  );
}
