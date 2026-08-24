export function parseBrands(raw) {
  if (raw == null) return []
  if (Array.isArray(raw)) {
    return raw.map(x => String(x).trim()).filter(Boolean)
  }
  const s = String(raw).trim()
  if (!s) return []
  if (s.startsWith('[')) {
    try {
      const arr = JSON.parse(s)
      if (Array.isArray(arr)) return arr.map(x => String(x).trim()).filter(Boolean)
    } catch {}
  }
  return [s]
}

export function brandsToStorage(list) {
  const arr = (list || []).map(x => String(x).trim()).filter(Boolean)
  if (!arr.length) return ''
  if (arr.length === 1) return arr[0]
  return JSON.stringify(arr)
}

export function brandsDisplay(raw, sep = '、') {
  return parseBrands(raw).join(sep)
}

export function primaryBrand(raw) {
  const arr = parseBrands(raw)
  return arr[0] || ''
}
