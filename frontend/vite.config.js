import { defineConfig } from 'vite'
import { resolve } from 'path'

export default defineConfig({
  root: '.',
  build: {
    rollupOptions: {
      input: {
        dashboard:      resolve(__dirname, 'dashboard.html'),
        mantenimiento:  resolve(__dirname, 'mantenimiento.html'),
        inventario:     resolve(__dirname, 'inventario.html'),
        planta_lab:     resolve(__dirname, 'planta_lab.html'),
        rh_seguridad:   resolve(__dirname, 'rh_seguridad.html'),
        finanzas:       resolve(__dirname, 'finanzas.html'),
        operacion_mina: resolve(__dirname, 'operacion_mina.html'),
        taller:         resolve(__dirname, 'taller.html'),
        caseta:         resolve(__dirname, 'caseta.html'),
        laboratorio:    resolve(__dirname, 'laboratorio.html'),
        bodega:         resolve(__dirname, 'bodega.html'),
        auditorias:     resolve(__dirname, 'auditorias.html'),
      }
    }
  }
})
