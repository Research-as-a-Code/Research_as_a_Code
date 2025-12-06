// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * Strategy Toggle Component
 * 
 * Allows users to select between UDR (Universal Deep Research) and 
 * TTD-DR (Test-Time Diffusion Deep Researcher) strategies.
 */

"use client";

import React from 'react';
import { Code2, Sparkles, Zap, Clock, DollarSign, Target, Brain } from 'lucide-react';

export type ResearchStrategy = 'auto' | 'udr' | 'ttd_dr';

interface StrategyToggleProps {
  value: ResearchStrategy;
  onChange: (value: ResearchStrategy) => void;
  disabled?: boolean;
}

export function StrategyToggle({ 
  value, 
  onChange, 
  disabled = false 
}: StrategyToggleProps) {
  
  return (
    <div className="bg-gray-900/50 backdrop-blur-lg rounded-xl p-6 border border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-100">
          Research Strategy
        </h3>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span className="px-2 py-1 bg-gray-800 rounded">
            {value === 'auto' ? 'AI Decides' : value === 'udr' ? 'NVIDIA' : 'Google'}
          </span>
        </div>
      </div>
      
      <div className="grid grid-cols-3 gap-3">
        {/* Auto Option */}
        <button
          onClick={() => !disabled && onChange('auto')}
          disabled={disabled}
          className={`
            relative p-3 rounded-lg border-2 transition-all duration-200
            ${value === 'auto' 
              ? 'border-purple-500 bg-purple-500/10 shadow-lg shadow-purple-500/20' 
              : 'border-gray-700 hover:border-gray-600 bg-gray-800/50'}
            ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          `}
        >
          {value === 'auto' && (
            <div className="absolute -top-2 -right-2">
              <span className="flex h-4 w-4">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-4 w-4 bg-purple-500"></span>
              </span>
            </div>
          )}
          
          <div className="flex flex-col items-center text-center">
            <div className={`mb-2 p-2 rounded-lg ${
              value === 'auto' ? 'bg-purple-500/20' : 'bg-gray-700/50'
            }`}>
              <Brain className={`w-6 h-6 ${
                value === 'auto' ? 'text-purple-400' : 'text-gray-400'
              }`} />
            </div>
            
            <h4 className="font-semibold text-gray-100 text-sm mb-1">Auto</h4>
            <p className="text-[10px] text-gray-400 mb-2">
              AI Decides
            </p>
            
            <div className="w-full space-y-1 text-left">
              <div className="flex items-center gap-1 text-[10px]">
                <Zap className="w-2.5 h-2.5 text-yellow-500" />
                <span className="text-gray-400">Smart routing</span>
              </div>
              <div className="flex items-center gap-1 text-[10px]">
                <Target className="w-2.5 h-2.5 text-purple-500" />
                <span className="text-gray-400">Adaptive</span>
              </div>
            </div>
          </div>
        </button>
        {/* UDR Option */}
        <button
          onClick={() => !disabled && onChange('udr')}
          disabled={disabled}
          className={`
            relative p-3 rounded-lg border-2 transition-all duration-200
            ${value === 'udr' 
              ? 'border-green-500 bg-green-500/10 shadow-lg shadow-green-500/20' 
              : 'border-gray-700 hover:border-gray-600 bg-gray-800/50'}
            ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          `}
        >
          {value === 'udr' && (
            <div className="absolute -top-2 -right-2">
              <span className="flex h-4 w-4">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-4 w-4 bg-green-500"></span>
              </span>
            </div>
          )}
          
          <div className="flex flex-col items-center text-center">
            <div className={`mb-2 p-2 rounded-lg ${
              value === 'udr' ? 'bg-green-500/20' : 'bg-gray-700/50'
            }`}>
              <Code2 className={`w-6 h-6 ${
                value === 'udr' ? 'text-green-400' : 'text-gray-400'
              }`} />
            </div>
            
            <h4 className="font-semibold text-gray-100 text-sm mb-1">UDR</h4>
            <p className="text-[10px] text-gray-400 mb-2">
              Strategy-as-Code
            </p>
            
            <div className="w-full space-y-1 text-left">
              <div className="flex items-center gap-1 text-[10px]">
                <Zap className="w-2.5 h-2.5 text-yellow-500" />
                <span className="text-gray-400">10-30s</span>
              </div>
              <div className="flex items-center gap-1 text-[10px]">
                <DollarSign className="w-2.5 h-2.5 text-green-500" />
                <span className="text-gray-400">Lower cost</span>
              </div>
            </div>
          </div>
        </button>
        
        {/* TTD-DR Option */}
        <button
          onClick={() => !disabled && onChange('ttd_dr')}
          disabled={disabled}
          className={`
            relative p-3 rounded-lg border-2 transition-all duration-200
            ${value === 'ttd_dr' 
              ? 'border-blue-500 bg-blue-500/10 shadow-lg shadow-blue-500/20' 
              : 'border-gray-700 hover:border-gray-600 bg-gray-800/50'}
            ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          `}
        >
          {value === 'ttd_dr' && (
            <div className="absolute -top-2 -right-2">
              <span className="flex h-4 w-4">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-4 w-4 bg-blue-500"></span>
              </span>
            </div>
          )}
          
          <div className="flex flex-col items-center text-center">
            <div className={`mb-2 p-2 rounded-lg ${
              value === 'ttd_dr' ? 'bg-blue-500/20' : 'bg-gray-700/50'
            }`}>
              <Sparkles className={`w-6 h-6 ${
                value === 'ttd_dr' ? 'text-blue-400' : 'text-gray-400'
              }`} />
            </div>
            
            <h4 className="font-semibold text-gray-100 text-sm mb-1">TTD-DR</h4>
            <p className="text-[10px] text-gray-400 mb-2">
              Iterative Refinement
            </p>
            
            <div className="w-full space-y-1 text-left">
              <div className="flex items-center gap-1 text-[10px]">
                <Clock className="w-2.5 h-2.5 text-orange-500" />
                <span className="text-gray-400">45-90s</span>
              </div>
              <div className="flex items-center gap-1 text-[10px]">
                <Target className="w-2.5 h-2.5 text-blue-500" />
                <span className="text-gray-400">Best quality</span>
              </div>
            </div>
          </div>
        </button>
      </div>
      
      {/* Current Selection Description */}
      <div className="mt-4 p-3 bg-gray-800/50 rounded-lg">
        <p className="text-xs text-gray-400">
          {value === 'auto' ? (
            <>
              <strong className="text-purple-400">Auto Mode:</strong> The AI planner will analyze 
              your query and choose the best strategy. Simple queries use fast RAG, complex ones 
              use UDR or TTD-DR automatically.
            </>
          ) : value === 'udr' ? (
            <>
              <strong className="text-green-400">UDR Mode:</strong> The agent will compile your 
              research request into executable Python code that orchestrates search tools. 
              Fast and deterministic, ideal for well-defined queries.
            </>
          ) : (
            <>
              <strong className="text-blue-400">TTD-DR Mode:</strong> The agent will create an 
              initial draft and iteratively refine it through multiple rounds of search and 
              denoising. Produces higher quality results for complex topics.
            </>
          )}
        </p>
      </div>
    </div>
  );
}
