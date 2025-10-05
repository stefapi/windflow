import { defineConfig, presetUno, presetAttributify, presetIcons } from 'unocss'

export default defineConfig({
  presets: [
    presetUno(),
    presetAttributify(),
    presetIcons({
      scale: 1.2,
      warn: true,
    }),
  ],
  theme: {
    colors: {
      primary: {
        DEFAULT: '#409EFF',
        light: '#79bbff',
        lighter: '#a0cfff',
        dark: '#337ecc',
      },
      success: {
        DEFAULT: '#67C23A',
        light: '#95d475',
        dark: '#529b2e',
      },
      warning: {
        DEFAULT: '#E6A23C',
        light: '#ebb563',
        dark: '#b88230',
      },
      danger: {
        DEFAULT: '#F56C6C',
        light: '#f89898',
        dark: '#c45656',
      },
      info: {
        DEFAULT: '#909399',
        light: '#b1b3b8',
        dark: '#73767a',
      },
    },
  },
  shortcuts: {
    'flex-center': 'flex items-center justify-center',
    'flex-between': 'flex items-center justify-between',
    'card': 'bg-white rounded-lg shadow-sm p-4',
    'btn': 'px-4 py-2 rounded cursor-pointer transition-all',
    'btn-primary': 'btn bg-primary text-white hover:bg-primary-dark',
    'btn-success': 'btn bg-success text-white hover:bg-success-dark',
    'btn-warning': 'btn bg-warning text-white hover:bg-warning-dark',
    'btn-danger': 'btn bg-danger text-white hover:bg-danger-dark',
  },
})
