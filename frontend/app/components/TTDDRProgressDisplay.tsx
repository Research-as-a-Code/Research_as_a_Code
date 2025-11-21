// SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
// SPDX-License-Identifier: Apache-2.0

/**
 * TTD-DR Progress Display Component
 * 
 * Visualizes the Test-Time Diffusion process with its stages:
 * Planning → Iterating (with denoising) → Synthesizing
 */

"use client";

import React from 'react';
import { 
  FileText, 
  Search, 
  Sparkles, 
  RefreshCw, 
  CheckCircle, 
  ArrowRight,
  Brain,
  Dna,
  FileCheck,
  TrendingUp
} from 'lucide-react';

export type TTDDRStage = 'planning' | 'iterating' | 'synthesizing' | 'complete' | 'idle';

interface TTDDRState {
  stage: TTDDRStage;
  currentIteration: number;
  maxIterations: number;
  convergenceScores: number[];
  currentQuestions: string[];
  gaps: string[];
  improvements: string[];
  variants?: number;
  draftWordCount?: number;
}

interface TTDDRProgressDisplayProps {
  state: TTDDRState;
}

export function TTDDRProgressDisplay({ state }: TTDDRProgressDisplayProps) {
  const stages = [
    { 
      id: 'planning', 
      label: 'Research Plan', 
      icon: FileText,
      color: 'blue'
    },
    { 
      id: 'iterating', 
      label: 'Iterative Refinement', 
      icon: RefreshCw,
      color: 'green'
    },
    { 
      id: 'synthesizing', 
      label: 'Final Synthesis', 
      icon: FileCheck,
      color: 'purple'
    }
  ];

  const getStageIndex = (stage: TTDDRStage): number => {
    const index = stages.findIndex(s => s.id === stage);
    return index >= 0 ? index : -1;
  };

  const currentStageIndex = getStageIndex(state.stage);

  return (
    <div className="bg-gray-900/50 backdrop-blur-lg rounded-xl p-6 border border-gray-700">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-green-400" />
          TTD-DR Process
        </h3>
        {state.stage === 'complete' && (
          <span className="px-3 py-1 bg-green-500/20 text-green-400 text-xs rounded-full flex items-center gap-1">
            <CheckCircle className="w-3 h-3" />
            Complete
          </span>
        )}
      </div>

      {/* Stage Pipeline */}
      <div className="flex items-center justify-between mb-6">
        {stages.map((stage, index) => (
          <React.Fragment key={stage.id}>
            <div className="flex flex-col items-center">
              <div className={`
                p-3 rounded-lg mb-2 transition-all duration-300
                ${index <= currentStageIndex 
                  ? stage.id === state.stage 
                    ? `bg-${stage.color}-500/20 border-2 border-${stage.color}-500 shadow-lg shadow-${stage.color}-500/30` 
                    : `bg-${stage.color}-500/10 border border-${stage.color}-500/50`
                  : 'bg-gray-800 border border-gray-700'}
              `}>
                <stage.icon className={`
                  w-6 h-6 transition-colors
                  ${index <= currentStageIndex 
                    ? stage.id === state.stage 
                      ? `text-${stage.color}-400` 
                      : `text-${stage.color}-500/70`
                    : 'text-gray-500'}
                `} />
              </div>
              <span className={`
                text-xs text-center
                ${index <= currentStageIndex ? 'text-gray-300' : 'text-gray-600'}
              `}>
                {stage.label}
              </span>
            </div>
            {index < stages.length - 1 && (
              <ArrowRight className={`
                w-4 h-4 mx-2 mb-7
                ${index < currentStageIndex ? 'text-green-500' : 'text-gray-600'}
              `} />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Stage-specific Content */}
      <div className="space-y-4">
        {state.stage === 'planning' && (
          <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-500/30">
            <div className="flex items-center gap-2 mb-2">
              <Brain className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-medium text-blue-300">Generating Research Plan</span>
            </div>
            <p className="text-xs text-gray-400">
              Creating structured approach with key areas, questions, and expected sections...
            </p>
          </div>
        )}

        {state.stage === 'iterating' && (
          <>
            {/* Iteration Progress */}
            <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/30">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <RefreshCw className="w-4 h-4 text-green-400 animate-spin" />
                  <span className="text-sm font-medium text-green-300">
                    Iteration {state.currentIteration} of {state.maxIterations}
                  </span>
                </div>
                {state.convergenceScores.length > 0 && (
                  <span className="text-xs text-gray-400">
                    Convergence: {(state.convergenceScores[state.convergenceScores.length - 1] * 100).toFixed(1)}%
                  </span>
                )}
              </div>

              {/* Convergence Chart */}
              {state.convergenceScores.length > 0 && (
                <div className="mb-3">
                  <div className="h-20 flex items-end gap-1 mb-1">
                    {state.convergenceScores.map((score, i) => (
                      <div key={i} className="flex-1 flex flex-col items-center">
                        <div
                          className={`
                            w-full transition-all duration-500
                            ${score >= 0.85 
                              ? 'bg-green-500' 
                              : score >= 0.7 
                                ? 'bg-yellow-500' 
                                : 'bg-orange-500'}
                          `}
                          style={{ height: `${score * 100}%` }}
                        />
                        <span className="text-[9px] text-gray-500 mt-1">{i + 1}</span>
                      </div>
                    ))}
                    {/* Show remaining iterations as empty */}
                    {Array.from({ length: state.maxIterations - state.convergenceScores.length }, (_, i) => (
                      <div key={`empty-${i}`} className="flex-1 flex flex-col items-center">
                        <div className="w-full bg-gray-700/30" style={{ height: '2px' }} />
                        <span className="text-[9px] text-gray-600 mt-1">
                          {state.convergenceScores.length + i + 1}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className="flex justify-between text-[10px] text-gray-500">
                    <span>0%</span>
                    <span>Convergence Target: 85%</span>
                    <span>100%</span>
                  </div>
                </div>
              )}

              {/* Current Sub-processes */}
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-gray-800/50 rounded p-2">
                  <Search className="w-3 h-3 text-blue-400 mb-1" />
                  <p className="text-[10px] text-gray-400">Searching</p>
                </div>
                <div className="bg-gray-800/50 rounded p-2">
                  <Sparkles className="w-3 h-3 text-yellow-400 mb-1" />
                  <p className="text-[10px] text-gray-400">Denoising</p>
                </div>
                {state.variants && state.variants > 0 && (
                  <div className="bg-gray-800/50 rounded p-2">
                    <Dna className="w-3 h-3 text-purple-400 mb-1" />
                    <p className="text-[10px] text-gray-400">Evolution</p>
                  </div>
                )}
              </div>
            </div>

            {/* Current Questions */}
            {state.currentQuestions.length > 0 && (
              <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
                <h4 className="text-xs font-medium text-gray-400 mb-2">Current Questions:</h4>
                <ul className="space-y-1">
                  {state.currentQuestions.slice(0, 3).map((q, i) => (
                    <li key={i} className="text-xs text-gray-500 flex items-start gap-1">
                      <span className="text-blue-400 mt-0.5">•</span>
                      <span className="line-clamp-1">{q}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Improvements */}
            {state.improvements.length > 0 && (
              <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
                <h4 className="text-xs font-medium text-gray-400 mb-2 flex items-center gap-1">
                  <TrendingUp className="w-3 h-3 text-green-400" />
                  Improvements:
                </h4>
                <ul className="space-y-1">
                  {state.improvements.slice(-3).map((imp, i) => (
                    <li key={i} className="text-xs text-green-400/70 flex items-start gap-1">
                      <CheckCircle className="w-3 h-3 mt-0.5" />
                      <span>{imp}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Draft Stats */}
            {state.draftWordCount && (
              <div className="flex items-center justify-between text-xs text-gray-500">
                <span>Draft: {state.draftWordCount} words</span>
                {state.gaps.length > 0 && (
                  <span className="text-orange-400">{state.gaps.length} gaps remaining</span>
                )}
              </div>
            )}
          </>
        )}

        {state.stage === 'synthesizing' && (
          <div className="bg-purple-500/10 rounded-lg p-4 border border-purple-500/30">
            <div className="flex items-center gap-2 mb-2">
              <FileCheck className="w-4 h-4 text-purple-400" />
              <span className="text-sm font-medium text-purple-300">Generating Final Report</span>
            </div>
            <p className="text-xs text-gray-400">
              Polishing converged draft, ensuring professional presentation...
            </p>
            {state.convergenceScores.length > 0 && (
              <div className="mt-2 text-xs text-gray-500">
                Final convergence: {(state.convergenceScores[state.convergenceScores.length - 1] * 100).toFixed(1)}%
                after {state.convergenceScores.length} iterations
              </div>
            )}
          </div>
        )}

        {state.stage === 'complete' && (
          <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/30">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle className="w-4 h-4 text-green-400" />
              <span className="text-sm font-medium text-green-300">Research Complete</span>
            </div>
            <div className="grid grid-cols-2 gap-4 mt-3 text-xs">
              <div>
                <span className="text-gray-500">Iterations:</span>
                <span className="ml-2 text-gray-300">{state.convergenceScores.length}</span>
              </div>
              <div>
                <span className="text-gray-500">Final Convergence:</span>
                <span className="ml-2 text-gray-300">
                  {state.convergenceScores.length > 0 
                    ? `${(state.convergenceScores[state.convergenceScores.length - 1] * 100).toFixed(1)}%`
                    : 'N/A'}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Process Explanation */}
      {state.stage === 'idle' && (
        <div className="text-center py-8 text-gray-500">
          <Sparkles className="w-8 h-8 mx-auto mb-3 text-gray-600" />
          <p className="text-sm">TTD-DR Ready</p>
          <p className="text-xs mt-2 text-gray-600">
            Will iteratively refine research through denoising
          </p>
        </div>
      )}
    </div>
  );
}
