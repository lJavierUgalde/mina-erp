import { defineConfig } from 'vite'
import { resolve } from 'path'

export default defineConfig({
  root: '.',
  build: {
    rollupOptions: {
      input: {
        index:         resolve(__dirname, 'index.html'),
        operacion:     resolve(__dirname, 'operacion-mina.html'),
        planta:        resolve(__dirname, 'planta-calidad.html'),
        logistica:     resolve(__dirname, 'logistica-fletes.html'),
      }
    }
  }
})
