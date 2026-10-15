import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { X, Send, Upload, Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { notifyEvaluationChanged } from '@/lib/events';
import { cn } from '@/lib/utils';
import { ChatSummaryTable } from './ChatSummaryTable';
import type {
  ChatTurnResponse,
  ChatExpect,
  ChatJobInfo,
  ChatSummary,
  ChatAction,
  ChatCollectedDetails,
} from '@/lib/types';

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  expect?: ChatExpect | null;
  job?: ChatJobInfo | null;
  summary?: ChatSummary | null;
  state?: string;
}

interface AskVixenPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AskVixenPanel: React.FC<AskVixenPanelProps> = ({ isOpen, onClose }) => {
  const location = useLocation();
  const navigate = useNavigate();

  // In-memory conversation state only
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentEvaluationId, setCurrentEvaluationId] = useState<string | null>(null);
  const [collectedDetails, setCollectedDetails] = useState<ChatCollectedDetails | null>(null);

  const [inputText, setInputText] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const latestMessage = messages[messages.length - 1];
  const latestExpect = latestMessage?.sender === 'assistant' ? latestMessage.expect : null;
  const latestJob = latestMessage?.sender === 'assistant' ? latestMessage.job : null;
  const latestState = latestMessage?.state;

  const isJobRunning = Boolean(
    (latestJob &&
      ['queued', 'extracting', 'analysing', 'running', 'started'].includes(
        latestJob.status.toLowerCase()
      )) ||
      ((latestState === 'extracting' || latestState === 'analysing') &&
        latestJob?.status !== 'done' &&
        latestJob?.status !== 'failed')
  );

  const hasSummary = messages.some((m) => Boolean(m.summary));

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, uploading, scrollToBottom]);

  // Handle Esc key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const applyTurnResponse = useCallback(
    (res: ChatTurnResponse) => {
      if (res.evaluation_id) {
        setCurrentEvaluationId(res.evaluation_id);
        notifyEvaluationChanged(res.evaluation_id);
      }
      if (res.collected) {
        setCollectedDetails(res.collected);
      }

      setMessages((prev) => [
        ...prev,
        {
          id: Math.random().toString(36).substring(2, 9),
          sender: 'assistant',
          text: res.reply,
          expect: res.expect ?? null,
          job: res.job ?? null,
          summary: res.summary ?? null,
          state: res.state,
        },
      ]);
    },
    []
  );

  const sendTurn = useCallback(
    async (payload: {
      evaluation_id?: string | null;
      message?: string | null;
      action?: ChatAction | null;
      collected?: ChatCollectedDetails | null;
    }) => {
      try {
        setLoading(true);
        const res = await apiClient.chatTurn({
          evaluation_id: payload.evaluation_id ?? currentEvaluationId,
          message: payload.message ?? null,
          action: payload.action ?? null,
          collected: payload.collected ?? collectedDetails,
        });
        applyTurnResponse(res);
      } catch (err: unknown) {
        const errorText =
          err instanceof Error ? err.message : 'Something went wrong. Please try again.';
        setMessages((prev) => [
          ...prev,
          {
            id: Math.random().toString(36).substring(2, 9),
            sender: 'assistant',
            text: errorText,
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [currentEvaluationId, collectedDetails, applyTurnResponse]
  );

  // Initialize or attach context when opened
  useEffect(() => {
    if (!isOpen) return;

    const match = location.pathname.match(/\/evaluations\/([^/]+)/);
    const routeEvalId = match && match[1] !== 'new' ? match[1] : null;

    if (routeEvalId) {
      // Opened on an evaluation page: attach to that evaluation and resume
      if (currentEvaluationId !== routeEvalId) {
        setCurrentEvaluationId(routeEvalId);
        setCollectedDetails(null);
        setMessages([]);
        sendTurn({ evaluation_id: routeEvalId });
      }
    } else {
      // Opened elsewhere (e.g. list, settings): new evaluation in memory
      if (currentEvaluationId !== null || messages.length === 0) {
        setCurrentEvaluationId(null);
        setCollectedDetails(null);
        setMessages([]);
        sendTurn({ evaluation_id: null });
      }
    }
  }, [isOpen]); // Intentionally on isOpen change

  // Polling every 2 s while a job runs and panel is open
  useEffect(() => {
    if (!isOpen || !currentEvaluationId || !isJobRunning) {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const res = await apiClient.chatTurn({
          evaluation_id: currentEvaluationId,
        });
        // Replace or append if status changed
        if (
          res.job?.status !== latestJob?.status ||
          res.job?.step_label !== latestJob?.step_label ||
          res.state !== latestState ||
          res.summary
        ) {
          applyTurnResponse(res);
        }
      } catch {
        // Silently ignore background polling errors
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [isOpen, currentEvaluationId, isJobRunning, latestJob?.status, latestJob?.step_label, latestState, applyTurnResponse]);

  const handleStartNew = () => {
    setCurrentEvaluationId(null);
    setCollectedDetails(null);
    setMessages([]);
    setInputText('');
    setUploadError(null);
    sendTurn({ evaluation_id: null });
  };

  const handleSendMessage = async () => {
    const text = inputText.trim();
    if (!text || loading || uploading) return;

    setInputText('');
    setMessages((prev) => [
      ...prev,
      {
        id: Math.random().toString(36).substring(2, 9),
        sender: 'user',
        text,
      },
    ]);

    await sendTurn({ message: text });
  };

  const handleChoiceClick = async (action: string, label: string) => {
    if (loading || uploading) return;

    setMessages((prev) => [
      ...prev,
      {
        id: Math.random().toString(36).substring(2, 9),
        sender: 'user',
        text: label,
      },
    ]);

    await sendTurn({
      action: action as ChatAction,
    });
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !currentEvaluationId || !latestExpect) return;

    setUploadError(null);
    setUploading(true);

    try {
      await apiClient.uploadDocument(
        currentEvaluationId,
        file,
        latestExpect.file_kind || 'requirements',
        latestExpect.vendor_id
      );

      // Refresh background tabs/lists
      notifyEvaluationChanged(currentEvaluationId);

      setMessages((prev) => [
        ...prev,
        {
          id: Math.random().toString(36).substring(2, 9),
          sender: 'user',
          text: `Uploaded ${file.name}`,
        },
      ]);

      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      // Send a turn so chat moves on
      await sendTurn({ evaluation_id: currentEvaluationId });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setUploadError(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleNavigate = (tab: 'comparison' | 'recommendation') => {
    if (currentEvaluationId) {
      navigate(`/evaluations/${currentEvaluationId}/${tab}`);
    }
  };

  if (!isOpen) return null;

  const fileSlotLabel =
    latestExpect?.file_kind === 'requirements' ? 'Requirements' : 'Proposal';
  const fileUploadLabel = latestExpect?.vendor_name
    ? `Upload ${fileSlotLabel} for ${latestExpect.vendor_name} (PDF or DOCX)`
    : `Upload ${fileSlotLabel} document (PDF or DOCX)`;

  return (
    <div
      role="dialog"
      aria-label="Ask Vixen Chat"
      className={cn(
        'fixed bottom-22 right-6 z-50 flex flex-col bg-background border border-border rounded-xl shadow-2xl transition-all duration-200 print:hidden overflow-hidden',
        hasSummary
          ? 'w-[740px] max-w-[calc(100vw-32px)]'
          : 'w-[420px] max-w-[calc(100vw-32px)]',
        'h-[600px] max-h-[calc(100vh-110px)]'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface shrink-0">
        <div className="flex items-center gap-2">
          <img src="/fox.png" alt="" className="h-6 w-6 object-contain pointer-events-none" />
          <span className="font-semibold text-text text-sm sm:text-base">Ask Vixen</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleStartNew}
            className="text-xs font-medium text-muted hover:text-navy px-2 py-1 rounded transition-colors focus:outline-none focus:ring-1 focus:ring-navy cursor-pointer"
            aria-label="Start new evaluation"
          >
            Start new
          </button>
          <button
            type="button"
            onClick={onClose}
            className="text-muted hover:text-text p-1 rounded-md transition-colors focus:outline-none focus:ring-1 focus:ring-navy cursor-pointer"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-4 space-y-3.5 bg-background">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              'flex flex-col',
              msg.sender === 'user' ? 'items-end' : 'items-start'
            )}
          >
            <div
              className={cn(
                'text-xs sm:text-sm px-3.5 py-2.5 rounded-2xl break-words',
                msg.sender === 'user'
                  ? 'bg-navy text-white rounded-br-xs max-w-[85%]'
                  : 'bg-surface text-text border border-border rounded-bl-xs max-w-[95%] space-y-2'
              )}
            >
              <div className="whitespace-pre-wrap">{msg.text}</div>

              {/* Summary table if present */}
              {msg.summary && (
                <ChatSummaryTable
                  summary={msg.summary}
                  onNavigate={handleNavigate}
                />
              )}
            </div>
          </div>
        ))}

        {/* Polling / Job progress banner */}
        {isJobRunning && (
          <div className="flex items-center gap-2 p-2.5 rounded-lg bg-navy/5 border border-navy/15 text-xs text-navy font-medium">
            <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0 text-navy" />
            <span>
              {latestJob?.step_label ||
                (latestState === 'extracting'
                  ? 'Extracting requirements...'
                  : 'Analyzing proposals...')}
            </span>
          </div>
        )}

        {/* Loading indicator */}
        {loading && (
          <div className="flex items-center gap-2 text-xs text-muted">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-navy" />
            <span>Vixen is thinking...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Expect Controls & Input area */}
      <div className="p-3 border-t border-border bg-surface shrink-0 space-y-2">
        {/* File upload expect */}
        {latestExpect?.kind === 'file' && (
          <div className="p-2.5 rounded-lg border border-border bg-background space-y-2">
            <input
              type="file"
              ref={fileInputRef}
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={handleFileUpload}
              className="hidden"
            />
            <button
              type="button"
              disabled={uploading || loading}
              onClick={() => fileInputRef.current?.click()}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-md bg-navy text-white hover:bg-navy/90 transition-colors disabled:opacity-50 cursor-pointer"
            >
              {uploading ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Uploading {fileSlotLabel}...</span>
                </>
              ) : (
                <>
                  <Upload className="h-3.5 w-3.5" />
                  <span>{fileUploadLabel}</span>
                </>
              )}
            </button>
            {uploadError && (
              <p className="text-xs text-status-noncompliant-text mt-1">{uploadError}</p>
            )}
          </div>
        )}

        {/* Choice expect */}
        {latestExpect?.kind === 'choice' && latestExpect.options && (
          <div className="flex flex-wrap gap-1.5 pb-1">
            {latestExpect.options.map((opt, i) => (
              <button
                key={i}
                type="button"
                disabled={loading || uploading}
                onClick={() => handleChoiceClick(opt.action, opt.label)}
                className="text-xs font-medium px-3 py-1.5 rounded-md border border-navy/40 bg-navy/5 text-navy hover:bg-navy hover:text-white transition-colors disabled:opacity-50 cursor-pointer"
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}

        {/* Text Input area (always available for conversation) */}
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            placeholder="Type a message..."
            disabled={loading || uploading}
            className="flex-1 h-9 px-3 text-xs sm:text-sm bg-background border border-border rounded-md text-text placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-navy disabled:opacity-50"
          />
          <button
            type="button"
            onClick={handleSendMessage}
            disabled={!inputText.trim() || loading || uploading}
            aria-label="Send message"
            className="h-9 px-3 flex items-center justify-center rounded-md bg-navy text-white hover:bg-navy/90 disabled:opacity-40 transition-colors cursor-pointer"
          >
            <Send className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
