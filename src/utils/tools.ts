/** Format tool name for display. MCP tools (mcp__server_id__tool_name) show as tool_name. */
export function formatToolDisplayName(name: string): string {
  if (!name.startsWith("mcp__")) return name;
  const parts = name.split("__");
  if (parts.length >= 3) return parts.slice(2).join("__");
  return name;
}
