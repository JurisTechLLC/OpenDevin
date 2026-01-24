/**
 * JurisTech OpenHands Extension - Models Settings Component
 * Settings UI for configuring additional coding models.
 */

import React, { useState, useEffect } from 'react';

interface ModelConfig {
  name: string;
  display_name: string;
  provider: string;
  base_url?: string;
  api_key_env?: string;
  is_vision_capable: boolean;
  is_coding_model: boolean;
  max_tokens: number;
  temperature: number;
}

interface ModelsConfig {
  models: ModelConfig[];
  default_model: string;
}

interface ModelsSettingsProps {
  config: ModelsConfig;
  onSave: (config: ModelsConfig) => void;
  isLoading?: boolean;
}

export function ModelsSettings({ config, onSave, isLoading }: ModelsSettingsProps) {
  const [localConfig, setLocalConfig] = useState<ModelsConfig>(config);
  const [isDirty, setIsDirty] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelConfig | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);

  useEffect(() => {
    setLocalConfig(config);
  }, [config]);

  const handleSetDefault = (modelName: string) => {
    setLocalConfig(prev => ({ ...prev, default_model: modelName }));
    setIsDirty(true);
  };

  const handleDeleteModel = (modelName: string) => {
    setLocalConfig(prev => ({
      ...prev,
      models: prev.models.filter(m => m.name !== modelName),
      default_model: prev.default_model === modelName ? prev.models[0]?.name || '' : prev.default_model
    }));
    setIsDirty(true);
  };

  const handleAddModel = (model: ModelConfig) => {
    setLocalConfig(prev => ({
      ...prev,
      models: [...prev.models, model]
    }));
    setIsDirty(true);
    setShowAddModal(false);
  };

  const handleUpdateModel = (updatedModel: ModelConfig) => {
    setLocalConfig(prev => ({
      ...prev,
      models: prev.models.map(m => m.name === updatedModel.name ? updatedModel : m)
    }));
    setIsDirty(true);
    setEditingModel(null);
  };

  const handleSave = () => {
    onSave(localConfig);
    setIsDirty(false);
  };

  const getProviderIcon = (provider: string) => {
    switch (provider.toLowerCase()) {
      case 'ollama':
        return '🦙';
      case 'anthropic':
        return '🤖';
      case 'openai':
        return '🧠';
      default:
        return '⚡';
    }
  };

  return (
    <div className="models-settings p-4 bg-gray-800 rounded-lg">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">
          Coding Models
        </h3>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-500"
        >
          + Add Model
        </button>
      </div>

      <div className="space-y-3">
        {localConfig.models.map((model) => (
          <div
            key={model.name}
            className={`p-3 rounded-lg border ${
              localConfig.default_model === model.name
                ? 'border-blue-500 bg-blue-900/20'
                : 'border-gray-600 bg-gray-700/50'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{getProviderIcon(model.provider)}</span>
                <div>
                  <h4 className="text-white font-medium">{model.display_name}</h4>
                  <p className="text-xs text-gray-400">{model.name}</p>
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                {model.is_vision_capable && (
                  <span className="px-2 py-0.5 bg-purple-600/50 text-purple-200 text-xs rounded">
                    Vision
                  </span>
                )}
                {model.is_coding_model && (
                  <span className="px-2 py-0.5 bg-green-600/50 text-green-200 text-xs rounded">
                    Coding
                  </span>
                )}
                
                {localConfig.default_model === model.name ? (
                  <span className="px-2 py-0.5 bg-blue-600 text-white text-xs rounded">
                    Default
                  </span>
                ) : (
                  <button
                    onClick={() => handleSetDefault(model.name)}
                    className="px-2 py-0.5 bg-gray-600 text-gray-300 text-xs rounded hover:bg-gray-500"
                  >
                    Set Default
                  </button>
                )}
                
                <button
                  onClick={() => setEditingModel(model)}
                  className="p-1 text-gray-400 hover:text-white"
                  title="Edit"
                >
                  ✏️
                </button>
                
                <button
                  onClick={() => handleDeleteModel(model.name)}
                  className="p-1 text-gray-400 hover:text-red-400"
                  title="Delete"
                >
                  🗑️
                </button>
              </div>
            </div>
            
            <div className="mt-2 text-xs text-gray-500">
              <span>Provider: {model.provider}</span>
              {model.base_url && <span className="ml-3">URL: {model.base_url}</span>}
              <span className="ml-3">Max Tokens: {model.max_tokens}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Save Button */}
      <div className="pt-4 mt-4 border-t border-gray-700">
        <button
          onClick={handleSave}
          disabled={!isDirty || isLoading}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      {/* Add/Edit Model Modal */}
      {(showAddModal || editingModel) && (
        <ModelFormModal
          model={editingModel}
          onSave={editingModel ? handleUpdateModel : handleAddModel}
          onClose={() => {
            setShowAddModal(false);
            setEditingModel(null);
          }}
        />
      )}
    </div>
  );
}

interface ModelFormModalProps {
  model: ModelConfig | null;
  onSave: (model: ModelConfig) => void;
  onClose: () => void;
}

function ModelFormModal({ model, onSave, onClose }: ModelFormModalProps) {
  const [formData, setFormData] = useState<ModelConfig>(
    model || {
      name: '',
      display_name: '',
      provider: 'ollama',
      base_url: 'http://localhost:11434',
      api_key_env: '',
      is_vision_capable: false,
      is_coding_model: true,
      max_tokens: 4096,
      temperature: 0.0
    }
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(formData);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold text-white mb-4">
          {model ? 'Edit Model' : 'Add New Model'}
        </h3>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-gray-300 mb-1">Model Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              className="w-full px-3 py-2 bg-gray-700 text-white rounded border border-gray-600"
              placeholder="ollama/codellama"
              required
              disabled={!!model}
            />
          </div>

          <div>
            <label className="block text-gray-300 mb-1">Display Name</label>
            <input
              type="text"
              value={formData.display_name}
              onChange={(e) => setFormData(prev => ({ ...prev, display_name: e.target.value }))}
              className="w-full px-3 py-2 bg-gray-700 text-white rounded border border-gray-600"
              placeholder="CodeLlama (Local)"
              required
            />
          </div>

          <div>
            <label className="block text-gray-300 mb-1">Provider</label>
            <select
              value={formData.provider}
              onChange={(e) => setFormData(prev => ({ ...prev, provider: e.target.value }))}
              className="w-full px-3 py-2 bg-gray-700 text-white rounded border border-gray-600"
            >
              <option value="ollama">Ollama (Local)</option>
              <option value="anthropic">Anthropic</option>
              <option value="openai">OpenAI</option>
              <option value="custom">Custom</option>
            </select>
          </div>

          <div>
            <label className="block text-gray-300 mb-1">Base URL</label>
            <input
              type="text"
              value={formData.base_url || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, base_url: e.target.value }))}
              className="w-full px-3 py-2 bg-gray-700 text-white rounded border border-gray-600"
              placeholder="http://localhost:11434"
            />
          </div>

          <div>
            <label className="block text-gray-300 mb-1">API Key Env Variable</label>
            <input
              type="text"
              value={formData.api_key_env || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, api_key_env: e.target.value }))}
              className="w-full px-3 py-2 bg-gray-700 text-white rounded border border-gray-600"
              placeholder="ANTHROPIC_API_KEY"
            />
          </div>

          <div>
            <label className="block text-gray-300 mb-1">Max Tokens</label>
            <input
              type="number"
              value={formData.max_tokens}
              onChange={(e) => setFormData(prev => ({ ...prev, max_tokens: parseInt(e.target.value) }))}
              className="w-full px-3 py-2 bg-gray-700 text-white rounded border border-gray-600"
              min="100"
              max="100000"
            />
          </div>

          <div className="flex gap-4">
            <label className="flex items-center gap-2 text-gray-300">
              <input
                type="checkbox"
                checked={formData.is_coding_model}
                onChange={(e) => setFormData(prev => ({ ...prev, is_coding_model: e.target.checked }))}
                className="rounded"
              />
              Coding Model
            </label>
            
            <label className="flex items-center gap-2 text-gray-300">
              <input
                type="checkbox"
                checked={formData.is_vision_capable}
                onChange={(e) => setFormData(prev => ({ ...prev, is_vision_capable: e.target.checked }))}
                className="rounded"
              />
              Vision Capable
            </label>
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-500"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-500"
            >
              {model ? 'Update' : 'Add'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default ModelsSettings;
