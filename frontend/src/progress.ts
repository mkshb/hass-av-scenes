/** What a start or stop is busy with, as the card shows it below the progress bar. */
import { clock } from "./now-playing";

/** av_scenes/control/subscribe: "current" while a room starts or stops. */
export interface Current {
  kind: string;
  /** The device or entity */
  name: string | null;
  /** When a wait ends (ISO time); for "ready" the latest it ends */
  until?: string;
  step?: number;
  steps?: number;
  step_type?: string;
  hook?: string;
}

/** av_scenes/control/subscribe: a power switch cut after its devices cooled down. */
export interface Cooling {
  outlet: string;
  /** The devices that cool down */
  names: string[];
  /** When the power goes off (ISO time) */
  until: string;
}

type Translate = (key: string, params?: Record<string, string>) => string;

function timeLeft(until: string, now: number): string {
  const left = Math.max(0, Math.ceil((Date.parse(until) - now) / 1000));
  return left >= 60 ? clock(left) : `${left} s`;
}

/** "Cooling down: Epson Beamer" and "power off in 2:30". */
export function coolingText(cooling: Cooling, now: number, t: Translate): { text: string; time: string } {
  const names = cooling.names.length ? cooling.names.join(", ") : cooling.outlet;
  return {
    text: t("cooling.text", { names }),
    time: t("cooling.time", { time: timeLeft(cooling.until, now) }),
  };
}

/** "Waiting for Epson Beamer" and "at most 0:42", or undefined for nothing to show. */
export function progressText(
  current: Current | null | undefined,
  now: number,
  t: Translate,
): { text: string; time?: string } | undefined {
  if (!current) {
    return undefined;
  }
  const name = current.name ?? "";
  const position = { step: String(current.step ?? ""), steps: String(current.steps ?? "") };
  let text: string;
  switch (current.kind) {
    case "step": {
      const label = t(`step.${current.step_type}`);
      text = t("doing.step", { ...position, what: name ? `${label} (${name})` : label });
      break;
    }
    case "wait":
      text = t("doing.wait", position);
      break;
    case "hooks":
      text = t(`doing.hooks_${current.hook}`);
      break;
    default:
      text = t(`doing.${current.kind}`, { name });
  }
  if (!current.until) {
    return { text };
  }
  const time = timeLeft(current.until, now);
  return { text, time: t(current.kind === "ready" ? "doing.at_most" : "doing.left", { time }) };
}
