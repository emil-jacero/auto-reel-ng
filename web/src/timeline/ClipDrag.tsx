import {
  useCallback,
  useEffect,
  useMemo,
  useLayoutEffect,
  useRef,
  useSyncExternalStore,
} from "react";
import type { PointerEvent, RefObject } from "react";

import {
  MOVE_CANCEL,
  IGNORE_WORDS,
  MOVE_LOCKED,
  bandSlot,
  dropWords,
  flatMove,
  inBox,
  isOwnPlace,
  pastSlop,
  shiftOf,
  slotLineMs,
} from "./clipDrag";
import type { Box } from "./clipDrag";
import type { DragStore } from "./dragStore";
import { extentMs, pxToTime, timeToPx } from "./model";
import type { Layout, Ms } from "./model";
import type { DrawnChapter, DropSlot } from "./reorder";
import type { TrackClip } from "./layout";

/*
 * A clip's block dragged on the track (`track-drag-edit`, design D2). The press claims the one
 * drag of `dragStore` (shared with trim, edge and card drags) and captures the pointer; past a
 * 3 px slop it is a drag. The block follows the pointer, the clips it passes shift by its width
 * (set on their elements, no render) and a line with words marks the slot. A release dispatches
 * the lists' own edit through `reorder.onDrop`; Escape, a release outside the track or a
 * cancelled pointer drops nothing. A mouse or a pen only: a swipe with touch scrolls the track.
 */

/** What the Timeline gives the track to reorder with. */
export type ReorderModel = {
  /** The drawn chapters, in order, with the clips each plays (as `clips[].chapter` counts them). */
  chapters: readonly DrawnChapter[];
  /** The slot nearest a dragged block whose centre is at this track time (throws on an inconsistent lay). */
  slotAt(identity: string, trackMs: Ms): DropSlot;
  /** A release: one draft edit (nothing when the slot is the clip's own place). */
  onDrop(identity: string, slot: DropSlot): void;
  /** The nearest slot for a clip the track does not draw, at this track time. */
  slotNear(trackMs: Ms): DropSlot;
  /** The identities the track draws. */
  drawn: ReadonlySet<string>;
  /** Whether a client point is over the clip bin: a release there ignores the clip. */
  overBin(x: number, y: number): boolean;
  /** A release over the bin: one draft edit that ignores the clip. */
  onIgnore(identity: string): void;
};

type Context = {
  clips: readonly TrackClip[];
  lay: Layout;
  pps: number;
  reorder: ReorderModel;
  locked: boolean;
  announce: (words: string) => void;
  onSelectClip: (identity: string) => void;
  /** Whether a press at this client x lands on a cut's or a card's span (selected, not dragged). */
  onSpan: (identity: string, clientX: number) => boolean;
};

type Press = {
  id: number;
  token: object;
  identity: string;
  index: number;
  x: number;
  y: number;
  started: boolean;
  refused: boolean;
  /** The slot a release would use, null when it would drop nothing. */
  slot: DropSlot | null;
  /** A release now would ignore the clip: the pointer is over the bin. */
  ignore: boolean;
  off: (() => void) | null;
};

/** The chapter bands' boxes (client px) by the drawn chapter's index. */
function bandBoxes(canvas: HTMLElement): { chapter: number; box: Box }[] {
  const boxes: { chapter: number; box: Box }[] = [];
  for (const node of canvas.querySelectorAll<HTMLElement>(
    ".tl-chapter[data-chapter]",
  )) {
    const rect = node.getBoundingClientRect();
    boxes.push({
      chapter: Number(node.dataset.chapter),
      box: {
        left: rect.left,
        right: rect.right,
        top: rect.top,
        bottom: rect.bottom,
      },
    });
  }
  return boxes;
}

/**
 * The press handlers of a clip's block. Stable: they read the latest context through a ref, so
 * the memoized blocks are not redrawn by a drag.
 */
export function useClipDrag(
  drag: DragStore,
  canvas: RefObject<HTMLDivElement | null>,
  viewport: RefObject<HTMLDivElement | null>,
  context: Context,
) {
  const now = useRef(context);
  now.current = context;
  const press = useRef<Press | null>(null);
  // A drag ends in a click on the block; that click selects nothing.
  const dragged = useRef(false);

  const end = useCallback(
    (event: { currentTarget: HTMLElement; pointerId: number } | null) => {
      const p = press.current;
      press.current = null;
      if (p === null) {
        return;
      }
      p.off?.();
      drag.setClip(null);
      drag.unclaim(p.token);
      if (
        event !== null &&
        event.currentTarget.hasPointerCapture?.(event.pointerId)
      ) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
    },
    [drag],
  );

  const update = useCallback(
    (p: Press, event: PointerEvent<HTMLElement>) => {
      const c = now.current;
      const clip = c.clips[p.index];
      const el = canvas.current;
      const box = viewport.current?.getBoundingClientRect();
      if (clip === undefined || el === null || box === undefined) {
        return;
      }
      const widthMs = extentMs(clip.kept);
      const dxPx = event.clientX - p.x;
      const base = { identity: p.identity, dxPx, from: p.index, widthMs };
      const outside = !inBox(
        { left: box.left, right: box.right, top: box.top, bottom: box.bottom },
        event.clientX,
        event.clientY,
      );
      if (outside) {
        p.slot = null;
        p.ignore = c.reorder.overBin(event.clientX, event.clientY);
        drag.setClip({
          ...base,
          to: p.index,
          lineMs: null,
          words: p.ignore ? IGNORE_WORDS : MOVE_CANCEL,
        });
        return;
      }
      p.ignore = false;
      let slot: DropSlot | null = null;
      const band = bandBoxes(el).find((b) =>
        inBox(b.box, event.clientX, event.clientY),
      );
      if (band !== undefined) {
        slot = bandSlot(c.reorder.chapters, band.chapter, p.identity);
      }
      if (slot === null) {
        const centre =
          c.lay.startsMs[p.index] + widthMs / 2 + pxToTime(dxPx, c.pps);
        try {
          slot = c.reorder.slotAt(p.identity, centre);
        } catch {
          slot = null;
        }
      }
      if (slot === null) {
        p.slot = null;
        drag.setClip({ ...base, to: p.index, lineMs: null, words: "" });
        return;
      }
      const own = isOwnPlace(c.reorder.chapters, slot, p.identity);
      p.slot = own ? null : slot;
      const starts = c.lay.startsMs.slice(0, c.clips.length);
      const extents = c.clips.map((k) => extentMs(k.kept));
      drag.setClip({
        ...base,
        to: flatMove(c.reorder.chapters, slot, p.identity).to,
        lineMs: slotLineMs(
          starts,
          extents,
          c.reorder.chapters,
          slot,
          p.identity,
        ),
        words: dropWords(own, slot),
      });
    },
    [drag, canvas, viewport],
  );

  useEffect(() => () => end(null), [end]);

  return useMemo(
    () => ({
      /** Whether the click that follows a drag is to be ignored; reads and clears. */
      consumeDragged(): boolean {
        const was = dragged.current;
        dragged.current = false;
        return was;
      },
      onDown(
        event: PointerEvent<HTMLElement>,
        identity: string,
        index: number,
      ) {
        if (event.button !== 0 || event.pointerType === "touch") {
          return;
        }
        dragged.current = false;
        end(null);
        // A press on a cut's or a card's span selects that and is not dragged.
        if (now.current.onSpan(identity, event.clientX)) {
          return;
        }
        const token = {};
        if (!drag.claim(token)) {
          return;
        }
        const target = event.currentTarget;
        target.setPointerCapture(event.pointerId);
        const cancel = (key: KeyboardEvent) => {
          if (key.key === "Escape") {
            key.preventDefault();
            key.stopPropagation();
            end({ currentTarget: target, pointerId: event.pointerId });
          }
        };
        // A scroll of the track mid-drag would move the slots under a still pointer (and may unmount
        // the captured block): it cancels.
        const scroller = viewport.current;
        const scrolled = () =>
          end({ currentTarget: target, pointerId: event.pointerId });
        // A context-menu request while the press is held (`clip-context-menu`, D4) runs before
        // React's root listener. An unstarted press ends quietly and the request goes on to open
        // the menu (a Ctrl+click on macOS presses button 0 first); a started drag is cancelled as
        // Escape does, and the event is prevented: neither our menu nor the browser's opens.
        const menu = (request: Event) => {
          const p = press.current;
          if (p === null || p.token !== token) {
            return;
          }
          if (p.started) {
            request.preventDefault();
          }
          end({ currentTarget: target, pointerId: event.pointerId });
        };
        window.addEventListener("keydown", cancel, true);
        window.addEventListener("contextmenu", menu, true);
        scroller?.addEventListener("scroll", scrolled);
        press.current = {
          id: event.pointerId,
          token,
          identity,
          index,
          x: event.clientX,
          y: event.clientY,
          started: false,
          refused: false,
          slot: null,
          ignore: false,
          off: () => {
            window.removeEventListener("keydown", cancel, true);
            window.removeEventListener("contextmenu", menu, true);
            scroller?.removeEventListener("scroll", scrolled);
          },
        };
      },
      onMove(event: PointerEvent<HTMLElement>) {
        const p = press.current;
        if (p === null || p.id !== event.pointerId) {
          return;
        }
        if (!p.started) {
          if (!pastSlop(event.clientX - p.x, event.clientY - p.y)) {
            return;
          }
          dragged.current = true;
          if (now.current.locked) {
            if (!p.refused) {
              p.refused = true;
              now.current.announce(MOVE_LOCKED);
            }
            return;
          }
          p.started = true;
          now.current.onSelectClip(p.identity);
        }
        update(p, event);
      },
      onUp(event: PointerEvent<HTMLElement>) {
        const p = press.current;
        if (p === null || p.id !== event.pointerId) {
          return;
        }
        const slot = p.started ? p.slot : null;
        const ignore = p.started && p.ignore;
        const identity = p.identity;
        end(event);
        if (ignore) {
          now.current.reorder.onIgnore(identity);
        } else if (slot !== null) {
          now.current.reorder.onDrop(identity, slot);
        }
      },
      onCancel(event: PointerEvent<HTMLElement>) {
        const p = press.current;
        if (p === null || p.id !== event.pointerId) {
          return;
        }
        end(event);
      },
      onLostCapture(event: PointerEvent<HTMLElement>) {
        const p = press.current;
        if (p === null || p.id !== event.pointerId) {
          return;
        }
        end(null);
      },
    }),
    [end, update, drag, viewport],
  );
}

/**
 * The drag in the air, drawn: the block follows the pointer and the clips it passes make room
 * (their elements are translated here, no render), and a line stands at the slot with its words.
 */
export function ClipDragLayer({
  drag,
  canvas,
  pps,
}: {
  drag: DragStore;
  canvas: RefObject<HTMLDivElement | null>;
  pps: number;
}) {
  const lineMs = useSyncExternalStore(
    drag.subscribe,
    () => drag.getClip()?.lineMs ?? null,
  );
  const words = useSyncExternalStore(
    drag.subscribe,
    () => drag.getClip()?.words ?? "",
  );
  const active = useSyncExternalStore(
    drag.subscribe,
    () => drag.getClip() !== null,
  );
  useLayoutEffect(() => {
    const el = canvas.current;
    if (!active || el === null) {
      return undefined;
    }
    const moved = new Set<HTMLElement>();
    const lifted = new Set<HTMLElement>();
    const apply = () => {
      const d = drag.getClip();
      if (d === null) {
        return;
      }
      const width = timeToPx(d.widthMs, pps);
      for (const node of el.querySelectorAll<HTMLElement>(
        ".tl-clip[data-index], .tl-clip-press[data-index]",
      )) {
        const at = Number(node.dataset.index);
        const by = at === d.from ? d.dxPx : shiftOf(d.from, d.to, at) * width;
        const value = by === 0 ? "" : `${by}px 0`;
        if (node.style.translate !== value) {
          node.style.translate = value;
          moved.add(node);
        }
        if (at === d.from && node.dataset.lifted === undefined) {
          node.dataset.lifted = "true";
          lifted.add(node);
        }
      }
    };
    apply();
    const off = drag.subscribe(apply);
    return () => {
      off();
      for (const node of moved) {
        node.style.translate = "";
      }
      for (const node of lifted) {
        delete node.dataset.lifted;
      }
    };
  }, [active, drag, canvas, pps]);
  if (!active) {
    return null;
  }
  return (
    <>
      {lineMs !== null && (
        <div
          className="tl-drop-line"
          aria-hidden="true"
          style={{ insetInlineStart: timeToPx(lineMs, pps) }}
        />
      )}
      {words !== "" && (
        <div
          className="tl-drop-words"
          style={{
            insetInlineStart: lineMs === null ? 0 : timeToPx(lineMs, pps),
          }}
        >
          {words}
        </div>
      )}
    </>
  );
}
