import { createApp } from 'vue'

import App from './App.vue'
import { createAppI18n } from './shared/i18n'
import { createAppRouter } from './router'
import './shared/styles/main.css'

createApp(App).use(createAppRouter()).use(createAppI18n()).mount('#app')
