import { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import { Search, Check, Cpu, Star, ArrowUpDown, GripVertical } from 'lucide-react';
import { cn } from '../utils/cn';
import { Modal } from './Modal';

interface EnhancedModelPickerProps {
  visible: boolean;
  onClose: () => void;
  currentModel: string;
  currentModelProvider?: string | null;
  currentModelKey?: string | null;
  modelsByProvider: Record<string, string[]>;
  modelMetadataByKey: Record<string, { contextLimit?: number; pricePerMillion?: number }>;
  loading: boolean;
  changeModel: (selection: {
    model: string;
    provider?: string;
    modelKey?: string;
  }) => Promise<{ ok: boolean }>;
}

interface ModelInfo {
  key: string;
  provider: string;
  label: string;
  contextLimit?: number;
  pricePerMillion?: number;
}

const PROVIDER_TABS = [
  { id: 'openrouter', label: 'OpenRouter' },
  { id: 'groq', label: 'Groq' },
  { id: 'openai-sub', label: 'OpenAI Sub' },
] as const;

function normalizeForSearch(s: string): string {
  return s.toLowerCase().replaceAll(/[-_.\s]/g, '');
}

function toModelKey(provider: string, label: string): string {
  return `${provider}::${label}`;
}

function parseProviderFromModelKey(modelKey: string): string | null {
  const idx = modelKey.indexOf('::');
  if (idx <= 0) return null;
  return modelKey.slice(0, idx);
}

function arrayEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

// Format context limit for display
function formatContextLimit(limit: number | undefined): string {
  if (!limit) return '—';
  if (limit >= 1_000_000) return `${(limit / 1_000_000).toFixed(1)}M`;
  if (limit >= 1000) return `${(limit / 1000).toFixed(0)}K`;
  return `${limit}`;
}

function formatPrice(price: number | undefined): string {
  if (price == null || price === 0) return '—';
  if (price < 0.01) return `$${price.toFixed(4)}`;
  return `$${price.toFixed(2)}`;
}

const SORT_OPTIONS = ['name', 'context', 'price'] as const;
type SortOption = (typeof SORT_OPTIONS)[number];

export function EnhancedModelPicker({
  visible,
  onClose,
  currentModel,
  currentModelProvider,
  currentModelKey,
  modelsByProvider,
  modelMetadataByKey,
  loading,
  changeModel,
}: EnhancedModelPickerProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<SortOption>('name');
  const [favoritesOrder, setFavoritesOrder] = useState<string[]>([]);
  const [groupByProvider, setGroupByProvider] = useState(false);
  const [activeTab, setActiveTab] = useState<string>(PROVIDER_TABS[0].id);
  const [changingModel, setChangingModel] = useState(false);
  const [draggedFavorite, setDraggedFavorite] = useState<string | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Build models per provider with metadata from API
  const modelsByProviderWithInfo = useMemo<Record<string, ModelInfo[]>>(() => {
    const result: Record<string, ModelInfo[]> = {};
    for (const tab of PROVIDER_TABS) {
      const labels = modelsByProvider[tab.id] ?? [];
      result[tab.id] = labels.map((label) => {
        const key = toModelKey(tab.id, label);
        const meta = modelMetadataByKey[key];
        return {
          key,
          provider: tab.id,
          label,
          contextLimit:
            meta?.contextLimit ??
            (label.includes('200k') ? 200_000 : label.includes('128k') ? 128_000 : undefined),
          pricePerMillion: meta?.pricePerMillion ?? undefined,
        };
      });
    }
    return result;
  }, [modelsByProvider, modelMetadataByKey]);

  // Flat maps for quick lookups
  const allModelsMap = useMemo<Record<string, ModelInfo>>(() => {
    const map: Record<string, ModelInfo> = {};
    for (const arr of Object.values(modelsByProviderWithInfo)) {
      for (const model of arr) map[model.key] = model;
    }
    return map;
  }, [modelsByProviderWithInfo]);

  const modelKeysByLabel = useMemo<Record<string, string[]>>(() => {
    const map: Record<string, string[]> = {};
    for (const arr of Object.values(modelsByProviderWithInfo)) {
      for (const model of arr) {
        if (!map[model.label]) map[model.label] = [];
        map[model.label].push(model.key);
      }
    }
    return map;
  }, [modelsByProviderWithInfo]);

  const hasAnyModels = Object.keys(allModelsMap).length > 0;

  const currentSelectionKey = useMemo(() => {
    if (currentModelKey && allModelsMap[currentModelKey]) return currentModelKey;
    const matches = modelKeysByLabel[currentModel] ?? [];
    if (matches.length === 0) return null;
    if (matches.length === 1) return matches[0];
    if (currentModelProvider) {
      const match = matches.find((key) => parseProviderFromModelKey(key) === currentModelProvider);
      if (match) return match;
    }
    for (const tab of PROVIDER_TABS) {
      const match = matches.find((key) => parseProviderFromModelKey(key) === tab.id);
      if (match) return match;
    }
    return matches[0];
  }, [allModelsMap, currentModel, currentModelKey, currentModelProvider, modelKeysByLabel]);

  const canonicalizeFavoriteOrder = useCallback(
    (rawOrder: string[]): string[] => {
      const normalized: string[] = [];
      const seen = new Set<string>();

      for (const value of rawOrder) {
        let key: string | null = null;
        if (allModelsMap[value]) {
          key = value;
        } else {
          const matches = modelKeysByLabel[value] ?? [];
          if (matches.length === 1) {
            key = matches[0];
          } else if (matches.length > 1) {
            for (const tab of PROVIDER_TABS) {
              const match = matches.find((candidate) => parseProviderFromModelKey(candidate) === tab.id);
              if (match) {
                key = match;
                break;
              }
            }
          }
        }

        if (key && !seen.has(key)) {
          seen.add(key);
          normalized.push(key);
        }
      }
      return normalized;
    },
    [allModelsMap, modelKeysByLabel],
  );

  const canonicalFavoritesOrder = useMemo(() => {
    return canonicalizeFavoriteOrder(favoritesOrder);
  }, [favoritesOrder, canonicalizeFavoriteOrder]);

  const favorites = useMemo(() => new Set(canonicalFavoritesOrder), [canonicalFavoritesOrder]);

  // Load favorites and groupByProvider from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('model-favorites');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setFavoritesOrder(Array.isArray(parsed) ? parsed : []);
      } catch {
        // Ignore invalid data
      }
    }
    const groupSaved = localStorage.getItem('model-favorites-group-by-provider');
    if (groupSaved === 'true') setGroupByProvider(true);
  }, []);

  // Migrate legacy label-only favorites to stable model keys once catalog is available.
  useEffect(() => {
    if (!hasAnyModels) return;
    if (!arrayEqual(favoritesOrder, canonicalFavoritesOrder)) {
      localStorage.setItem('model-favorites', JSON.stringify(canonicalFavoritesOrder));
      setFavoritesOrder(canonicalFavoritesOrder);
    }
  }, [hasAnyModels, favoritesOrder, canonicalFavoritesOrder]);

  const persistFavorites = (order: string[]) => {
    localStorage.setItem('model-favorites', JSON.stringify(order));
  };

  const toggleFavorite = (modelKey: string) => {
    setFavoritesOrder((prevRaw) => {
      const prev = canonicalizeFavoriteOrder(prevRaw);
      const next = prev.includes(modelKey)
        ? prev.filter((key) => key !== modelKey)
        : [...prev, modelKey];
      persistFavorites(next);
      return next;
    });
  };

  const reorderFavorites = (draggedKey: string, dropTargetKey: string) => {
    if (draggedKey === dropTargetKey) return;
    setFavoritesOrder((prevRaw) => {
      const prev = canonicalizeFavoriteOrder(prevRaw);
      const fromIdx = prev.indexOf(draggedKey);
      const toIdx = prev.indexOf(dropTargetKey);
      if (fromIdx < 0 || toIdx < 0 || fromIdx === toIdx) return prev;
      const next = prev.filter((key) => key !== draggedKey);
      const newToIdx = next.indexOf(dropTargetKey);
      if (newToIdx < 0) return prev;
      next.splice(newToIdx, 0, draggedKey);
      persistFavorites(next);
      return next;
    });
  };

  // Focus search input when modal becomes visible
  useEffect(() => {
    if (visible) searchInputRef.current?.focus();
  }, [visible]);

  // Favorites list for sidebar: ordered, only models that exist, optionally grouped
  const favoritesForSidebar = useMemo(() => {
    const ordered = canonicalFavoritesOrder.filter((key) => allModelsMap[key]);
    if (!groupByProvider) return [{ provider: null as string | null, models: ordered }];
    const byProvider: Record<string, string[]> = {};
    for (const key of ordered) {
      const model = allModelsMap[key];
      if (!model) continue;
      if (!byProvider[model.provider]) byProvider[model.provider] = [];
      byProvider[model.provider].push(key);
    }
    return PROVIDER_TABS.map((tab) => ({
      provider: tab.id,
      models: byProvider[tab.id] ?? [],
    })).filter((group) => group.models.length > 0);
  }, [canonicalFavoritesOrder, allModelsMap, groupByProvider]);

  // Filter and sort models for the active tab
  const filteredModels = useMemo(() => {
    const models = modelsByProviderWithInfo[activeTab] ?? [];
    let filtered = models;

    if (searchQuery.trim()) {
      const normQuery = normalizeForSearch(searchQuery);
      filtered = filtered.filter((model) => normalizeForSearch(model.label).includes(normQuery));
    }

    filtered = [...filtered].sort((a, b) => {
      const aFav = favorites.has(a.key);
      const bFav = favorites.has(b.key);
      if (aFav && !bFav) return -1;
      if (!aFav && bFav) return 1;
      if (aFav && bFav) {
        const ai = canonicalFavoritesOrder.indexOf(a.key);
        const bi = canonicalFavoritesOrder.indexOf(b.key);
        return ai - bi;
      }

      if (sortBy === 'context') {
        const aCtx = a.contextLimit ?? 0;
        const bCtx = b.contextLimit ?? 0;
        if (aCtx !== bCtx) return bCtx - aCtx;
      } else if (sortBy === 'price') {
        const aPrice = a.pricePerMillion ?? Infinity;
        const bPrice = b.pricePerMillion ?? Infinity;
        if (aPrice !== bPrice) return aPrice - bPrice;
      }
      return a.label.localeCompare(b.label);
    });

    return filtered;
  }, [
    activeTab,
    canonicalFavoritesOrder,
    favorites,
    modelsByProviderWithInfo,
    searchQuery,
    sortBy,
  ]);

  const totalModelCount = useMemo(() => {
    return Object.values(modelsByProviderWithInfo).reduce((sum, arr) => sum + arr.length, 0);
  }, [modelsByProviderWithInfo]);

  const handleSelectModel = async (model: ModelInfo) => {
    if (model.key === currentSelectionKey) {
      onClose();
      return;
    }

    setChangingModel(true);
    try {
      await changeModel({
        model: model.label,
        provider: model.provider,
        modelKey: model.key,
      });
      onClose();
    } catch (error) {
      console.error('Failed to change model:', error);
    } finally {
      setChangingModel(false);
    }
  };

  const hasResults = filteredModels.length > 0;
  const hasFavorites = canonicalFavoritesOrder.length > 0;

  const handleGroupByProviderToggle = () => {
    setGroupByProvider((prev) => {
      const next = !prev;
      localStorage.setItem('model-favorites-group-by-provider', String(next));
      return next;
    });
  };

  return (
    <Modal
      visible={visible}
      onClose={onClose}
      loading={loading}
      loadingLabel="Loading models..."
      title="Select Model"
      subtitle={`${totalModelCount} model${totalModelCount !== 1 ? 's' : ''} across ${PROVIDER_TABS.length} provider${PROVIDER_TABS.length !== 1 ? 's' : ''}`}
      icon={<Cpu className="w-5 h-5 text-cyan-400" />}
      maxWidth={hasFavorites ? 'max-w-4xl' : 'max-w-3xl'}
      footer={
        <p className="text-xs text-gray-400">
          Press <kbd className="px-1.5 py-0.5 bg-gray-700/50 rounded border border-gray-600/50">Esc</kbd> to close
        </p>
      }
    >
      <div className="flex flex-1 min-h-0">
        {/* Favorites Sidebar */}
        {hasFavorites && (
          <div className="flex flex-col w-56 shrink-0 border-r border-gray-700/50 bg-gray-900/30">
            <div className="px-3 py-2.5 border-b border-gray-700/50 flex items-center justify-between shrink-0">
              <span className="text-xs font-medium text-amber-400 flex items-center gap-1.5">
                <Star className="w-3.5 h-3.5 fill-current" />
                Favorites
              </span>
              <label htmlFor="favorites-group-toggle" className="flex items-center gap-1.5 cursor-pointer" title="Group by provider">
                <span className="text-[10px] text-gray-500">Group</span>
                <button
                  id="favorites-group-toggle"
                  type="button"
                  role="switch"
                  aria-checked={groupByProvider}
                  onClick={handleGroupByProviderToggle}
                  className={cn(
                    'w-7 h-3.5 rounded-full transition-colors',
                    groupByProvider ? 'bg-cyan-500/60' : 'bg-gray-600',
                  )}
                >
                  <span
                    className={cn(
                      'block w-2.5 h-2.5 rounded-full bg-white/90 transform transition-transform',
                      groupByProvider ? 'translate-x-3.5' : 'translate-x-0.5',
                    )}
                  />
                </button>
              </label>
            </div>
            <div className="flex-1 overflow-y-auto py-2 min-h-0">
              {favoritesForSidebar.map((group) => (
                <div key={group.provider ?? 'all'} className="mb-2 last:mb-0">
                  {groupByProvider && group.provider && (
                    <div className="px-3 py-1 text-[10px] font-medium text-gray-500 uppercase tracking-wider">
                      {PROVIDER_TABS.find((tab) => tab.id === group.provider)?.label ?? group.provider}
                    </div>
                  )}
                  {group.models.map((modelKey) => {
                    const model = allModelsMap[modelKey];
                    if (!model) return null;
                    const isActive = model.key === currentSelectionKey;

                    return (
                      <div
                        key={model.key}
                        draggable
                        onDragStart={() => setDraggedFavorite(model.key)}
                        onDragEnd={() => setDraggedFavorite(null)}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => {
                          e.preventDefault();
                          if (draggedFavorite && draggedFavorite !== model.key) {
                            reorderFavorites(draggedFavorite, model.key);
                          }
                          setDraggedFavorite(null);
                        }}
                        className={cn(
                          'flex items-center gap-1.5 px-3 py-2 mx-1 rounded-md cursor-pointer group/fav transition-colors',
                          isActive ? 'bg-cyan-500/20' : 'hover:bg-gray-700/50',
                          draggedFavorite === model.key && 'opacity-50',
                        )}
                        onClick={() => !changingModel && handleSelectModel(model)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            if (!changingModel) handleSelectModel(model);
                          }
                        }}
                      >
                        <GripVertical
                          className="w-3 h-3 text-gray-500 shrink-0 cursor-grab active:cursor-grabbing opacity-0 group-hover/fav:opacity-100"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium truncate text-gray-200">{model.label}</p>
                          {(model.contextLimit != null || model.pricePerMillion != null) && (
                            <p className="text-[10px] text-gray-500 truncate">
                              {formatContextLimit(model.contextLimit)}
                              {model.pricePerMillion != null && ` · ${formatPrice(model.pricePerMillion)}/M`}
                            </p>
                          )}
                        </div>
                        {isActive && <Check className="w-3.5 h-3.5 text-cyan-400 shrink-0" />}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Main Content */}
        <div className="flex flex-col flex-1 min-h-0 min-w-0">
          {/* Provider Tabs */}
          <div className="flex gap-1 px-6 pt-4 border-b border-gray-700/50 shrink-0">
            {PROVIDER_TABS.map((tab) => {
              const count = (modelsByProviderWithInfo[tab.id] ?? []).length;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    'px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors',
                    activeTab === tab.id
                      ? 'bg-gray-800/80 text-cyan-400 border-b-2 border-cyan-500 -mb-px'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50',
                  )}
                >
                  {tab.label}
                  <span className="ml-2 text-xs text-gray-500">({count})</span>
                </button>
              );
            })}
          </div>

          {/* Search and Sort */}
          <div className="px-6 py-4 border-b border-gray-700/50 space-y-3 shrink-0">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search models..."
                className="w-full pl-10 pr-4 py-2.5 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30"
              />
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  const idx = SORT_OPTIONS.indexOf(sortBy);
                  setSortBy(SORT_OPTIONS[(idx + 1) % SORT_OPTIONS.length]);
                }}
                className="flex items-center gap-2 px-3 py-1.5 bg-gray-800/50 hover:bg-gray-700/50 border border-gray-700/30 rounded-lg text-sm text-gray-300 transition-colors"
              >
                <ArrowUpDown className="w-3.5 h-3.5" />
                Sort by: {sortBy === 'name' ? 'Name' : sortBy === 'context' ? 'Context' : 'Price'}
              </button>
              {favorites.size > 0 && (
                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded-lg text-sm text-amber-300">
                  <Star className="w-3.5 h-3.5 fill-current" />
                  {favorites.size} favorite{favorites.size !== 1 ? 's' : ''}
                </div>
              )}
            </div>
          </div>

          {/* Model List */}
          <div className="flex-1 overflow-y-auto px-6 py-4 min-h-0">
            {!hasResults ? (
              <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                {searchQuery ? (
                  <>
                    <Search className="w-12 h-12 mb-3 opacity-50" />
                    <p className="text-sm">No models found</p>
                    <button
                      onClick={() => setSearchQuery('')}
                      className="mt-2 text-xs text-cyan-400 hover:text-cyan-300"
                    >
                      Clear search
                    </button>
                  </>
                ) : (
                  <>
                    <Cpu className="w-12 h-12 mb-3 opacity-50" />
                    <p className="text-sm">
                      {PROVIDER_TABS.find((tab) => tab.id === activeTab)?.label} has no models configured
                    </p>
                    <p className="text-xs mt-1">Add an API key in Provider Settings to sync models</p>
                  </>
                )}
              </div>
            ) : (
              <div className="space-y-1">
                {filteredModels.map((model) => {
                  const isActive = model.key === currentSelectionKey;
                  const isFavorite = favorites.has(model.key);

                  return (
                    <div
                      key={model.key}
                      role="button"
                      tabIndex={0}
                      onClick={() => !changingModel && handleSelectModel(model)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          if (!changingModel) handleSelectModel(model);
                        }
                      }}
                      className={cn(
                        'w-full flex items-center justify-between px-4 py-3 rounded-lg transition-colors group cursor-pointer',
                        isActive
                          ? 'bg-cyan-500/20 border border-cyan-500/30'
                          : 'bg-gray-800/30 hover:bg-gray-700/50 border border-transparent',
                        changingModel && 'opacity-50 cursor-not-allowed',
                      )}
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <span
                          role="button"
                          tabIndex={0}
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleFavorite(model.key);
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              e.stopPropagation();
                              toggleFavorite(model.key);
                            }
                          }}
                          className={cn(
                            'p-1 rounded transition-colors shrink-0',
                            isFavorite
                              ? 'text-amber-400 hover:text-amber-300'
                              : 'text-gray-500 hover:text-gray-400 opacity-0 group-hover:opacity-100',
                          )}
                        >
                          <Star className={cn('w-4 h-4', isFavorite && 'fill-current')} />
                        </span>

                        <div className="flex-1 min-w-0 text-left">
                          <p
                            className={cn(
                              'text-sm font-medium truncate',
                              isActive ? 'text-cyan-300' : 'text-gray-200',
                            )}
                          >
                            {model.label}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 shrink-0">
                        {model.contextLimit != null && (
                          <span className="text-xs text-gray-400 bg-gray-900/50 px-2 py-1 rounded border border-gray-700/30 font-mono">
                            {formatContextLimit(model.contextLimit)}
                          </span>
                        )}
                        {model.pricePerMillion != null && (
                          <span className="text-xs text-gray-400 bg-gray-900/50 px-2 py-1 rounded border border-gray-700/30">
                            {formatPrice(model.pricePerMillion)}/M
                          </span>
                        )}
                        {isActive && (
                          <div className="flex items-center justify-center w-5 h-5 bg-cyan-500 rounded-full">
                            <Check className="w-3.5 h-3.5 text-white" />
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}
