import { createRouter, createWebHistory } from 'vue-router'

import { useLab } from '@/composables/useLab'

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
      meta: { requiresAuth: true },
    },
    { path: '/signin', name: 'signin', component: () => import('@/views/LoginView.vue') },
    { path: '/learning', name: 'learning', component: () => import('@/views/LearningView.vue') },
    {
      path: '/route',
      name: 'route',
      component: () => import('@/views/RouteView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/datasets',
      name: 'datasets',
      component: () => import('@/views/DatasetsView.vue'),
      meta: { requiresAuth: true },
    },
    { path: '/:pathMatch(.*)*', redirect: '/learning' },
  ],
})

router.beforeEach(async (to) => {
  const lab = useLab()
  if (!lab.state.authChecked) await lab.checkAuth()
  if (to.meta.requiresAuth && (!lab.state.user || lab.state.authExpired)) {
    return { name: 'signin', query: { next: to.fullPath } }
  }
  if (to.name === 'signin' && lab.state.user && !lab.state.authExpired) return { name: 'learning' }
  return true
})
