import { createRouter, createWebHistory, type RouterHistory } from 'vue-router'

import PlacesPage from '@/features/weather/pages/PlacesPage.vue'
import SearchPage from '@/features/weather/pages/SearchPage.vue'

export function createAppRouter(history: RouterHistory = createWebHistory()) {
  return createRouter({
    history,
    routes: [
      { path: '/', name: 'search', component: SearchPage },
      // Every place matching a name (/places?q=Odessa), to pick the one that was meant.
      { path: '/places', name: 'places', component: PlacesPage },
      // Unknown paths go back to the search page instead of a blank screen.
      { path: '/:pathMatch(.*)*', redirect: '/' },
    ],
  })
}
