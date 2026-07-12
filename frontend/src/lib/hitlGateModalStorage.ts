import type { HitlGateInfo } from '@/types';

export function buildHitlGateEventKey(runId: string, gate?: HitlGateInfo | null): string {
  return `${runId}:${gate?.stage ?? 'unknown'}:${gate?.paused_at ?? 'unknown'}`;
}

function seenStorageKey(eventKey: string): string {
  return `aisci_hitl_modal_seen_${eventKey}`;
}

export function hasSeenHitlGateModal(eventKey: string): boolean {
  try {
    return sessionStorage.getItem(seenStorageKey(eventKey)) === '1';
  } catch {
    return false;
  }
}

export function markHitlGateModalSeen(eventKey: string): void {
  try {
    sessionStorage.setItem(seenStorageKey(eventKey), '1');
  } catch {
    /* ignore */
  }
}

export function clearHitlGateModalSeenForRun(runId: string): void {
  try {
    const prefix = `aisci_hitl_modal_seen_${runId}:`;
    const toRemove: string[] = [];
    for (let i = 0; i < sessionStorage.length; i += 1) {
      const key = sessionStorage.key(i);
      if (key?.startsWith(prefix)) toRemove.push(key);
    }
    toRemove.forEach((key) => sessionStorage.removeItem(key));
  } catch {
    /* ignore */
  }
}
