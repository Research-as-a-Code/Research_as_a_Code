// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Strategy Selector Component
 * 
 * Allows users to select multiple research strategies for side-by-side comparison.
 * Supports UDR, TTD-DR, and future strategies.
 */

"use client";

import React from 'react';
import { Code2, Sparkles, Zap, Clock, DollarSign, Target, Check } from 'lucide-react';

export type ResearchStrategy = 'udr' | 'ttd_dr';

export const STRATEGY_CONFIG: Record<ResearchStrategy, {
  name: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  bgColor: string;
  borderColor: string;
  features: { icon: React.ComponentType<{ className?: string }>; iconColor: string; text: string }[];
  source: string;
}> = {
  udr: {
    name: 'UDR',
    description: 'Strategy-as-Code',
    icon: Code2,
    color: 'text-green-400',
    bgColor: 'bg-green-500/10',
    borderColor: 'border-green-500',
    source: 'NVIDIA',
    features: [
      { icon: Zap, iconColor: 'text-yellow-500', text: '10-30s' },
      { icon: DollarSign, iconColor: 'text-green-500', text: 'Lower cost' },
    ],
  },
  ttd_dr: {
    name: 'TTD-DR',
    description: 'Iterative Refinement',
    icon: Sparkles,
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500',
    source: 'Google',
    features: [
      { icon: Clock, iconColor: 'text-orange-500', text: '45-90s' },
      { icon: Target, iconColor: 'text-blue-500', text: 'Best quality' },
    ],
  },
};

interface StrategySelectorProps {
  selectedStrategies: ResearchStrategy[];
  onChange: (strategies: ResearchStrategy[]) => void;
  disabled?: boolean;
}

export function StrategySelector({ 
  selectedStrategies, 
  onChange, 
  disabled = false 
}: StrategySelectorProps) {
  
  const toggleStrategy = (strategy: ResearchStrategy) => {
    if (disabled) return;
    
    if (selectedStrategies.includes(strategy)) {
      // Don't allow deselecting if it's the last one
      if (selectedStrategies.length > 1) {
        onChange(selectedStrategies.filter(s => s !== strategy));
      }
    } else {
      onChange([...selectedStrategies, strategy]);
    }
  };

  const selectAll = () => {
    if (disabled) return;
    onChange(Object.keys(STRATEGY_CONFIG) as ResearchStrategy[]);
  };

  const allStrategies = Object.keys(STRATEGY_CONFIG) as ResearchStrategy[];
  const allSelected = allStrategies.every(s => selectedStrategies.includes(s));
  
  return (
    <div className="bg-gray-900/50 backdrop-blur-lg rounded-xl p-6 border border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-100">
          Research Strategies
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={selectAll}
            disabled={disabled || allSelected}
            className={`
              text-xs px-3 py-1.5 rounded-lg transition-all
              ${allSelected 
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed' 
                : 'bg-purple-600 hover:bg-purple-700 text-white cursor-pointer'}
              ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            Compare All
          </button>
          <span className="px-2 py-1 bg-gray-800 rounded text-xs text-gray-400">
            {selectedStrategies.length} selected
          </span>
        </div>
      </div>
      
      <div className="grid grid-cols-2 gap-3">
        {allStrategies.map((strategy) => {
          const config = STRATEGY_CONFIG[strategy];
          const isSelected = selectedStrategies.includes(strategy);
          const Icon = config.icon;
          
          return (
            <button
              key={strategy}
              onClick={() => toggleStrategy(strategy)}
              disabled={disabled}
              className={`
                relative p-4 rounded-lg border-2 transition-all duration-200 text-left
                ${isSelected 
                  ? `${config.borderColor} ${config.bgColor} shadow-lg` 
                  : 'border-gray-700 hover:border-gray-600 bg-gray-800/50'}
                ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
              `}
            >
              {/* Checkbox indicator */}
              <div className={`
                absolute top-3 right-3 w-5 h-5 rounded border-2 flex items-center justify-center transition-all
                ${isSelected 
                  ? `${config.borderColor} ${config.bgColor}` 
                  : 'border-gray-600 bg-gray-800'}
              `}>
                {isSelected && <Check className={`w-3 h-3 ${config.color}`} />}
              </div>
              
              <div className="flex flex-col">
                <div className={`mb-2 p-2 rounded-lg w-fit ${
                  isSelected ? config.bgColor.replace('/10', '/20') : 'bg-gray-700/50'
                }`}>
                  <Icon className={`w-6 h-6 ${
                    isSelected ? config.color : 'text-gray-400'
                  }`} />
                </div>
                
                <h4 className="font-semibold text-gray-100 text-sm mb-0.5">{config.name}</h4>
                <p className="text-[10px] text-gray-400 mb-2">
                  {config.description}
                </p>
                
                <div className="space-y-1">
                  {config.features.map((feature, idx) => {
                    const FeatureIcon = feature.icon;
                    return (
                      <div key={idx} className="flex items-center gap-1.5 text-[10px]">
                        <FeatureIcon className={`w-3 h-3 ${feature.iconColor}`} />
                        <span className="text-gray-400">{feature.text}</span>
                      </div>
                    );
                  })}
                </div>
                
                <div className="mt-2 text-[10px] text-gray-500">
                  {config.source}
                </div>
              </div>
            </button>
          );
        })}
      </div>
      
      {/* Selection summary */}
      <div className="mt-4 p-3 bg-gray-800/50 rounded-lg">
        <p className="text-xs text-gray-400">
          {selectedStrategies.length === 1 ? (
            <>
              <strong className={STRATEGY_CONFIG[selectedStrategies[0]].color}>
                Single Strategy:
              </strong>{' '}
              Running {STRATEGY_CONFIG[selectedStrategies[0]].name} only.
            </>
          ) : (
            <>
              <strong className="text-purple-400">Comparison Mode:</strong>{' '}
              Running {selectedStrategies.map(s => STRATEGY_CONFIG[s].name).join(' vs ')} in parallel. 
              Results will appear in separate tabs for comparison.
            </>
          )}
        </p>
      </div>
    </div>
  );
}

