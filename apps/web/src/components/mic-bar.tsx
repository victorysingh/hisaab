'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Check, Loader2, Mic, Send, Volume2, VolumeX, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api, WHAT_IF_EVENT, WHAT_IF_STORAGE_KEY, type WhatIfChange } from '@/lib/api';

type AgentAction = { tool: string; args: Record<string, unknown>; summary: string };
type AgentReply = {
  intent: string;
  reply_text: string;
  ui_hint: 'show_dues' | 'show_forecast' | 'show_home' | 'refresh' | null;
  proposed_actions: AgentAction[];
  what_if_changes: WhatIfChange[] | null;
};

// Minimal typing for the browser's built-in speech recognition (Chrome / Edge).
type SpeechResultEvent = {
  resultIndex: number;
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
};
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: SpeechResultEvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  start(): void;
  stop(): void;
}
function createRecognition(): Recognition | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => Recognition;
    webkitSpeechRecognition?: new () => Recognition;
  };
  const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
  return Ctor ? new Ctor() : null;
}

export const DATA_CHANGED_EVENT = 'hisaab:data-changed';

const SUGGESTIONS = [
  "Who hasn't paid?",
  'Will I manage rent next month?',
  'What if Kabir pays 15 days late?',
  'Who should I chase today?',
  'Aisha paid 2500 cash',
];
const YES = /^(yes|yeah|yep|haan|ha|han|ji|confirm|ok|okay|sure|kar do|theek hai|done)\b/i;
const NO = /^(no|nahi|nahin|cancel|stop|mat)\b/i;

export function MicBar() {
  const router = useRouter();
  const pathname = usePathname();
  const [text, setText] = useState('');
  const [listening, setListening] = useState(false);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [reply, setReply] = useState<string | null>(null);
  const [pending, setPending] = useState<AgentAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const recRef = useRef<Recognition | null>(null);
  const finalRef = useRef('');

  const speak = useCallback(
    (words: string) => {
      if (muted || typeof window === 'undefined' || !('speechSynthesis' in window)) return;
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(words.replace(/₹/g, 'rupees '));
      const voice = window.speechSynthesis.getVoices().find((v) => v.lang === 'en-IN');
      if (voice) u.voice = voice;
      u.lang = 'en-IN';
      u.rate = 1.05;
      window.speechSynthesis.speak(u);
    },
    [muted],
  );

  const show = useCallback(
    (words: string) => {
      setReply(words);
      setOpen(true);
      speak(words);
    },
    [speak],
  );

  function route(r: AgentReply) {
    if (r.ui_hint === 'show_forecast') {
      const changes = r.what_if_changes ?? [];
      if (pathname === '/forecast') {
        window.dispatchEvent(new CustomEvent(WHAT_IF_EVENT, { detail: { changes } }));
      } else {
        try {
          if (changes.length) sessionStorage.setItem(WHAT_IF_STORAGE_KEY, JSON.stringify(changes));
        } catch {
          // storage unavailable
        }
        router.push('/forecast');
      }
    } else if (r.ui_hint === 'show_dues' && pathname !== '/dues') {
      router.push('/dues');
    } else if (r.ui_hint === 'show_home' && pathname !== '/') {
      router.push('/');
    }
  }

  async function confirmAction(action: AgentAction) {
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ reply_text: string }>('/agent/confirm', {
        method: 'POST',
        body: JSON.stringify({ action }),
      });
      setPending(null);
      show(r.reply_text);
      window.dispatchEvent(new Event(DATA_CHANGED_EVENT));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function send(raw: string) {
    const words = raw.trim();
    if (!words) return;
    setText('');
    setError(null);
    setOpen(true);
    if (pending && YES.test(words)) return confirmAction(pending);
    if (pending && NO.test(words)) {
      setPending(null);
      return show('Okay, cancelled.');
    }
    setBusy(true);
    try {
      const r = await api<AgentReply>('/agent/turn', {
        method: 'POST',
        body: JSON.stringify({ transcript: words, language: 'en-IN' }),
      });
      setPending(r.proposed_actions[0] ?? null);
      show(r.reply_text);
      route(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function toggleMic() {
    if (listening) {
      recRef.current?.stop();
      return;
    }
    const rec = createRecognition();
    if (!rec) {
      setOpen(true);
      setError('Voice needs Chrome or Edge. You can type the command instead.');
      return;
    }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel();
    finalRef.current = '';
    rec.lang = 'en-IN';
    rec.interimResults = true;
    rec.continuous = false;
    rec.onresult = (e) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) finalRef.current += res[0].transcript;
        else interim += res[0].transcript;
      }
      setText((finalRef.current + ' ' + interim).trim());
    };
    rec.onerror = (e) => {
      setListening(false);
      if (e.error === 'not-allowed') setError('Microphone permission is blocked. Allow it in the address bar, or type.');
      else if (e.error !== 'no-speech' && e.error !== 'aborted') setError(`Voice error: ${e.error}`);
    };
    rec.onend = () => {
      setListening(false);
      const said = finalRef.current.trim();
      if (said) void send(said);
    };
    recRef.current = rec;
    setOpen(true);
    setError(null);
    setListening(true);
    rec.start();
  }

  useEffect(() => () => recRef.current?.stop(), []);

  // Prompt chips elsewhere on the page ask through this event.
  const sendRef = useRef(send);
  useEffect(() => {
    sendRef.current = send;
  });
  useEffect(() => {
    const onAsk = (e: Event) => void sendRef.current((e as CustomEvent<{ text: string }>).detail.text);
    window.addEventListener('hisaab:ask', onAsk);
    return () => window.removeEventListener('hisaab:ask', onAsk);
  }, []);

  return (
    <>
      {open && (
        <div className="fixed bottom-36 left-1/2 z-30 w-full max-w-md -translate-x-1/2 px-2">
          <div className="brut-card pop p-3">
            <div className="flex items-start gap-2">
              <div className="min-w-0 flex-1 space-y-2 text-sm">
                {listening && <p className="font-medium text-red-600">Listening… speak now</p>}
                {busy && (
                  <p className="flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" /> Thinking…
                  </p>
                )}
                {!listening && !busy && reply && <p className="text-base leading-snug">{reply}</p>}
                {error && <p className="text-red-700">{error}</p>}
                {!listening && !busy && !reply && !error && (
                  <div className="space-y-2">
                    <p className="text-muted-foreground">Tap the mic and speak, or try:</p>
                    <div className="flex flex-wrap gap-1.5">
                      {SUGGESTIONS.map((s) => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => void send(s)}
                          className="rounded-full border-2 border-[var(--ink)] bg-white px-2.5 py-1 text-xs font-semibold hover:bg-[var(--lime)]"
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {pending && !busy && (
                  <div className="flex gap-2 pt-1">
                    <Button type="button" size="sm" onClick={() => void confirmAction(pending)}>
                      <Check className="mr-1 h-4 w-4" /> Confirm
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setPending(null);
                        show('Okay, cancelled.');
                      }}
                    >
                      Cancel
                    </Button>
                    <span className="self-center text-xs text-muted-foreground">or say &quot;yes&quot;</span>
                  </div>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <button
                  type="button"
                  aria-label="Close"
                  onClick={() => {
                    setOpen(false);
                    setReply(null);
                    setError(null);
                  }}
                  className="rounded p-1 text-muted-foreground hover:bg-muted"
                >
                  <X className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  aria-label={muted ? 'Unmute replies' : 'Mute replies'}
                  onClick={() => {
                    setMuted((m) => !m);
                    if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel();
                  }}
                  className="rounded p-1 text-muted-foreground hover:bg-muted"
                >
                  {muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="fixed bottom-16 left-1/2 z-30 w-full max-w-md -translate-x-1/2 border-t-2 border-[var(--ink)] bg-[var(--paper)] p-2 md:border-x-2">
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void send(text);
          }}
        >
          <Button
            type="button"
            size="icon"
            onClick={toggleMic}
            className={
              'h-12 w-12 shrink-0 rounded-full border-2 border-[var(--ink)] shadow-[3px_3px_0_var(--ink)] ' +
              (listening
                ? 'animate-pulse bg-[var(--coral)] text-white hover:bg-[var(--coral)]'
                : 'mic-ring bg-[var(--ink)] text-[var(--lime)] hover:bg-[var(--ink)]')
            }
            aria-label={listening ? 'Stop listening' : 'Speak'}
          >
            <Mic className="h-5 w-5" />
          </Button>
          <Input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onFocus={() => setOpen(true)}
            placeholder={pending ? 'Say "yes" to confirm' : 'Ask anything… "will I make rent?"'}
            className="h-11 flex-1 rounded-full border-2 border-[var(--ink)] bg-white px-4"
          />
          <Button
            type="submit"
            size="icon"
            variant="outline"
            aria-label="Send"
            disabled={busy || !text.trim()}
            className="h-11 w-11 rounded-full border-2 border-[var(--ink)] bg-[var(--saffron)] hover:bg-[var(--saffron)]"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </>
  );
}
