/** Labels of remote buttons. */

type Translate = (key: string, params?: Record<string, string>) => string;

/**
 * The label of a command: its translation, else the command made readable
 * ("my_app" -> "My app"), never the bare translation key.
 */
export function commandLabel(command: string, t: Translate): string {
  const key = `command.${command}`;
  const text = t(key);
  if (text !== key) {
    return text;
  }
  const words = command.replace(/[_-]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
