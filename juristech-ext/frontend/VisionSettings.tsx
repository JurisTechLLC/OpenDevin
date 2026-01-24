/**
 * JurisTech OpenHands Extension - Vision Settings Component
 * Settings UI for configuring image processing with Llava.
 */

import React, { useState, useEffect } from 'react';

interface VisionConfig {
  enabled: boolean;
  ollama_base_url: string;
  vision_model: string;
  max_image_size_mb: number;
  description_max_tokens: number;
  auto_process_images: boolean;
}

interface VisionSettingsProps {
  config: VisionConfig;
  onSave: (config: VisionConfig) => void;
  isLoading?: boolean;
}

export function VisionSettings({ config, onSave, isLoading }: VisionSettingsProps) {
  const [localConfig, setLocalConfig] = useState<VisionConfig>(config);
  const [isDirty, setIsDirty] = useState(false);
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [testMessage, setTestMessage] = useState('');

  useEffect(() => {
    setLocalConfig(config);
  }, [config]);

  const handleChange = (field: keyof VisionConfig, value: any) => {
    setLocalConfig(prev => ({ ...prev, [field]: value }));
    setIsDirty(true);
  };

  const handleSave = () => {
    onSave(localConfig);
    setIsDirty(false);
  };

  const testConnection = async () => {
    setTestStatus('testing');
    setTestMessage('Testing connection to Ollama...');
    
    try {
      const response = await fetch(`${localConfig.ollama_base_url}/api/tags`);
      if (response.ok) {
        const data = await response.json();
        const hasVisionModel = data.models?.some(
          (m: any) => m.name.includes(localConfig.vision_model.split(':')[0])
        );
        
        if (hasVisionModel) {
          setTestStatus('success');
          setTestMessage(`Connected! Vision model "${localConfig.vision_model}" is available.`);
        } else {
          setTestStatus('error');
          setTestMessage(`Connected to Ollama, but vision model "${localConfig.vision_model}" not found. Please pull it with: ollama pull ${localConfig.vision_model}`);
        }
      } else {
        setTestStatus('error');
        setTestMessage('Failed to connect to Ollama. Is it running?');
      }
    } catch (error) {
      setTestStatus('error');
      setTestMessage(`Connection error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  return (
    <div className="vision-settings p-4 bg-gray-800 rounded-lg">
      <h3 className="text-lg font-semibold text-white mb-4">
        Image Processing Settings
      </h3>
      
      <div className="space-y-4">
        {/* Enable/Disable Toggle */}
        <div className="flex items-center justify-between">
          <label className="text-gray-300">Enable Image Processing</label>
          <button
            onClick={() => handleChange('enabled', !localConfig.enabled)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              localConfig.enabled ? 'bg-blue-600' : 'bg-gray-600'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                localConfig.enabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {/* Auto Process Images Toggle */}
        <div className="flex items-center justify-between">
          <label className="text-gray-300">Auto-process attached images</label>
          <button
            onClick={() => handleChange('auto_process_images', !localConfig.auto_process_images)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              localConfig.auto_process_images ? 'bg-blue-600' : 'bg-gray-600'
            }`}
            disabled={!localConfig.enabled}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                localConfig.auto_process_images ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {/* Ollama Base URL */}
        <div>
          <label className="block text-gray-300 mb-1">Ollama Base URL</label>
          <input
            type="text"
            value={localConfig.ollama_base_url}
            onChange={(e) => handleChange('ollama_base_url', e.target.value)}
            className="w-full px-3 py-2 bg-gray-700 text-white rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
            placeholder="http://localhost:11434"
            disabled={!localConfig.enabled}
          />
        </div>

        {/* Vision Model */}
        <div>
          <label className="block text-gray-300 mb-1">Vision Model</label>
          <select
            value={localConfig.vision_model}
            onChange={(e) => handleChange('vision_model', e.target.value)}
            className="w-full px-3 py-2 bg-gray-700 text-white rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
            disabled={!localConfig.enabled}
          >
            <option value="llava:7b">Llava 7B</option>
            <option value="llava:13b">Llava 13B</option>
            <option value="llava:34b">Llava 34B</option>
            <option value="bakllava">BakLLaVA</option>
          </select>
          <p className="text-xs text-gray-500 mt-1">
            Llava models can understand and describe images
          </p>
        </div>

        {/* Max Image Size */}
        <div>
          <label className="block text-gray-300 mb-1">
            Max Image Size (MB): {localConfig.max_image_size_mb}
          </label>
          <input
            type="range"
            min="1"
            max="50"
            value={localConfig.max_image_size_mb}
            onChange={(e) => handleChange('max_image_size_mb', parseFloat(e.target.value))}
            className="w-full"
            disabled={!localConfig.enabled}
          />
        </div>

        {/* Description Max Tokens */}
        <div>
          <label className="block text-gray-300 mb-1">
            Description Max Tokens: {localConfig.description_max_tokens}
          </label>
          <input
            type="range"
            min="100"
            max="2000"
            step="100"
            value={localConfig.description_max_tokens}
            onChange={(e) => handleChange('description_max_tokens', parseInt(e.target.value))}
            className="w-full"
            disabled={!localConfig.enabled}
          />
        </div>

        {/* Test Connection Button */}
        <div className="pt-2">
          <button
            onClick={testConnection}
            disabled={!localConfig.enabled || testStatus === 'testing'}
            className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {testStatus === 'testing' ? 'Testing...' : 'Test Connection'}
          </button>
          
          {testMessage && (
            <p className={`mt-2 text-sm ${
              testStatus === 'success' ? 'text-green-400' :
              testStatus === 'error' ? 'text-red-400' :
              'text-gray-400'
            }`}>
              {testMessage}
            </p>
          )}
        </div>

        {/* Save Button */}
        <div className="pt-4 border-t border-gray-700">
          <button
            onClick={handleSave}
            disabled={!isDirty || isLoading}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default VisionSettings;
