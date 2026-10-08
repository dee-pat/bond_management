import "../../../bond_management/public/js/clipboard.js";

type ClipboardRuntime = {
  bond_management: {
    utils: {
      clipboard: {
        sanitize: (
          value: unknown,
          options?: { numeric?: boolean; unicodeControls?: boolean }
        ) => string;
      };
    };
  };
};

export function sanitizeClipboardText(value: unknown): string {
  return (
    globalThis as typeof globalThis & ClipboardRuntime
  ).bond_management.utils.clipboard.sanitize(value, { unicodeControls: true });
}
