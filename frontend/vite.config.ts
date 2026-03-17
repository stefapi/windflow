import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import UnoCSS from 'unocss/vite'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import Icons from 'unplugin-icons/vite'
import IconsResolver from 'unplugin-icons/resolver'
import path from 'node:path'
import Starter from 'unplugin-vue-jsx/vite'
import Shiki from 'markdown-it-shiki'
import { visualizer } from 'rollup-plugin-visualizer'
import ElementPlus from 'unplugin-element-plus/vite'
import { FileSystemIconLoader } from 'unplugin-icons/loaders'
import { default as Inspector } from 'unplugin-vue-inspector/vite'
import VueMacros from 'unplugin-vue-macros/vite'
import Markdown from 'unplugin-vue-markdown/vite'
import { VueRouterAutoImports } from 'unplugin-vue-router'
import VueRouter from 'unplugin-vue-router/vite'
import compression from 'vite-plugin-compression'
import dts from 'vite-plugin-dts'
import Inspect from 'vite-plugin-inspect'
import mkcert from 'vite-plugin-mkcert'
import { VitePWA } from 'vite-plugin-pwa'
import VueDevTools from 'vite-plugin-vue-devtools'
import webfontDownload from 'vite-plugin-webfont-dl'

// https://vitejs.dev/config/
// @ts-ignore
export default defineConfig({
  plugins: [
    // https://github.com/vue-macros/vue-macros
    VueMacros({
      plugins: {
        vue: vue({
          include: [/\.vue$/, /\.md$/],
        }),
        vueJsx: Starter(),
      },
    }),
    // https://github.com/posva/unplugin-vue-router
    VueRouter({
      /* options */
      routesFolder: 'src/pages',
      extensions: ['.vue', '.md'],
      dts: 'src/types/typed-router.d.ts',
      routeBlockLang: 'yaml', // or json, depending on your preference
    }),
    ElementPlus({
      useSource: true, // Enable customizable SCSS styles
    }),
    // 🧪 Vite plugin inspection tools
    Inspect({
      build: true,
      outputDir: '.vite-inspect',
    }),


    Inspector({
      launchEditor: 'pycharm',
    }),

    mkcert(),

    // https://github.com/antfu/vite-plugin-pwa
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'safari-pinned-tab.svg'],
      base: '/',
      workbox: {
        globPatterns: ['manifest.webmanifest', '**/*.{js,css,html,ico,png,svg,webp,woff,woff2,ttf}'],
      },
      manifest: {
        name: 'VesselHarbor',
        short_name: 'VesselHarbor',
        description: 'Self-hosted platform for managing and orchestrating containerized applications and virtual machines',
        theme_color: '#ffffff',
        background_color: '#ffffff',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        // strategies: "injectManifest",
        icons: [
          {
            src: '/pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable',
          },
        ],
      },
    }),
    UnoCSS(),
    AutoImport({
      imports: [
        'vue',
        'vue-router',
        'pinia',
        '@vueuse/core',
        VueRouterAutoImports,
        {
          '@/composables/api': ['useAuth', 'useUsers', 'useGroups', 'useOrganizations', 'useEnvironments'],
          '@/composables/ui': ['useModal', 'useTable', 'useForm', 'globalModal', 'validationRules'],
          '@/composables/business': ['usePermissions', 'useValidation', 'businessValidationRules', 'ACTIONS', 'RESOURCES'],
        },
      ],
      dts: 'src/auto-imports.d.ts',
      dirs: ['src/services', 'src/store'],
      vueTemplate: true,
    }),
    // https://github.com/antfu/unplugin-icons
    Icons({
      compiler: 'vue3',
      autoInstall: true,
      scale: 1.5, // Default scale for icons
      defaultClass: 'icon', // Default CSS class
      customCollections: {
        // Your custom icons
        'my-icons': FileSystemIconLoader('./src/assets/icons'),
      },
    }),
    // 🧩 Auto-import Vue components
    Components({
      dts: 'src/components.d.ts',
      dirs: ['src/components'],
      extensions: ['vue', 'md'],
      resolvers: [
        ElementPlusResolver(),
        IconsResolver({
          prefix: 'i', // Optional prefix (default: 'i')
          enabledCollections: ['carbon', 'fa', 'mdi', 'twemoji', 'material-symbols'], // Enabled collections
        }),
      ],
      deep: true,
    }),
    Markdown({
      headEnabled: true,
      markdownItSetup(md) {

        md.use(Shiki)
      },
    }),

    dts({
      rollupTypes: true,
      entryRoot: 'src', // root directory for the declaration files
      cleanVueFileName: true, // removes .vue suffix from filenames
      staticImport: true, // uses static imports in declaration files
      exclude: ['src/views/**/*.vue'], // Exclude large view components from type generation (TS7056 fix)
    }),

    // 🐞 Vue Devtools in development (local)
    VueDevTools(),
    // Performance optimizations

    compression(),
    // Webfont download

    webfontDownload(),

    // Bundle analysis (only in build mode)
    visualizer({
      open: true,
      gzipSize: true,
      brotliSize: true,
    }),
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: process.env.VITE_FRONTEND_PORT ? parseInt(process.env.VITE_FRONTEND_PORT) : 5173,
    // @ts-expect-error - Plugin callable issue
    https: false,
    watch: {
      ignored: ['!**/src/layouts/**'], // 👈 Vite will watch this folder
    },
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8010',
        changeOrigin: true,
        // Handle FastAPI redirects (e.g., /api/v1/targets -> /api/v1/targets/)
        followRedirects: true,
        // Preserve the full path including query params during redirect
        rewrite: (path) => path,
      },
      '/ws': {
        target: process.env.VITE_WS_URL || 'ws://localhost:8010',
        ws: true,
      },
    },
  },
  preview: {
    port: 3000, // Preview server port for built files
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "sass:math";`,
      },
    },
  },
  base: './',
  build: {
    manifest: true,
    target: 'esnext',
    minify: 'esbuild',
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'element-plus': ['element-plus', '@element-plus/icons-vue'],
          'vue-flow': ['@vue-flow/core', '@vue-flow/controls', '@vue-flow/minimap', '@vue-flow/background'],
        },
      },
    },
  },
  optimizeDeps: {
    include: ['vue', 'vue-router', 'pinia', 'pinia-plugin-persistedstate', 'element-plus', '@vueuse/core', 'axios', '@iconify/vue', '@unhead/vue', 'nprogress', 'idb', 'workbox-window'],
  },
})
