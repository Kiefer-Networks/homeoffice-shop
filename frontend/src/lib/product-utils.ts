const GROUP_LABELS: Record<string, string> = {
  colour_name: 'Color',
  color_name: 'Color',
  style_name: 'Style',
  size_name: 'Size',
}

export function formatGroupLabel(group: string): string {
  return GROUP_LABELS[group.toLowerCase()] || group.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}
