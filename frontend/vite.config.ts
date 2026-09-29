import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  base: './', // caminhos relativos: funciona no GitHub Pages e em qualquer pasta
  plugins: [react(), tailwindcss()],
  build: { chunkSizeWarningLimit: 800 },
})
