import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    requiresGuest?: boolean
    requiresSupervisor?: boolean
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: () => import('@/views/LandingView.vue'),
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { requiresGuest: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { requiresGuest: true },
    },
    {
      path: '/restore',
      name: 'restore',
      component: () => import('@/views/RestoreView.vue'),
      meta: { requiresGuest: true },
    },
    {
      path: '/assignments',
      name: 'assignments',
      component: () => import('@/views/AssignmentsView.vue'),
    },
    {
      path: '/assignments/new',
      name: 'assignments-new',
      component: () => import('@/views/NewAssignmentView.vue'),
      meta: { requiresSupervisor: true },
    },
    {
      path: '/assignments/:id',
      name: 'assignment-detail',
      component: () => import('@/views/AssignmentDetailView.vue'),
      props: (to) => ({ id: Number(to.params.id) }),
    },
    {
      path: '/styleguide',
      name: 'styleguide',
      component: () => import('@/views/StyleGuideView.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  if (to.meta.requiresGuest && auth.isAuthenticated) {
    return { path: '/assignments' }
  }

  if (to.meta.requiresSupervisor && !auth.user?.is_supervisor) {
    return { path: '/assignments' }
  }
})

export default router
