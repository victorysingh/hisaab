'use client';

import { Mic, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export function MicBar() {
  return (
    <div className="fixed inset-x-0 bottom-16 z-30 border-t bg-background p-2">
      <div className="mx-auto flex max-w-md items-center gap-2">
        <Button type="button" size="icon" className="h-12 w-12 shrink-0 rounded-full" aria-label="Speak">
          <Mic className="h-5 w-5" />
        </Button>
        <Input placeholder="Type or speak a command" className="flex-1" />
        <Button type="button" size="icon" variant="outline" aria-label="Send">
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
