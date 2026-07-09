'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { settingsService, LLMModel } from '@/services/settings.service';
import { CheckCircle2, XCircle, Loader2, Eye, EyeOff, Zap, Shield, Trash2 } from 'lucide-react';

const PROVIDERS = [
  { id: 'anthropic', name: 'Anthropic', description: 'Claude models - best for reasoning and analysis' },
  { id: 'openai', name: 'OpenAI', description: 'GPT models - versatile general purpose' },
  { id: 'gemini', name: 'Google Gemini', description: 'Gemini models - fast and cost-effective' },
];

export default function SettingsPage() {
  const [currentSettings, setCurrentSettings] = useState<{
    provider: string;
    model: string;
    api_key_hint: string;
    is_configured: boolean;
  } | null>(null);

  const [selectedProvider, setSelectedProvider] = useState('anthropic');
  const [apiKey, setApiKey] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [models, setModels] = useState<Record<string, LLMModel[]>>({});
  const [validating, setValidating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [validationResult, setValidationResult] = useState<{ valid: boolean; message: string } | null>(null);
  const [saveResult, setSaveResult] = useState<{ success: boolean; message: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    try {
      const [settings, modelsData] = await Promise.all([
        settingsService.getLLMSettings(),
        settingsService.getAvailableModels(),
      ]);

      setCurrentSettings(settings);
      setSelectedProvider(settings.provider);
      setSelectedModel(settings.model);

      if ('providers' in modelsData) {
        setModels(modelsData.providers);
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  }

  function handleProviderChange(provider: string) {
    setSelectedProvider(provider);
    setValidationResult(null);
    setSaveResult(null);
    const providerModels = models[provider] || [];
    if (providerModels.length > 0) {
      setSelectedModel(providerModels[0].id);
    }
  }

  async function handleValidate() {
    if (!apiKey.trim()) {
      setValidationResult({ valid: false, message: 'Please enter an API key' });
      return;
    }
    setValidating(true);
    setValidationResult(null);
    try {
      const result = await settingsService.validateKey({
        provider: selectedProvider,
        api_key: apiKey,
        model: selectedModel,
      });
      setValidationResult(result);
    } catch (error) {
      setValidationResult({ valid: false, message: 'Validation request failed' });
    } finally {
      setValidating(false);
    }
  }

  async function handleSave() {
    if (!apiKey.trim()) {
      setSaveResult({ success: false, message: 'Please enter an API key' });
      return;
    }
    setSaving(true);
    setSaveResult(null);
    try {
      const result = await settingsService.updateLLMSettings({
        provider: selectedProvider,
        api_key: apiKey,
        model: selectedModel,
      });
      setSaveResult({ success: true, message: result.message });
      setApiKey('');
      await loadSettings();
    } catch (error: any) {
      const msg = error?.response?.data?.detail || 'Failed to save settings';
      setSaveResult({ success: false, message: msg });
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove() {
    if (!confirm('Are you sure you want to remove the saved API key? The system will revert to .env configuration.')) return;
    setRemoving(true);
    setSaveResult(null);
    setValidationResult(null);
    try {
      const result = await settingsService.removeKey();
      setSaveResult({ success: true, message: result.message });
      setApiKey('');
      await loadSettings();
    } catch (error: any) {
      const msg = error?.response?.data?.detail || 'Failed to remove key';
      setSaveResult({ success: false, message: msg });
    } finally {
      setRemoving(false);
    }
  }

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  const providerModels = models[selectedProvider] || [];

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-gray-600 mt-1">Configure your AI provider and model preferences</p>
      </div>

      {/* Current Status */}
      <Card className="border-blue-200 bg-blue-50/50">
        <CardContent className="pt-6">
          <div className="flex items-center gap-3">
            <Zap className="w-5 h-5 text-blue-600" />
            <div>
              <p className="font-medium text-blue-900">Current Active Provider</p>
              <p className="text-sm text-blue-700 mt-0.5">
                {currentSettings?.is_configured ? (
                  <>
                    <span className="font-semibold capitalize">{currentSettings.provider}</span>
                    {' — '}
                    <span>{currentSettings.model}</span>
                    {' — '}
                    <span className="font-mono text-xs">{currentSettings.api_key_hint}</span>
                  </>
                ) : (
                  'No provider configured yet'
                )}
              </p>
            </div>
            {currentSettings?.is_configured && (
              <Badge className="ml-auto bg-green-600">Active</Badge>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Provider Selection */}
      <Card>
        <CardHeader>
          <CardTitle>LLM Provider</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {PROVIDERS.map((provider) => (
              <button
                key={provider.id}
                onClick={() => handleProviderChange(provider.id)}
                className={`p-4 border-2 rounded-xl text-left transition-all ${
                  selectedProvider === provider.id
                    ? 'border-blue-600 bg-blue-50 ring-2 ring-blue-200'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                <p className="font-semibold text-gray-900">{provider.name}</p>
                <p className="text-xs text-gray-500 mt-1">{provider.description}</p>
              </button>
            ))}
          </div>

          {/* Model Selection */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1.5">Model</label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full p-2.5 border border-gray-200 rounded-lg text-sm bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              {providerModels.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name} ({model.id})
                </option>
              ))}
            </select>
          </div>

          {/* API Key Input */}
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1.5">API Key</label>
            <div className="relative">
              <Input
                type={showKey ? 'text' : 'password'}
                placeholder={`Enter your ${PROVIDERS.find(p => p.id === selectedProvider)?.name} API key`}
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  setValidationResult(null);
                  setSaveResult(null);
                }}
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1.5 flex items-center gap-1">
              <Shield className="w-3 h-3" />
              Your API key is stored securely and never exposed in API responses
            </p>
          </div>

          {/* Validation Result */}
          {validationResult && (
            <div
              className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
                validationResult.valid
                  ? 'bg-green-50 text-green-800 border border-green-200'
                  : 'bg-red-50 text-red-800 border border-red-200'
              }`}
            >
              {validationResult.valid ? (
                <CheckCircle2 className="w-4 h-4 text-green-600" />
              ) : (
                <XCircle className="w-4 h-4 text-red-600" />
              )}
              {validationResult.message}
            </div>
          )}

          {/* Save Result */}
          {saveResult && (
            <div
              className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
                saveResult.success
                  ? 'bg-green-50 text-green-800 border border-green-200'
                  : 'bg-red-50 text-red-800 border border-red-200'
              }`}
            >
              {saveResult.success ? (
                <CheckCircle2 className="w-4 h-4 text-green-600" />
              ) : (
                <XCircle className="w-4 h-4 text-red-600" />
              )}
              {saveResult.message}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 pt-2">
            <Button
              onClick={handleValidate}
              disabled={validating || !apiKey.trim()}
              variant="outline"
              className="flex-1"
            >
              {validating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  Validating...
                </>
              ) : (
                'Validate Key'
              )}
            </Button>
            <Button
              onClick={handleSave}
              disabled={saving || !apiKey.trim()}
              className="flex-1 bg-blue-600 hover:bg-blue-700"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  Saving...
                </>
              ) : (
                'Save & Activate'
              )}
            </Button>
          </div>

          {/* Remove Key */}
          {currentSettings?.is_configured && currentSettings.api_key_hint !== 'From .env' && (
            <div className="pt-2 border-t border-gray-100">
              <Button
                onClick={handleRemove}
                disabled={removing}
                variant="outline"
                className="text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700"
              >
                {removing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Removing...
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4 mr-2" />
                    Remove Saved Key
                  </>
                )}
              </Button>
              <p className="text-xs text-gray-500 mt-1.5">
                This will remove the saved key and revert to .env configuration
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Help Section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Where to get API keys?</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 text-sm">
            <div className="flex items-start gap-3">
              <span className="font-semibold text-gray-700 w-24 shrink-0">Anthropic</span>
              <a
                href="https://console.anthropic.com/account/keys"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                console.anthropic.com/account/keys
              </a>
            </div>
            <div className="flex items-start gap-3">
              <span className="font-semibold text-gray-700 w-24 shrink-0">OpenAI</span>
              <a
                href="https://platform.openai.com/api-keys"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                platform.openai.com/api-keys
              </a>
            </div>
            <div className="flex items-start gap-3">
              <span className="font-semibold text-gray-700 w-24 shrink-0">Google</span>
              <a
                href="https://aistudio.google.com/apikey"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                aistudio.google.com/apikey
              </a>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
