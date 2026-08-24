// 平台/模型 logo 图标 + 名称 的单一可信源。
// 全站所有"平台展示"都应走这里(或 <PlatformIcon> 组件),以后换图标只改一处。
// 图标资源优先使用 public/ai-icons/*.png，缺失时回退 *.svg。

const ICONS = {
  chatgpt: '/ai-icons/chatgpt',
  gemini: '/ai-icons/gemini',
  google_aio: '/ai-icons/google_aio',
  google_aim: '/ai-icons/google_aim',
  perplexity: '/ai-icons/perplexity',
  copilot: '/ai-icons/copilot',
  // 搜索/国产平台等
  deepseek: '/ai-icons/deepseek',
  doubao: '/ai-icons/doubao',
  qwen: '/ai-icons/qwen',
  wenxin: '/ai-icons/wenxin',
  yuanbao: '/ai-icons/yuanbao',
  kimi: '/ai-icons/kimi',
}

// 图标文件名固定时，给 URL 带版本号可避免浏览器继续使用旧缓存。
const ICON_VERSION = '20260731p'

// 把任意写法(中文名 / 模型代号大小写)归一到图标 key;无图标的平台返回 ''
function platformKey(p) {
  const s = String(p || '').toLowerCase()
  // ChatGPT
  if (s.includes('chatgpt') || s.includes('gpt') || s === 'openai') return 'chatgpt'
  // Gemini
  if (s.includes('gemini') || s === 'bard' || s === 'google gemini') return 'gemini'
  // 通义千问 / Qwen
  if (s.includes('qwen') || s.includes('千问') || s.includes('通义')) return 'qwen'
  // 文心一言
  if (s.includes('wenxin') || s.includes('文心')) return 'wenxin'
  // 元宝
  if (s.includes('yuanbao') || s.includes('元宝')) return 'yuanbao'
  // 豆包
  if (s.includes('doubao') || s.includes('豆包')) return 'doubao'
  // DeepSeek
  if (s.includes('deepseek') || s.includes('deep seek')) return 'deepseek'
  // Google AIO (AI Overview)
  if (s.includes('aio') || s.includes('ai overview')) return 'google_aio'
  // Google AIM (AI Mode)
  if (s.includes('aim') || s.includes('ai mode')) return 'google_aim'
  // Perplexity
  if (s.includes('perplexity') || s === 'pplx') return 'perplexity'
  // Copilot
  if (s.includes('copilot') || s === 'bing' || s.includes('microsoft copilot')) return 'copilot'
  // Kimi
  if (s.includes('kimi')) return 'kimi'
  return ''
}

// 模型代号 → 中文显示名
const NAME = {
  chatgpt: 'ChatGPT', gemini: 'Gemini', google_aio: 'Google AIO',
  google_aim: 'Google AIM', perplexity: 'Perplexity', copilot: 'Copilot',
  deepseek: 'DeepSeek', doubao: '豆包', qwen: '通义千问', wenxin: '文心一言', yuanbao: '元宝', kimi: 'Kimi',
}

const ABBR = {
  'ChatGPT': 'GPT', 'Gemini': 'Gem', 'Google AIO': 'AIO',
  'Google AIM': 'AIM', 'Perplexity': 'PPLX', 'Copilot': 'COP',
  'DeepSeek': 'DS', '豆包': '豆', '通义千问': '千', '文心一言': '文', '元宝': '元', 'Kimi': 'KM',
}

export function platformIcon(p) {
  const k = platformKey(p)
  return k ? `${ICONS[k]}.png?v=${ICON_VERSION}` : ''
}

export function platformIconFallback(p) {
  const k = platformKey(p)
  return k ? `${ICONS[k]}.svg?v=${ICON_VERSION}` : ''
}

// Kimi 主体「K」是白色,需深底;其余白底
export function platformIconBg(p) {
  return platformKey(p) === 'kimi' ? '#1a1b20' : '#ffffff'
}

export function platformName(p) {
  const k = platformKey(p)
  return k ? (NAME[k] || p) : p
}

// 无图标时的文字回退(缩写)
export function platformAbbr(p) {
  const d = platformName(p)
  return ABBR[d] || String(d || '').slice(0, 2)
}
