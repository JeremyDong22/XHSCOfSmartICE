// Washing Machine - Main data cleaning tool component
// Version: 4.7 - Updated prompt preview to use 满足/不满足 labels
// Changes: Update buildFullPrompt to match backend's 满足/不满足 label values
// Previous: v4.6 - Merge image/text analysis into single row, add likes count parameter

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
  // Include likes count in AI analysis
  includeLikes: boolean;
  userDescription: string;  // User's description of desired posts
  fullPrompt: string;  // Complete prompt sent to Gemini (for transparency)
}

export interface CleaningConfig {
  filterBy: FilterByConfig;
  labelBy: LabelByConfig;
}

export interface CleaningTask {
  id: string;
  files: string[];
  config: CleaningConfig;
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'rate_limited';
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
  // Label By state - always enabled (AI cleaning is required)
  const [labelBy, setLabelBy] = useState<LabelByConfig>({
    enabled: true,
    imageTarget: null,
    textTarget: null,
    includeLikes: false,
    userDescription: '',
    fullPrompt: '',
  });

  // Prompt preview collapse state (default: collapsed)
  const [isPromptExpanded, setIsPromptExpanded] = useState(false);

  // Build the full prompt dynamically based on user description
  // IMPORTANT: This must match EXACTLY what gemini_labeler.py sends to Gemini
  const buildFullPrompt = (userDesc: string): string => {
    return `You are a content labeler for Xiaohongshu (小红书) posts. Analyze the provided content and categorize it.

User's filter criteria: ${userDesc}

Based on this criteria, determine if the post matches (满足) or doesn't match (不满足).

Also classify the image style into one of these fixed categories:
- 特写图: Close-up shots focusing on the main subject (food, product details)
- 环境图: Environment/ambiance shots showing location, atmosphere, setting
- 拼接图: Collage or composite images combining multiple photos
- 信息图: Infographic style with text overlays, promotional content, lists

Output your analysis in this exact JSON format:
{
  "label": "<满足 or 不满足>",
  "style_label": "<特写图 or 环境图 or 拼接图 or 信息图>",
  "reasoning": "<brief explanation in Chinese>"
}`;
  };

  // Update full prompt when user description changes
  const handleUserDescriptionChange = (desc: string) => {
    setLabelBy({
      ...labelBy,
      userDescription: desc,
      fullPrompt: buildFullPrompt(desc)
    });
  };

  // Validation - labelBy.enabled is always true, no need to check
  // At least one of: image target, text target, or likes must be selected
  const hasAtLeastOneTarget = labelBy.imageTarget !== null || labelBy.textTarget !== null || labelBy.includeLikes;
  const hasUserDescription = labelBy.userDescription.trim().length > 0;
  const isValid = selectedFiles.length > 0 && hasAtLeastOneTarget && hasUserDescription;

  // Generate task and submit
  const handleSubmit = () => {
    if (!isValid) return;

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
            <h3 className="text-sm font-mono font-semibold text-stone-50 tracking-tight">数据清洗</h3>
          </div>
        </div>

        {/* Selected files indicator */}
        <div className="mt-3 px-3 py-2 bg-stone-900 rounded-lg border border-stone-700">
          <div className="flex items-center justify-between text-sm">
            <span className="text-stone-400">待清洗文件:</span>
            <span className={`font-mono text-xs ${selectedFiles.length > 0 ? 'text-emerald-400' : 'text-stone-500'}`}>
              已选 {selectedFiles.length} 个
            </span>
          </div>
        </div>
      </div>

      {/* Main content - scrollable */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* AI Cleaning Section - always enabled */}
        <section>
          <div className="flex items-center gap-3 mb-3">
            <span className="text-sm font-medium text-stone-200">AI 清洗</span>
            <span className="text-xs text-stone-500">使用 AI 分析并清洗帖子数据</span>
          </div>

          <div className="p-4 bg-stone-900 rounded-lg border border-[rgba(217,119,87,0.3)] transition-all">
            {/* Selection indicator */}
            {hasAtLeastOneTarget && (
              <div className="mb-4 px-3 py-2 bg-stone-800 rounded-lg border border-[rgba(217,119,87,0.2)]">
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-stone-500">已选择:</span>
                  <span className="text-[#E8A090] font-medium">
                    {[
                      labelBy.imageTarget === 'cover_image' ? '帖子封面' :
                      labelBy.imageTarget === 'images' ? '全部图片' : null,
                      labelBy.textTarget === 'title' ? '帖子标题' :
                      labelBy.textTarget === 'content' ? '标题 + 正文' : null,
                      labelBy.includeLikes ? '点赞数量' : null,
                    ].filter(Boolean).join(' + ')}
                  </span>
                </div>
              </div>
            )}

            {/* Combined AI Input Selection - Image, Text, and Likes in one row */}
            <div className="mb-4">
              <label className="block text-xs text-stone-500 mb-2">将以下传给AI:</label>
              <div className="flex gap-2">
                {/* Cover Image Option */}
                <button
                  onClick={() => setLabelBy({
                    ...labelBy,
                    imageTarget: labelBy.imageTarget === 'cover_image' ? null : 'cover_image',
                  })}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                    labelBy.imageTarget === 'cover_image'
                      ? 'bg-[rgba(217,119,87,0.2)] text-[#E8A090] border border-[rgba(217,119,87,0.3)]'
                      : 'bg-stone-800 text-stone-400 border border-stone-700 hover:border-stone-600'
                  }`}
                >
                  帖子封面
                </button>
                {/* Title Option */}
                <button
                  onClick={() => setLabelBy({
                    ...labelBy,
                    textTarget: labelBy.textTarget === 'title' ? null : 'title',
                  })}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                    labelBy.textTarget === 'title'
                      ? 'bg-[rgba(217,119,87,0.2)] text-[#E8A090] border border-[rgba(217,119,87,0.3)]'
                      : 'bg-stone-800 text-stone-400 border border-stone-700 hover:border-stone-600'
                  }`}
                >
                  帖子标题
                </button>
                {/* Likes Count Option */}
                <button
                  onClick={() => setLabelBy({
                    ...labelBy,
                    includeLikes: !labelBy.includeLikes,
                  })}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                    labelBy.includeLikes
                      ? 'bg-[rgba(217,119,87,0.2)] text-[#E8A090] border border-[rgba(217,119,87,0.3)]'
                      : 'bg-stone-800 text-stone-400 border border-stone-700 hover:border-stone-600'
                  }`}
                >
                  点赞数量
                </button>
              </div>
            </div>

            {/* User Description Input */}
            <div>
              <label className="block text-xs text-stone-500 mb-2">
                请描述你想清洗出来的帖子特征
              </label>
              <textarea
                value={labelBy.userDescription}
                onChange={(e) => handleUserDescriptionChange(e.target.value)}
                rows={3}
                placeholder="例如：图片中只有一份甜品的帖子"
                className={`w-full px-3 py-2 bg-stone-800 border rounded-lg text-sm text-stone-200 placeholder:text-stone-600 transition-colors resize-none ${
                  hasUserDescription
                    ? 'border-[rgba(16,185,129,0.3)]'
                    : 'border-stone-700'
                }`}
              />
              {!hasUserDescription && (
                <p className="mt-2 text-xs text-amber-400/70">
                  请输入帖子特征描述
                </p>
              )}
            </div>
          </div>
        </section>

        {/* Debug: Prompt preview */}
        {hasUserDescription && (
          <section className="-mt-2">
            <button
              onClick={() => setIsPromptExpanded(!isPromptExpanded)}
              className="w-full mb-1 text-left"
            >
              <span className="text-xs text-stone-600">
                &gt; {isPromptExpanded ? '收起提示词' : '查看完整提示词'}
              </span>
            </button>

            {/* Expandable content with smooth transition */}
            <div
              className={`overflow-hidden transition-all duration-300 ease-in-out ${
                isPromptExpanded ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0'
              }`}
            >
              <div className="p-4 bg-stone-900/30 rounded border border-stone-700/30">
                <pre className="text-xs text-stone-400 font-mono whitespace-pre-wrap max-h-[300px] overflow-y-auto leading-relaxed">
                  {labelBy.fullPrompt}
                </pre>
                <div className="mt-3 pt-3 border-t border-stone-700/30">
                  <p className="text-xs text-stone-500">
                    <span className="text-stone-600">输出格式:</span>{' '}
                    <span className="text-stone-500 font-mono">label</span> (满足/不满足) + {' '}
                    <span className="text-stone-500 font-mono">style_label</span> (特写图/环境图/拼接图/信息图) + {' '}
                    <span className="text-stone-500 font-mono">reasoning</span> (中文解释)
                  </p>
                </div>
              </div>
            </div>
          </section>
        )}
      </div>

      {/* Footer - Submit Button */}
      <div className="p-4 border-t border-stone-700 bg-stone-900/50">
        <button
          onClick={handleSubmit}
          disabled={!isValid || disabled}
          className={`w-full py-3 rounded-lg font-medium text-sm transition-all flex items-center justify-center gap-2 ${
            isValid && !disabled
              ? 'bg-gradient-to-r from-[#D97757] to-[#B85C3E] text-white hover:from-[#E8886A] hover:to-[#C96D4F] shadow-lg shadow-[rgba(217,119,87,0.25)]'
              : 'bg-stone-700 text-stone-500 cursor-not-allowed'
          }`}
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 5v14M5 12h14" />
          </svg>
          添加到清洗队列
        </button>

        {!isValid && selectedFiles.length === 0 && (
          <p className="mt-2 text-xs text-center text-stone-500">
            请从左侧面板选择文件
          </p>
        )}
        {!isValid && selectedFiles.length > 0 && !hasAtLeastOneTarget && (
          <p className="mt-2 text-xs text-center text-stone-500">
            请至少选择一项传给AI（封面、标题或点赞数量）
          </p>
        )}
        {!isValid && selectedFiles.length > 0 && hasAtLeastOneTarget && !hasUserDescription && (
          <p className="mt-2 text-xs text-center text-amber-400/70">
            请描述你想筛选的帖子特征
          </p>
        )}
      </div>
    </div>
  );
}
