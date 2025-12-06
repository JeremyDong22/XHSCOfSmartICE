// Washing Machine - Main data cleaning tool component
// Version: 1.5 - Changed default label count from 3 to 2
// Features: Label By with Image Analysis (cover/all images) and Text Analysis (title/title+content)
// Contains unified prompt + flexible prompt editors, and queue submission
// Previous: Split Label By into two mutually-exclusive groups; updated LabelByConfig interface

'use client';

import { useState, useMemo } from 'react';

// Types for cleaning configuration
export interface FilterByConfig {
  enabled: boolean;
  metric: 'likes' | 'collects' | 'comments';
  operator: 'gte' | 'lte' | 'gt' | 'lt';
  value: number;
}

export interface LabelByConfig {
  enabled: boolean;
  // Image group - can select one or none
  imageTarget: 'cover_image' | 'images' | null;
  // Text group - can select one or none
  textTarget: 'title' | 'content' | null;
  labelCount: number;
  labels: string[];
  prompt: string;
}

export interface CleaningConfig {
  filterBy: FilterByConfig;
  labelBy: LabelByConfig;
  unifiedPrompt: string;
}

export interface CleaningTask {
  id: string;
  files: string[];
  config: CleaningConfig;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  startedAt?: Date;
  completedAt?: Date;
  progress?: number;
  error?: string;
}

interface WashingMachineProps {
  selectedFiles: string[];
  onTaskSubmit: (task: CleaningTask) => void;
  disabled?: boolean;
}


export default function WashingMachine({
  selectedFiles,
  onTaskSubmit,
  disabled = false,
}: WashingMachineProps) {
  // Label By state
  const [labelBy, setLabelBy] = useState<LabelByConfig>({
    enabled: false,
    imageTarget: null,
    textTarget: null,
    labelCount: 2,
    labels: [],
    prompt: '',
  });

  // Unified prompt state
  const [unifiedPrompt, setUnifiedPrompt] = useState(
    'You are a content analyzer. Analyze the provided content and output your categorization in a structured JSON format with the following fields: { "label": "<category>", "confidence": <0-1>, "reasoning": "<brief explanation>" }'
  );

  // Dynamic placeholder based on labelCount
  const exampleCategories = [
    'Single Food Item',
    'Multiple Food Items',
    'Lifestyle Scene',
    'Product Shot',
    'Recipe Tutorial',
  ];

  const placeholderText = useMemo(() => {
    const categories = exampleCategories.slice(0, labelBy.labelCount);
    return `List your categories here, e.g.:\n${categories.map((cat, idx) => `${idx + 1}. ${cat}`).join('\n')}`;
  }, [labelBy.labelCount]);

  // Validation
  const hasAtLeastOneTarget = labelBy.imageTarget !== null || labelBy.textTarget !== null;
  const isValid = selectedFiles.length > 0 && labelBy.enabled && hasAtLeastOneTarget;
  const hasLabelPrompt = !labelBy.enabled || (labelBy.prompt.trim().length > 0);

  // Generate task and submit
  const handleSubmit = () => {
    if (!isValid || !hasLabelPrompt) return;

    const task: CleaningTask = {
      id: `task_${Date.now()}`,
      files: [...selectedFiles],
      config: {
        filterBy: {
          enabled: false,
          metric: 'likes',
          operator: 'gte',
          value: 0,
        },
        labelBy,
        unifiedPrompt,
      },
      status: 'queued',
    };

    onTaskSubmit(task);
  };

  return (
    <div className="bg-stone-800 rounded-xl border border-stone-700 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-stone-700">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#D97757] to-[#B85C3E] flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">2</span>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-stone-100">Data Cleaning</h3>
          </div>
        </div>

        {/* Selected files indicator */}
        <div className="mt-3 px-3 py-2 bg-stone-900 rounded-lg border border-stone-700">
          <div className="flex items-center justify-between text-sm">
            <span className="text-stone-400">Files to wash:</span>
            <span className={`font-mono ${selectedFiles.length > 0 ? 'text-emerald-400' : 'text-stone-500'}`}>
              {selectedFiles.length} selected
            </span>
          </div>
        </div>
      </div>

      {/* Main content - scrollable */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* LABEL BY Section */}
        <section>
          <div className="flex items-center gap-3 mb-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={labelBy.enabled}
                onChange={(e) => setLabelBy({ ...labelBy, enabled: e.target.checked })}
                className="flex-shrink-0"
              />
              <span className="text-sm font-medium text-stone-200">Label By</span>
            </label>
            <span className="text-xs text-stone-500">Add AI-generated labels to posts</span>
          </div>

          <div className={`p-4 bg-stone-900 rounded-lg border transition-all ${
            labelBy.enabled ? 'border-[rgba(217,119,87,0.3)]' : 'border-stone-700 opacity-50'
          }`}>
            {/* Selection indicator */}
            {labelBy.enabled && hasAtLeastOneTarget && (
              <div className="mb-4 px-3 py-2 bg-stone-800 rounded-lg border border-[rgba(217,119,87,0.2)]">
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-stone-500">Selected:</span>
                  <span className="text-[#E8A090] font-medium">
                    {[
                      labelBy.imageTarget === 'cover_image' ? 'Cover Image' :
                      labelBy.imageTarget === 'images' ? 'All Images' : null,
                      labelBy.textTarget === 'title' ? 'Title Only' :
                      labelBy.textTarget === 'content' ? 'Title + Content' : null,
                    ].filter(Boolean).join(' + ')}
                  </span>
                </div>
              </div>
            )}

            {/* Image Analysis Group */}
            <div className="mb-4">
              <label className="block text-xs text-stone-500 mb-2">Image Analysis:</label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { value: 'cover_image' as const, label: 'Cover Image' },
                  { value: 'images' as const, label: 'All Images' },
                ].map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setLabelBy({
                      ...labelBy,
                      imageTarget: labelBy.imageTarget === option.value ? null : option.value,
                    })}
                    disabled={!labelBy.enabled}
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                      labelBy.imageTarget === option.value
                        ? 'bg-[rgba(217,119,87,0.2)] text-[#E8A090] border border-[rgba(217,119,87,0.3)]'
                        : 'bg-stone-800 text-stone-400 border border-stone-700 hover:border-stone-600'
                    } disabled:opacity-50`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Text Analysis Group */}
            <div className="mb-4">
              <label className="block text-xs text-stone-500 mb-2">Text Analysis:</label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { value: 'title' as const, label: 'Title Only' },
                  { value: 'content' as const, label: 'Title + Content' },
                ].map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setLabelBy({
                      ...labelBy,
                      textTarget: labelBy.textTarget === option.value ? null : option.value,
                    })}
                    disabled={!labelBy.enabled}
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                      labelBy.textTarget === option.value
                        ? 'bg-[rgba(217,119,87,0.2)] text-[#E8A090] border border-[rgba(217,119,87,0.3)]'
                        : 'bg-stone-800 text-stone-400 border border-stone-700 hover:border-stone-600'
                    } disabled:opacity-50`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Label count */}
            <div className="mb-4">
              <label className="block text-xs text-stone-500 mb-2">
                How many labels/categories?
              </label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min={2}
                  max={5}
                  value={labelBy.labelCount}
                  onChange={(e) => setLabelBy({ ...labelBy, labelCount: parseInt(e.target.value) })}
                  disabled={!labelBy.enabled}
                  className="flex-1"
                />
                <span className="w-8 text-center font-mono text-sm text-[#E8A090]">
                  {labelBy.labelCount}
                </span>
              </div>
            </div>

            {/* Flexible Prompt */}
            <div>
              <label className="block text-xs text-stone-500 mb-2">
                Categorization Prompt
                <span className="text-stone-600 ml-2">(Define your labels and criteria)</span>
              </label>
              <textarea
                value={labelBy.prompt}
                onChange={(e) => setLabelBy({ ...labelBy, prompt: e.target.value })}
                placeholder={placeholderText}
                disabled={!labelBy.enabled}
                rows={5}
                className="w-full px-3 py-2 bg-stone-800 border border-stone-700 rounded-lg text-sm text-stone-200 placeholder:text-stone-600 resize-none disabled:opacity-50"
              />
              {labelBy.enabled && !labelBy.prompt.trim() && (
                <p className="mt-1 text-xs text-amber-400/70">
                  Please define your categorization labels and criteria
                </p>
              )}
            </div>
          </div>
        </section>

        {/* UNIFIED PROMPT Section */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-sm font-medium text-stone-200">Output Format Prompt</span>
            <span className="text-xs text-stone-500">(Controls how the LLM structures its response)</span>
          </div>

          <div className="p-4 bg-stone-900 rounded-lg border border-stone-700">
            <textarea
              value={unifiedPrompt}
              onChange={(e) => setUnifiedPrompt(e.target.value)}
              rows={4}
              className="w-full px-3 py-2 bg-stone-800 border border-stone-700 rounded-lg text-sm text-stone-200 font-mono resize-none"
            />
            <p className="mt-2 text-xs text-stone-500">
              This prompt tells the LLM how to format its output. It's prepended to all labeling requests.
            </p>
          </div>
        </section>
      </div>

      {/* Footer - Submit Button */}
      <div className="p-4 border-t border-stone-700 bg-stone-900/50">
        <button
          onClick={handleSubmit}
          disabled={!isValid || !hasLabelPrompt || disabled}
          className={`w-full py-3 rounded-lg font-medium text-sm transition-all flex items-center justify-center gap-2 ${
            isValid && hasLabelPrompt && !disabled
              ? 'bg-gradient-to-r from-[#D97757] to-[#B85C3E] text-white hover:from-[#E8886A] hover:to-[#C96D4F] shadow-lg shadow-[rgba(217,119,87,0.25)]'
              : 'bg-stone-700 text-stone-500 cursor-not-allowed'
          }`}
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 5v14M5 12h14" />
          </svg>
          Add to Wash Queue
        </button>

        {!isValid && selectedFiles.length === 0 && (
          <p className="mt-2 text-xs text-center text-stone-500">
            Select files from the left panel to begin
          </p>
        )}
        {!isValid && selectedFiles.length > 0 && !labelBy.enabled && (
          <p className="mt-2 text-xs text-center text-stone-500">
            Enable Label By to start cleaning
          </p>
        )}
        {!isValid && selectedFiles.length > 0 && labelBy.enabled && !hasAtLeastOneTarget && (
          <p className="mt-2 text-xs text-center text-stone-500">
            Select at least one analysis target (Image or Text)
          </p>
        )}
      </div>
    </div>
  );
}
