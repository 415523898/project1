import { createApp } from 'vue'

import { createPinia } from 'pinia'

import App from './App.vue'
import { router } from './router'
import { ApiBase } from './utils/api-base'
import './styles/tokens.css'
import './styles/tailwind.css'
import './styles/dialog-surfaces.css'

function boot(): void {
  ApiBase.applyQueryOverride()
  createApp(App).use(createPinia()).use(router).mount('#app')
}

boot()
