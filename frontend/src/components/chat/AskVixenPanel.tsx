import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { X, Send, Upload, Loader2, Check } from 'lucide-react';
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
  ChatDocumentSlot,
} from '@/lib/types';

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  expect?: ChatExpect | null;
  job?: ChatJobInfo | null;
  summary?: ChatSummary | null;
  state?: string;
  isProgress?: boolean;
}

interface AskVixenPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const parseConfirmCardDetails = (text: string, collected?: ChatCollectedDetails | null) => {
  const titleMatch = text.match(/•\s*Title:\s*(.+)/i);
  const catMatch = text.match(/•\s*Category:\s*(.+)/i);
  const locMatch = text.match(/•\s*Location:\s*(.+)/i);
  const venMatch = text.match(/•\s*Vendors:\s*(.+)/i);

  return {
    title: titleMatch ? titleMatch[1].trim() : (collected?.title || '—'),
    category: catMatch ? catMatch[1].trim() : (collected?.category || '—'),
    location: locMatch ? locMatch[1].trim() : 'None',
    vendors: venMatch ? venMatch[1].trim() : (collected?.vendor_names?.join(', ') || '—'),
  };
};

export const AskVixenPanel: React.FC<AskVixenPanelProps> = ({ isOpen, onClose }) => {
  const location = useLocation();
  const navigate = useNavigate();

  // In-memory conversation state only
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentEvaluationId, setCurrentEvaluationId] = useState<string | null>(null);
  const [collectedDetails, setCollectedDetails] = useState<ChatCollectedDetails | null>(null);
  const [isDetached, setIsDetached] = useState<boolean>(false);

  const [inputText, setInputText] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [slotErrors, setSlotErrors] = useState<Record<string, string>>({});
  const [uploadingSlotKey, setUploadingSlotKey] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const lastAttachedPathRef = useRef<string | null>(null);

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
        setIsDetached(false);
        notifyEvaluationChanged(res.evaluation_id);
      }
      if (res.collected) {
        setCollectedDetails(res.collected);
      }

      setMessages((prev) => {
        const lastIndex = prev.length - 1;
        const lastMsg = lastIndex >= 0 ? prev[lastIndex] : null;
        const lastWasProgress = lastMsg?.sender === 'assistant' && lastMsg?.isProgress;

        const isRunning = Boolean(
          (res.job &&
            ['queued', 'extracting', 'analysing', 'running', 'started'].includes(
              res.job.status.toLowerCase()
            )) ||
            ((res.state === 'extracting' || res.state === 'analysing') &&
              res.job?.status !== 'done' &&
              res.job?.status !== 'failed')
        );

        const displayStepLabel = res.job?.step_label || res.reply;

        if (lastWasProgress) {
          if (isRunning) {
            // Update in place with the latest step label
            const updated = [...prev];
            updated[lastIndex] = {
              ...lastMsg,
              text: displayStepLabel,
              job: res.job ?? null,
              state: res.state,
              expect: res.expect ?? null,
              summary: res.summary ?? null,
              isProgress: true,
            };
            return updated;
          } else {
            // Job ended: REPLACE the progress message with the result reply
            const updated = [...prev];
            updated[lastIndex] = {
              id: lastMsg.id,
              sender: 'assistant',
              text: res.reply,
              job: res.job ?? null,
              state: res.state,
              expect: res.expect ?? null,
              summary: res.summary ?? null,
              isProgress: false,
            };
            return updated;
          }
        }

        if (isRunning) {
          return [
            ...prev,
            {
              id: Math.random().toString(36).substring(2, 9),
              sender: 'assistant',
              text: displayStepLabel,
              job: res.job ?? null,
              state: res.state,
              expect: res.expect ?? null,
              summary: res.summary ?? null,
              isProgress: true,
            },
          ];
        }

        // If last was upload_files and this is also upload_files:
        const lastWasUploadFiles =
          lastMsg?.sender === 'assistant' && lastMsg?.state === 'upload_files';
        if (lastWasUploadFiles && res.state === 'upload_files') {
          const updated = [...prev];
          updated[lastIndex] = {
            ...lastMsg,
            text: res.reply,
            job: res.job ?? null,
            state: res.state,
            expect: res.expect ?? null,
            summary: res.summary ?? null,
            isProgress: false,
          };
          return updated;
        }

        return [
          ...prev,
          {
            id: Math.random().toString(36).substring(2, 9),
            sender: 'assistant',
            text: res.reply,
            expect: res.expect ?? null,
            job: res.job ?? null,
            summary: res.summary ?? null,
            state: res.state,
            isProgress: false,
          },
        ];
      });
    },
    []
  );

  const sendTurn = useCallback(
    async (payload: {
      evaluation_id?: string | null;
      message?: string | null;
      action?: ChatAction | null;
      collected?: ChatCollectedDetails | null;
      value?: string | null;
    }) => {
      try {
        setLoading(true);
        const evalId =
          payload.evaluation_id !== undefined
            ? payload.evaluation_id
            : (isDetached ? null : currentEvaluationId);
        const coll =
          payload.collected !== undefined
            ? payload.collected
            : (payload.evaluation_id === null ? null : collectedDetails);
        const res = await apiClient.chatTurn({
          evaluation_id: evalId,
          message: payload.message ?? null,
          action: payload.action ?? null,
          collected: coll,
          value: payload.value !== undefined ? payload.value : null,
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
    [currentEvaluationId, collectedDetails, isDetached, applyTurnResponse]
  );

  // Initialize or attach context when opened
  useEffect(() => {
    if (!isOpen) {
      setIsDetached(false);
      return;
    }

    const match = location.pathname.match(/\/evaluations\/([^/]+)/);
    const routeEvalId = match && match[1] !== 'new' ? match[1] : null;

    if (lastAttachedPathRef.current && lastAttachedPathRef.current !== location.pathname) {
      setIsDetached(false);
    }
    lastAttachedPathRef.current = location.pathname;

    if (isDetached) return;

    if (routeEvalId) {
      if (currentEvaluationId !== routeEvalId) {
        setCurrentEvaluationId(routeEvalId);
        setCollectedDetails(null);
        setMessages([]);
        sendTurn({ evaluation_id: routeEvalId });
      }
    } else {
      if (currentEvaluationId !== null || messages.length === 0) {
        setCurrentEvaluationId(null);
        setCollectedDetails(null);
        setMessages([]);
        sendTurn({ evaluation_id: null });
      }
    }
  }, [isOpen, location.pathname, isDetached, currentEvaluationId, messages.length, sendTurn]);

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
        applyTurnResponse(res);
      } catch {
        // Silently ignore background polling errors
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [isOpen, currentEvaluationId, isJobRunning, applyTurnResponse]);

  const handleStartNew = () => {
    setIsDetached(true);
    setCurrentEvaluationId(null);
    setCollectedDetails(null);
    setMessages([]);
    setInputText('');
    setUploadError(null);
    setSlotErrors({});
    setUploadingSlotKey(null);
    setUploading(false);
    sendTurn({ evaluation_id: null, collected: null });
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

  const handleChoiceClick = async (action: string, label: string, value?: string | null) => {
    if (loading || uploading) return;

    if (action === 'review_first') {
      if (currentEvaluationId) {
        navigate(`/evaluations/${currentEvaluationId}/requirements`);
      }
      // Send turn so chat stays open and keeps "Run analysis now" available
      await sendTurn({
        action: action as ChatAction,
        value: value !== undefined ? value : null,
      });
      return;
    }

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
      value: value !== undefined ? value : null,
    });
  };

  const handleSlotFileUpload = async (slot: ChatDocumentSlot, file: File) => {
    if (!currentEvaluationId) return;
    const slotKey = `${slot.kind}_${slot.vendor_id || ''}`;
    setSlotErrors((prev) => {
      const next = { ...prev };
      delete next[slotKey];
      return next;
    });
    setUploadingSlotKey(slotKey);

    try {
      await apiClient.uploadDocument(
        currentEvaluationId,
        file,
        slot.kind,
        slot.vendor_id ?? undefined
      );

      notifyEvaluationChanged(currentEvaluationId);
      await sendTurn({ evaluation_id: currentEvaluationId });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setSlotErrors((prev) => ({ ...prev, [slotKey]: msg }));
    } finally {
      setUploadingSlotKey(null);
    }
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

      notifyEvaluationChanged(currentEvaluationId);

      setMessages((prev) => [
        ...prev,
        {
          id: Math.random().toString(36).substring(2, 9),
          sender: 'user',
          text: `Uploaded ${file.name}`,
        },
      ]);

      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      await sendTurn({ evaluation_id: currentEvaluationId });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setUploadError(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleNavigate = (tab: 'comparison' | 'recommendation' | 'print') => {
    if (currentEvaluationId) {
      if (tab === 'print') {
        navigate(`/evaluations/${currentEvaluationId}/recommendation?print=true`);
      } else {
        navigate(`/evaluations/${currentEvaluationId}/${tab}`);
      }
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
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-accent-tint shrink-0">
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
        {messages.map((msg, index) => {
          const isLatest = index === messages.length - 1;

          return (
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
                    ? 'bg-orange text-navy rounded-br-xs max-w-[85%]'
                    : 'bg-surface text-text border border-border rounded-bl-xs max-w-[95%] space-y-2.5'
                )}
              >
                {msg.isProgress ? (
                  <div className="flex items-center gap-2 text-xs text-navy font-medium">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-navy shrink-0" />
                    <span>{msg.text}</span>
                  </div>
                ) : (
                  <>
                    {msg.state === 'confirm_details' ? (
                      <div className="space-y-2.5">
                        <p className="text-xs text-text font-medium">
                          Please confirm the evaluation details:
                        </p>
                        <div className="rounded-lg border border-border bg-background p-3 space-y-2">
                          {(() => {
                            const details = parseConfirmCardDetails(msg.text, collectedDetails);
                            return (
                              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                                <dt className="text-muted font-medium">Title:</dt>
                                <dd className="text-text font-medium">{details.title}</dd>

                                <dt className="text-muted font-medium">Category:</dt>
                                <dd className="text-text">{details.category}</dd>

                                <dt className="text-muted font-medium">Location:</dt>
                                <dd className="text-text">{details.location}</dd>

                                <dt className="text-muted font-medium">Vendors:</dt>
                                <dd className="text-text">{details.vendors}</dd>
                              </dl>
                            );
                          })()}

                          {msg.expect?.kind === 'choice' && msg.expect.options && (
                            <div className="flex flex-wrap gap-1.5 pt-2 border-t border-border">
                              {msg.expect.options.map((opt, i) => (
                                <button
                                  key={i}
                                  type="button"
                                  disabled={loading || uploading || !isLatest}
                                  onClick={() => handleChoiceClick(opt.action, opt.label, opt.value)}
                                  className="text-xs font-medium px-3 py-1.5 rounded-md border border-orange text-navy hover:bg-orange hover:text-navy active:bg-orange active:text-navy transition-colors disabled:opacity-50 cursor-pointer"
                                >
                                  {opt.label}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="whitespace-pre-wrap">{msg.text}</div>
                    )}

                    {/* Files Card for expect kind 'files' */}
                    {msg.expect?.kind === 'files' && msg.expect.files && (
                      <div className="rounded-lg border border-border bg-background p-3 space-y-2">
                        <div className="text-xs font-semibold text-text border-b border-border pb-1 flex items-center justify-between">
                          <span>Required Documents</span>
                          <span className="text-[11px] font-normal text-muted">PDF or DOCX</span>
                        </div>
                        <div className="divide-y divide-border">
                          {msg.expect.files.map((slot, idx) => {
                            const slotKey = `${slot.kind}_${slot.vendor_id || ''}`;
                            const isUploadingThis = uploadingSlotKey === slotKey;
                            const slotError = slotErrors[slotKey];
                            const slotLabel =
                              slot.kind === 'requirements'
                                ? 'Requirements document'
                                : `Proposal — ${slot.vendor_name || 'Vendor'}`;

                            return (
                              <div key={idx} className="py-2 first:pt-1 last:pb-0 flex flex-col gap-1">
                                <div className="flex items-center justify-between gap-2 text-xs">
                                  <span className="font-medium text-text">{slotLabel}</span>
                                  {slot.uploaded ? (
                                    <div className="flex items-center gap-1.5 text-status-compliant-text font-medium text-xs">
                                      <Check className="h-4 w-4 shrink-0" />
                                      <span
                                        className="text-muted truncate max-w-[150px]"
                                        title={slot.filename || undefined}
                                      >
                                        {slot.filename || 'Uploaded'}
                                      </span>
                                    </div>
                                  ) : (
                                    <div>
                                      <input
                                        type="file"
                                        id={`slot-file-input-${idx}`}
                                        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                        className="hidden"
                                        onChange={(e) => {
                                          const file = e.target.files?.[0];
                                          if (file) {
                                            handleSlotFileUpload(slot, file);
                                          }
                                          e.target.value = '';
                                        }}
                                        disabled={loading || uploading || isJobRunning}
                                      />
                                      <button
                                        type="button"
                                        disabled={
                                          loading ||
                                          uploading ||
                                          isJobRunning ||
                                          Boolean(uploadingSlotKey) ||
                                          !isLatest
                                        }
                                        onClick={() =>
                                          document.getElementById(`slot-file-input-${idx}`)?.click()
                                        }
                                        className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md border border-orange text-navy hover:bg-orange hover:text-navy active:bg-orange active:text-navy transition-colors disabled:opacity-50 cursor-pointer"
                                      >
                                        {isUploadingThis ? (
                                          <>
                                            <Loader2 className="h-3.5 w-3.5 animate-spin text-navy" />
                                            <span>Uploading...</span>
                                          </>
                                        ) : (
                                          <>
                                            <Upload className="h-3.5 w-3.5 text-navy" />
                                            <span>Upload</span>
                                          </>
                                        )}
                                      </button>
                                    </div>
                                  )}
                                </div>
                                {slotError && (
                                  <p className="text-xs text-status-noncompliant-text mt-0.5">
                                    {slotError}
                                  </p>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Summary table if present */}
                    {msg.summary && (
                      <ChatSummaryTable
                        summary={msg.summary}
                        onNavigate={handleNavigate}
                      />
                    )}
                  </>
                )}
              </div>
            </div>
          );
        })}

        {/* Loading indicator */}
        {loading && !isJobRunning && (
          <div className="flex items-center gap-2 text-xs text-muted">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-navy" />
            <span>Vixen is thinking...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Expect Controls & Input area */}
      <div className="p-3 border-t border-border bg-surface shrink-0 space-y-2">
        {/* Single file upload fallback if kind is 'file' */}
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
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-md border border-orange text-navy hover:bg-orange hover:text-navy active:bg-orange active:text-navy transition-colors disabled:opacity-50 cursor-pointer"
            >
              {uploading ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-navy" />
                  <span>Uploading {fileSlotLabel}...</span>
                </>
              ) : (
                <>
                  <Upload className="h-3.5 w-3.5 text-navy" />
                  <span>{fileUploadLabel}</span>
                </>
              )}
            </button>
            {uploadError && (
              <p className="text-xs text-status-noncompliant-text mt-1">{uploadError}</p>
            )}
          </div>
        )}

        {/* Choice expect (choices other than confirm_details, which renders inside its card) */}
        {latestExpect?.kind === 'choice' &&
          latestExpect.options &&
          latestState !== 'confirm_details' && (
            <div className="flex flex-wrap gap-1.5 pb-1">
              {latestExpect.options.map((opt, i) => (
                <button
                  key={i}
                  type="button"
                  disabled={loading || uploading}
                  onClick={() => handleChoiceClick(opt.action, opt.label, opt.value)}
                  className="text-xs font-medium px-3 py-1.5 rounded-md border border-orange text-navy hover:bg-orange hover:text-navy active:bg-orange active:text-navy transition-colors disabled:opacity-50 cursor-pointer"
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
            className="h-9 px-3 flex items-center justify-center rounded-md bg-orange text-navy hover:bg-orange/90 disabled:opacity-40 transition-colors cursor-pointer"
          >
            <Send className="h-3.5 w-3.5 text-navy" />
          </button>
        </div>
      </div>
    </div>
  );
};
