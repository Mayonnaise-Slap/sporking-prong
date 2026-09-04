import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import './styles/tokens.css'
import './styles/base.css'

const app = createApp(App)

app.use(createPinia())

// Confirm any token that survived a reload is still valid, and load the
// user, before the router evaluates its first navigation guard.
await useAuthStore().initialize()

app.use(router)

app.mount('#app')
