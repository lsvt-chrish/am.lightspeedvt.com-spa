import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { initTheme } from './composables/useTheme'
import './index.css'

initTheme()

const app = createApp(App).use(router)

// Wait for the router to resolve the initial route before mounting: without
// this, the app renders once with an unresolved route (meta is undefined,
// so App.vue's `v-if="!route.meta.chromeless"` briefly shows the sidebar/nav
// even on chromeless routes like the iframed VetComm page) and then
// re-renders once routing catches up -- visible as a flash of the normal
// app shell before the intended page appears.
router.isReady().then(() => {
  app.mount('#app')
})
