/**
 * JurisTech OpenHands Extension - Supervisor Settings UI
 * Allows users to configure and manage supervisor AI instances.
 */

import React, { useState, useEffect } from 'react';

// Types
interface SupervisorConfig {
  id: string;
  name: string;
  supervisor_type: string;
  model_name: string;
  model_provider: string;
  model_base_url: string | null;
  api_key_env: string;
  temperature: number;
  max_tokens: number;
  system_prompt: string;
  enabled: boolean;
  priority: number;
  auto_generate_prompt: boolean;
  focus_areas: string[];
  custom_instructions: string;
  auto_send_enabled: boolean;
  auto_send_confidence_threshold: number;
  auto_send_max_consecutive: number;
  auto_send_stop_keywords: string[];
}

interface SupervisorsConfig {
  supervisors: SupervisorConfig[];
  enabled: boolean;
  show_in_panel: boolean;
  auto_insert_response: boolean;
  rag_enabled: boolean;
  rag_index_path: string;
  rag_chunk_size: number;
  rag_chunk_overlap: number;
}

interface SupervisorSettingsProps {
  config: SupervisorsConfig;
  onSave: (config: SupervisorsConfig) => void;
  onIndexCodebase?: (path: string) => Promise<void>;
}

const SUPERVISOR_TYPES = [
  { value: 'general', label: 'General', description: 'Maintains vision and goals' },
  { value: 'architecture', label: 'Architecture', description: 'Reviews code architecture' },
  { value: 'security', label: 'Security', description: 'Identifies security risks' },
  { value: 'performance', label: 'Performance', description: 'Optimizes performance' },
  { value: 'testing', label: 'Testing', description: 'Ensures test coverage' },
  { value: 'custom', label: 'Custom', description: 'User-defined supervisor' },
];

const MODEL_PROVIDERS = [
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'ollama', label: 'Ollama (Local)' },
  { value: 'openai', label: 'OpenAI' },
];

const DEFAULT_MODELS = {
  anthropic: [
    { value: 'anthropic/claude-opus-4-5-20251101', label: 'Claude Opus 4.5' },
    { value: 'anthropic/claude-sonnet-4-5-20251101', label: 'Claude Sonnet 4.5' },
  ],
  ollama: [
    { value: 'ollama/llama3', label: 'Llama 3' },
    { value: 'ollama/glm4', label: 'GLM-4' },
  ],
  openai: [
    { value: 'openai/gpt-4', label: 'GPT-4' },
    { value: 'openai/gpt-4-turbo', label: 'GPT-4 Turbo' },
  ],
};

// Generate unique ID
const generateId = () => `supervisor-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

// Default supervisor config
const createDefaultSupervisor = (type: string = 'custom'): SupervisorConfig => ({
  id: generateId(),
  name: type === 'general' ? 'General Supervisor' : `New ${type.charAt(0).toUpperCase() + type.slice(1)} Supervisor`,
  supervisor_type: type,
  model_name: 'anthropic/claude-opus-4-5-20251101',
  model_provider: 'anthropic',
  model_base_url: null,
  api_key_env: 'ANTHROPIC_API_KEY',
  temperature: 0.3,
  max_tokens: 2048,
  system_prompt: '',
  enabled: true,
  priority: type === 'general' ? 0 : 10,
  auto_generate_prompt: true,
  focus_areas: [],
  custom_instructions: '',
  auto_send_enabled: false,
  auto_send_confidence_threshold: 0.8,
  auto_send_max_consecutive: 5,
  auto_send_stop_keywords: ['delete', 'remove', 'drop', 'security', 'credential', 'password', 'production', 'deploy'],
});

export const SupervisorSettings: React.FC<SupervisorSettingsProps> = ({
  config,
  onSave,
  onIndexCodebase,
}) => {
  const [localConfig, setLocalConfig] = useState<SupervisorsConfig>(config);
  const [selectedSupervisor, setSelectedSupervisor] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editingSupervisor, setEditingSupervisor] = useState<SupervisorConfig | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [indexPath, setIndexPath] = useState('');
  const [isIndexing, setIsIndexing] = useState(false);

  useEffect(() => {
    setLocalConfig(config);
  }, [config]);

  const handleGlobalToggle = (field: keyof SupervisorsConfig, value: boolean) => {
    setLocalConfig(prev => ({ ...prev, [field]: value }));
    setIsDirty(true);
  };

  const handleAddSupervisor = (type: string) => {
    const newSupervisor = createDefaultSupervisor(type);
    setEditingSupervisor(newSupervisor);
    setIsEditing(true);
  };

  const handleEditSupervisor = (supervisor: SupervisorConfig) => {
    setEditingSupervisor({ ...supervisor });
    setIsEditing(true);
  };

  const handleDeleteSupervisor = (id: string) => {
    if (confirm('Are you sure you want to delete this supervisor?')) {
      setLocalConfig(prev => ({
        ...prev,
        supervisors: prev.supervisors.filter(s => s.id !== id),
      }));
      setIsDirty(true);
    }
  };

  const handleToggleSupervisor = (id: string) => {
    setLocalConfig(prev => ({
      ...prev,
      supervisors: prev.supervisors.map(s =>
        s.id === id ? { ...s, enabled: !s.enabled } : s
      ),
    }));
    setIsDirty(true);
  };

  const handleSaveSupervisor = () => {
    if (!editingSupervisor) return;

    setLocalConfig(prev => {
      const existingIndex = prev.supervisors.findIndex(s => s.id === editingSupervisor.id);
      if (existingIndex >= 0) {
        const updated = [...prev.supervisors];
        updated[existingIndex] = editingSupervisor;
        return { ...prev, supervisors: updated };
      } else {
        return { ...prev, supervisors: [...prev.supervisors, editingSupervisor] };
      }
    });

    setIsEditing(false);
    setEditingSupervisor(null);
    setIsDirty(true);
  };

  const handleSaveAll = () => {
    onSave(localConfig);
    setIsDirty(false);
  };

  const handleIndexCodebase = async () => {
    if (!onIndexCodebase || !indexPath) return;
    setIsIndexing(true);
    try {
      await onIndexCodebase(indexPath);
      alert('Codebase indexed successfully!');
    } catch (error) {
      alert(`Error indexing codebase: ${error}`);
    } finally {
      setIsIndexing(false);
    }
  };

  const renderSupervisorCard = (supervisor: SupervisorConfig) => {
    const typeInfo = SUPERVISOR_TYPES.find(t => t.value === supervisor.supervisor_type);
    const isGeneral = supervisor.supervisor_type === 'general';

    return (
      <div
        key={supervisor.id}
        className={`p-4 rounded-lg border ${
          supervisor.enabled
            ? 'border-blue-500 bg-gray-800'
            : 'border-gray-600 bg-gray-900 opacity-60'
        }`}
      >
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold text-white">{supervisor.name}</h3>
              {isGeneral && (
                <span className="px-2 py-0.5 text-xs bg-blue-600 text-white rounded">Primary</span>
              )}
              {supervisor.auto_send_enabled && isGeneral && (
                <span className="px-2 py-0.5 text-xs bg-green-600 text-white rounded">Auto-Send</span>
              )}
            </div>
            <p className="text-sm text-gray-400 mt-1">
              {typeInfo?.description || 'Custom supervisor'}
            </p>
            <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
              <span>Model: {supervisor.model_name.split('/').pop()}</span>
              <span>Priority: {supervisor.priority}</span>
              <span>Temp: {supervisor.temperature}</span>
            </div>
            {supervisor.focus_areas.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {supervisor.focus_areas.map((area, i) => (
                  <span key={i} className="px-2 py-0.5 text-xs bg-gray-700 text-gray-300 rounded">
                    {area}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleToggleSupervisor(supervisor.id)}
              className={`p-2 rounded ${
                supervisor.enabled ? 'bg-green-600 hover:bg-green-700' : 'bg-gray-600 hover:bg-gray-500'
              }`}
              title={supervisor.enabled ? 'Disable' : 'Enable'}
            >
              {supervisor.enabled ? 'ON' : 'OFF'}
            </button>
            <button
              onClick={() => handleEditSupervisor(supervisor)}
              className="p-2 bg-blue-600 hover:bg-blue-700 rounded text-white"
              title="Edit"
            >
              Edit
            </button>
            {!isGeneral && (
              <button
                onClick={() => handleDeleteSupervisor(supervisor.id)}
                className="p-2 bg-red-600 hover:bg-red-700 rounded text-white"
                title="Delete"
              >
                Delete
              </button>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderEditModal = () => {
    if (!isEditing || !editingSupervisor) return null;

    const isGeneral = editingSupervisor.supervisor_type === 'general';
    const providerModels = DEFAULT_MODELS[editingSupervisor.model_provider as keyof typeof DEFAULT_MODELS] || [];

    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-gray-800 rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
          <h2 className="text-xl font-bold text-white mb-4">
            {editingSupervisor.id.includes(Date.now().toString().slice(0, 8)) ? 'Add' : 'Edit'} Supervisor
          </h2>

          <div className="space-y-4">
            {/* Basic Info */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Name</label>
              <input
                type="text"
                value={editingSupervisor.name}
                onChange={e => setEditingSupervisor(prev => prev ? { ...prev, name: e.target.value } : null)}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Type</label>
              <select
                value={editingSupervisor.supervisor_type}
                onChange={e => setEditingSupervisor(prev => prev ? { ...prev, supervisor_type: e.target.value } : null)}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                disabled={isGeneral}
              >
                {SUPERVISOR_TYPES.map(type => (
                  <option key={type.value} value={type.value}>
                    {type.label} - {type.description}
                  </option>
                ))}
              </select>
            </div>

            {/* Model Configuration */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Provider</label>
                <select
                  value={editingSupervisor.model_provider}
                  onChange={e => setEditingSupervisor(prev => prev ? {
                    ...prev,
                    model_provider: e.target.value,
                    model_name: DEFAULT_MODELS[e.target.value as keyof typeof DEFAULT_MODELS]?.[0]?.value || '',
                  } : null)}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                >
                  {MODEL_PROVIDERS.map(provider => (
                    <option key={provider.value} value={provider.value}>{provider.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Model</label>
                <select
                  value={editingSupervisor.model_name}
                  onChange={e => setEditingSupervisor(prev => prev ? { ...prev, model_name: e.target.value } : null)}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                >
                  {providerModels.map(model => (
                    <option key={model.value} value={model.value}>{model.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {editingSupervisor.model_provider === 'ollama' && (
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Ollama Base URL</label>
                <input
                  type="text"
                  value={editingSupervisor.model_base_url || 'http://localhost:11434'}
                  onChange={e => setEditingSupervisor(prev => prev ? { ...prev, model_base_url: e.target.value } : null)}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                  placeholder="http://localhost:11434"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">API Key Environment Variable</label>
              <input
                type="text"
                value={editingSupervisor.api_key_env}
                onChange={e => setEditingSupervisor(prev => prev ? { ...prev, api_key_env: e.target.value } : null)}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                placeholder="ANTHROPIC_API_KEY"
              />
            </div>

            {/* Parameters */}
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Temperature: {editingSupervisor.temperature}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={editingSupervisor.temperature}
                  onChange={e => setEditingSupervisor(prev => prev ? { ...prev, temperature: parseFloat(e.target.value) } : null)}
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Max Tokens</label>
                <input
                  type="number"
                  value={editingSupervisor.max_tokens}
                  onChange={e => setEditingSupervisor(prev => prev ? { ...prev, max_tokens: parseInt(e.target.value) } : null)}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Priority</label>
                <input
                  type="number"
                  value={editingSupervisor.priority}
                  onChange={e => setEditingSupervisor(prev => prev ? { ...prev, priority: parseInt(e.target.value) } : null)}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                />
              </div>
            </div>

            {/* Focus Areas */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Focus Areas (comma-separated)</label>
              <input
                type="text"
                value={editingSupervisor.focus_areas.join(', ')}
                onChange={e => setEditingSupervisor(prev => prev ? {
                  ...prev,
                  focus_areas: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                } : null)}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                placeholder="vision alignment, goal tracking, quality assurance"
              />
            </div>

            {/* System Prompt */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-sm font-medium text-gray-300">System Prompt</label>
                <label className="flex items-center gap-2 text-sm text-gray-400">
                  <input
                    type="checkbox"
                    checked={editingSupervisor.auto_generate_prompt}
                    onChange={e => setEditingSupervisor(prev => prev ? { ...prev, auto_generate_prompt: e.target.checked } : null)}
                    className="rounded"
                  />
                  Auto-generate based on type
                </label>
              </div>
              <textarea
                value={editingSupervisor.system_prompt}
                onChange={e => setEditingSupervisor(prev => prev ? { ...prev, system_prompt: e.target.value } : null)}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white h-32"
                placeholder="Enter custom system prompt or leave empty to auto-generate..."
                disabled={editingSupervisor.auto_generate_prompt}
              />
            </div>

            {/* Custom Instructions */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Custom Instructions</label>
              <textarea
                value={editingSupervisor.custom_instructions}
                onChange={e => setEditingSupervisor(prev => prev ? { ...prev, custom_instructions: e.target.value } : null)}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white h-24"
                placeholder="Additional instructions to append to the system prompt..."
              />
            </div>

            {/* Auto-Send Settings (General Supervisor Only) */}
            {isGeneral && (
              <div className="border-t border-gray-600 pt-4 mt-4">
                <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                  Experimental: Auto-Send
                  <span className="px-2 py-0.5 text-xs bg-yellow-600 text-white rounded">EXPERIMENTAL</span>
                </h3>
                <p className="text-sm text-gray-400 mb-4">
                  When enabled, the General Supervisor can automatically approve and send responses to continue
                  the programming flow. This only triggers when ALL supervisors approve with high confidence.
                </p>

                <div className="space-y-4">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={editingSupervisor.auto_send_enabled}
                      onChange={e => setEditingSupervisor(prev => prev ? { ...prev, auto_send_enabled: e.target.checked } : null)}
                      className="rounded"
                    />
                    <span className="text-white">Enable Auto-Send</span>
                  </label>

                  {editingSupervisor.auto_send_enabled && (
                    <>
                      <div>
                        <label className="block text-sm font-medium text-gray-300 mb-1">
                          Confidence Threshold: {editingSupervisor.auto_send_confidence_threshold}
                        </label>
                        <input
                          type="range"
                          min="0.5"
                          max="1"
                          step="0.05"
                          value={editingSupervisor.auto_send_confidence_threshold}
                          onChange={e => setEditingSupervisor(prev => prev ? { ...prev, auto_send_confidence_threshold: parseFloat(e.target.value) } : null)}
                          className="w-full"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-300 mb-1">
                          Max Consecutive Auto-Sends
                        </label>
                        <input
                          type="number"
                          min="1"
                          max="20"
                          value={editingSupervisor.auto_send_max_consecutive}
                          onChange={e => setEditingSupervisor(prev => prev ? { ...prev, auto_send_max_consecutive: parseInt(e.target.value) } : null)}
                          className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-300 mb-1">
                          Stop Keywords (comma-separated)
                        </label>
                        <input
                          type="text"
                          value={editingSupervisor.auto_send_stop_keywords.join(', ')}
                          onChange={e => setEditingSupervisor(prev => prev ? {
                            ...prev,
                            auto_send_stop_keywords: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                          } : null)}
                          className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                          placeholder="delete, remove, security, production"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          Auto-send will be blocked if any of these keywords appear in the proposal
                        </p>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3 mt-6">
            <button
              onClick={() => {
                setIsEditing(false);
                setEditingSupervisor(null);
              }}
              className="px-4 py-2 bg-gray-600 hover:bg-gray-500 rounded text-white"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveSupervisor}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white"
            >
              Save Supervisor
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="p-6 bg-gray-900 text-white min-h-screen">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Supervisor AI Settings</h1>
          {isDirty && (
            <button
              onClick={handleSaveAll}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded text-white"
            >
              Save All Changes
            </button>
          )}
        </div>

        {/* Global Settings */}
        <div className="bg-gray-800 rounded-lg p-4 mb-6">
          <h2 className="text-lg font-semibold mb-4">Global Settings</h2>
          <div className="space-y-3">
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={localConfig.enabled}
                onChange={e => handleGlobalToggle('enabled', e.target.checked)}
                className="rounded"
              />
              <span>Enable Supervisor AI</span>
            </label>
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={localConfig.show_in_panel}
                onChange={e => handleGlobalToggle('show_in_panel', e.target.checked)}
                className="rounded"
              />
              <span>Show supervisor responses in separate panel</span>
            </label>
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={localConfig.auto_insert_response}
                onChange={e => handleGlobalToggle('auto_insert_response', e.target.checked)}
                className="rounded"
              />
              <span>Auto-insert supervisor response into chat (without sending)</span>
            </label>
          </div>
        </div>

        {/* RAG Settings */}
        <div className="bg-gray-800 rounded-lg p-4 mb-6">
          <h2 className="text-lg font-semibold mb-4">Codebase RAG Index</h2>
          <div className="space-y-3">
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={localConfig.rag_enabled}
                onChange={e => handleGlobalToggle('rag_enabled', e.target.checked)}
                className="rounded"
              />
              <span>Enable RAG (Retrieval Augmented Generation) for code context</span>
            </label>

            {localConfig.rag_enabled && (
              <div className="mt-4 space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">Index Path</label>
                  <input
                    type="text"
                    value={localConfig.rag_index_path}
                    onChange={e => setLocalConfig(prev => ({ ...prev, rag_index_path: e.target.value }))}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                  />
                </div>

                <div className="flex gap-4">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-300 mb-1">Chunk Size</label>
                    <input
                      type="number"
                      value={localConfig.rag_chunk_size}
                      onChange={e => setLocalConfig(prev => ({ ...prev, rag_chunk_size: parseInt(e.target.value) }))}
                      className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                    />
                  </div>
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-300 mb-1">Chunk Overlap</label>
                    <input
                      type="number"
                      value={localConfig.rag_chunk_overlap}
                      onChange={e => setLocalConfig(prev => ({ ...prev, rag_chunk_overlap: parseInt(e.target.value) }))}
                      className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                    />
                  </div>
                </div>

                <div className="flex gap-2 mt-4">
                  <input
                    type="text"
                    value={indexPath}
                    onChange={e => setIndexPath(e.target.value)}
                    className="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                    placeholder="Path to codebase directory..."
                  />
                  <button
                    onClick={handleIndexCodebase}
                    disabled={isIndexing || !indexPath}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded text-white"
                  >
                    {isIndexing ? 'Indexing...' : 'Index Codebase'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Supervisors List */}
        <div className="bg-gray-800 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Supervisors</h2>
            <div className="flex gap-2">
              {SUPERVISOR_TYPES.filter(t => t.value !== 'general').map(type => (
                <button
                  key={type.value}
                  onClick={() => handleAddSupervisor(type.value)}
                  className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm text-white"
                >
                  + {type.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            {localConfig.supervisors.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <p>No supervisors configured.</p>
                <p className="text-sm mt-2">Add a General Supervisor to get started.</p>
                <button
                  onClick={() => handleAddSupervisor('general')}
                  className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white"
                >
                  + Add General Supervisor
                </button>
              </div>
            ) : (
              localConfig.supervisors
                .sort((a, b) => a.priority - b.priority)
                .map(renderSupervisorCard)
            )}
          </div>
        </div>

        {/* Info Box */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="font-semibold mb-2">How Supervisors Work</h3>
          <ul className="text-sm text-gray-400 space-y-1">
            <li>- Supervisors review AI agent proposals before they are executed</li>
            <li>- They respond in priority order (lower number = responds first)</li>
            <li>- The General Supervisor maintains overall vision and goals</li>
            <li>- Specialized supervisors (Architecture, Security, etc.) focus on specific concerns</li>
            <li>- Auto-send (experimental) only triggers when ALL supervisors approve</li>
            <li>- RAG provides relevant code context to supervisors for better reviews</li>
          </ul>
        </div>
      </div>

      {renderEditModal()}
    </div>
  );
};

export default SupervisorSettings;
