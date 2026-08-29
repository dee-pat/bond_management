export function toFilterValue(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  return String(value);
}
