import { createRouter, createWebHistory } from 'vue-router'
import Home from './views/Home.vue'
import LinkBuilderPage from './views/LinkBuilderPage.vue'
import PathScannerPage from './views/PathScannerPage.vue'
import CertificationsChoicePage from './views/CertificationsChoicePage.vue'
import CertificationsByCertPage from './views/CertificationsByCertPage.vue'
import CertificationsByUserPage from './views/CertificationsByUserPage.vue'

const routes = [
  { path: '/', name: 'Home', component: Home },
  { path: '/credentials', redirect: () => ({ path: '/', query: { openCredentials: '1' } }) },
  { path: '/link-builder', name: 'LinkBuilder', component: LinkBuilderPage },
  { path: '/scan', name: 'Scan', component: PathScannerPage },
  { path: '/certifications', name: 'Certifications', component: CertificationsChoicePage },
  { path: '/certifications/by-certification', name: 'CertificationsByCert', component: CertificationsByCertPage },
  { path: '/certifications/by-user', name: 'CertificationsByUser', component: CertificationsByUserPage },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
