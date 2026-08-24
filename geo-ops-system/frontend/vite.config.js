import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  build: {
    // 不生成 source map，避免暴露原始代码结构
    sourcemap: false,
    // esbuild 是 vite 默认 minifier；下面配合 esbuild.drop 移除 console / debugger
    minify: 'esbuild',
    // 调高 chunk 警告阈值
    chunkSizeWarningLimit: 4000,
    rollupOptions: {
      output: {
        // 资源文件名加 hash，且不暴露原始模块路径
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
        // 拆分第三方库到独立长缓存 chunk：vendor 跨部署 hash 稳定 → 浏览器缓存命中，
        // 只重下变更的应用代码；xlsx(~1MB,仅导出用)单独成块按需加载,不进主包。
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('xlsx')) return 'vendor-xlsx'
          if (id.includes('element-plus') || id.includes('@element-plus')) return 'vendor-element'
          if (id.includes('markdown-it') || id.includes('entities') || id.includes('linkify')
              || id.includes('mdurl') || id.includes('uc.micro') || id.includes('punycode')) return 'vendor-md'
          if (id.includes('/vue') || id.includes('@vue') || id.includes('vue-router')
              || id.includes('pinia')) return 'vendor-vue'
          return 'vendor'
        },
      },
    },
  },
  esbuild: {
    // 生产构建移除所有 console.* 和 debugger，避免泄露日志/调试信息
    drop: ['console', 'debugger'],
    // 注释也一并移除
    legalComments: 'none',
  },
  server: {
    port: 3106,
    open: false,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:7008',  // Changed from 7007
        changeOrigin: true
      }
    }
  }
})
