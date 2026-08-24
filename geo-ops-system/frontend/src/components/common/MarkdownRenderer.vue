<template>
  <div class="markdown-body" v-html="rendered" />
</template>

<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({ html: false, breaks: true, linkify: true })

// 外部链接(http/https)统一新标签页打开,避免点「仿写样本」等外链时离开当前页、丢失阅读进度。
// 内部锚点(#xxx)等不受影响。
const _defaultLinkOpen = md.renderer.rules.link_open
  || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))
md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const href = tokens[idx].attrGet('href') || ''
  if (/^https?:\/\//i.test(href)) {
    tokens[idx].attrSet('target', '_blank')
    tokens[idx].attrSet('rel', 'noopener noreferrer')
  }
  return _defaultLinkOpen(tokens, idx, options, env, self)
}

const props = defineProps({
  content: { type: String, default: '' }
})

const rendered = computed(() => md.render(props.content || ''))
</script>
