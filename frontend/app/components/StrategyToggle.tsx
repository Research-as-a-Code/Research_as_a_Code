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
import { Code2, Sparkles, Zap, Clock, DollarSign, Target } from 'lucide-react';

export type ResearchStrategy = 'udr' | 'ttd_dr';

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
            {value === 'udr' ? 'NVIDIA' : 'Google'}
          </span>
        </div>
      </div>
      
      <div className="grid grid-cols-2 gap-4">
        {/* UDR Option */}
        <button
          onClick={() => !disabled && onChange('udr')}
          disabled={disabled}
          className={`
            relative p-4 rounded-lg border-2 transition-all duration-200
            ${value === 'udr' 
              ? 'border-blue-500 bg-blue-500/10 shadow-lg shadow-blue-500/20' 
              : 'border-gray-700 hover:border-gray-600 bg-gray-800/50'}
            ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          `}
        >
          {value === 'udr' && (
            <div className="absolute -top-2 -right-2">
              <span className="flex h-4 w-4">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-4 w-4 bg-blue-500"></span>
              </span>
            </div>
          )}
          
          <div className="flex flex-col items-center text-center">
            <div className={`mb-3 p-3 rounded-lg ${
              value === 'udr' ? 'bg-blue-500/20' : 'bg-gray-700/50'
            }`}>
              <Code2 className={`w-8 h-8 ${
                value === 'udr' ? 'text-blue-400' : 'text-gray-400'
              }`} />
            </div>
            
            <h4 className="font-semibold text-gray-100 mb-1">UDR</h4>
            <p className="text-xs text-gray-400 mb-3">
              Universal Deep Research
            </p>
            
            <div className="w-full space-y-2 text-left">
              <p className="text-xs text-gray-500">
                Strategy-as-Code approach
              </p>
              
              {/* Characteristics */}
              <div className="space-y-1 pt-2 border-t border-gray-700/50">
                <div className="flex items-center gap-2 text-xs">
                  <Zap className="w-3 h-3 text-yellow-500" />
                  <span className="text-gray-400">10-30s</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <DollarSign className="w-3 h-3 text-green-500" />
                  <span className="text-gray-400">Lower cost</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <Target className="w-3 h-3 text-blue-500" />
                  <span className="text-gray-400">Precise execution</span>
                </div>
              </div>
              
              <p className="text-[10px] text-gray-600 pt-2">
                Best for: Structured queries, quick results
              </p>
            </div>
          </div>
        </button>
        
        {/* TTD-DR Option */}
        <button
          onClick={() => !disabled && onChange('ttd_dr')}
          disabled={disabled}
          className={`
            relative p-4 rounded-lg border-2 transition-all duration-200
            ${value === 'ttd_dr' 
              ? 'border-green-500 bg-green-500/10 shadow-lg shadow-green-500/20' 
              : 'border-gray-700 hover:border-gray-600 bg-gray-800/50'}
            ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          `}
        >
          {value === 'ttd_dr' && (
            <div className="absolute -top-2 -right-2">
              <span className="flex h-4 w-4">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-4 w-4 bg-green-500"></span>
              </span>
            </div>
          )}
          
          <div className="flex flex-col items-center text-center">
            <div className={`mb-3 p-3 rounded-lg ${
              value === 'ttd_dr' ? 'bg-green-500/20' : 'bg-gray-700/50'
            }`}>
              <Sparkles className={`w-8 h-8 ${
                value === 'ttd_dr' ? 'text-green-400' : 'text-gray-400'
              }`} />
            </div>
            
            <h4 className="font-semibold text-gray-100 mb-1">TTD-DR</h4>
            <p className="text-xs text-gray-400 mb-3">
              Test-Time Diffusion
            </p>
            
            <div className="w-full space-y-2 text-left">
              <p className="text-xs text-gray-500">
                Iterative refinement approach
              </p>
              
              {/* Characteristics */}
              <div className="space-y-1 pt-2 border-t border-gray-700/50">
                <div className="flex items-center gap-2 text-xs">
                  <Clock className="w-3 h-3 text-orange-500" />
                  <span className="text-gray-400">45-90s</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <DollarSign className="w-3 h-3 text-red-500" />
                  <span className="text-gray-400">Higher cost</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <Target className="w-3 h-3 text-green-500" />
                  <span className="text-gray-400">Superior quality</span>
                </div>
              </div>
              
              <p className="text-[10px] text-gray-600 pt-2">
                Best for: Complex research, quality focus
              </p>
            </div>
          </div>
        </button>
      </div>
      
      {/* Current Selection Description */}
      <div className="mt-4 p-3 bg-gray-800/50 rounded-lg">
        <p className="text-xs text-gray-400">
          {value === 'udr' ? (
            <>
              <strong className="text-blue-400">UDR Mode:</strong> The agent will compile your 
              research request into executable Python code that orchestrates search tools. 
              Fast and deterministic, ideal for well-defined queries.
            </>
          ) : (
            <>
              <strong className="text-green-400">TTD-DR Mode:</strong> The agent will create an 
              initial draft and iteratively refine it through multiple rounds of search and 
              denoising. Produces higher quality results for complex topics.
            </>
          )}
        </p>
      </div>
    </div>
  );
}
