/** First value of a query parameter, trimmed; undefined when missing or blank. */
export function queryValue(value: unknown): string | undefined {
  const text = Array.isArray(value) ? value[0] : value
  return typeof text === 'string' && text.trim() ? text.trim() : undefined
}
