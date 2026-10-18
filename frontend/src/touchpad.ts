/**
 * Swipe area for navigation, like the touch surface of an Apple TV remote.
 *
 * Every STEP pixels of movement send one arrow key in the direction that
 * dominates, so a long swipe moves several items. A short tap without
 * movement is OK.
 */

/** Pixels of movement per arrow key. */
export const STEP = 40;
/** Movement that still counts as a tap. */
const TAP_SLOP = 10;
/** Longest press that still counts as a tap (ms). */
const TAP_TIME = 500;

export type Direction = "up" | "down" | "left" | "right";

export class Swipe {
  private originX = 0;
  private originY = 0;
  private startX = 0;
  private startY = 0;
  private startTime = 0;
  private moved = false;

  start(x: number, y: number, time: number): void {
    this.originX = this.startX = x;
    this.originY = this.startY = y;
    this.startTime = time;
    this.moved = false;
  }

  /** The arrow keys this movement adds up to (none until a step is full). */
  move(x: number, y: number): Direction[] {
    if (Math.hypot(x - this.startX, y - this.startY) > TAP_SLOP) {
      this.moved = true;
    }
    const keys: Direction[] = [];
    for (;;) {
      const dx = x - this.originX;
      const dy = y - this.originY;
      if (Math.max(Math.abs(dx), Math.abs(dy)) < STEP) {
        return keys;
      }
      if (Math.abs(dx) >= Math.abs(dy)) {
        keys.push(dx > 0 ? "right" : "left");
        this.originX += Math.sign(dx) * STEP;
        this.originY = y;
      } else {
        keys.push(dy > 0 ? "down" : "up");
        this.originY += Math.sign(dy) * STEP;
        this.originX = x;
      }
    }
  }

  /** True when the touch was a tap (OK). */
  end(x: number, y: number, time: number): boolean {
    if (Math.hypot(x - this.startX, y - this.startY) > TAP_SLOP) {
      this.moved = true;
    }
    return !this.moved && time - this.startTime <= TAP_TIME;
  }
}

/** Storage key of a viewer's choice between arrow keys and touch surface. */
export function touchpadKey(room: string, activity: string): string {
  return `av-scenes-touchpad:${room}:${activity}`;
}

/** The viewer's own choice ("on" / "off") wins over the activity's setting. */
export function useTouchpad(chosen: string | null | undefined, configured: boolean): boolean {
  return chosen === "on" ? true : chosen === "off" ? false : configured;
}
