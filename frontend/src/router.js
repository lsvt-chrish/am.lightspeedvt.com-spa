import { createRouter, createWebHistory } from 'vue-router'
import Home from './views/Home.vue'
import LinkBuilderPage from './views/LinkBuilderPage.vue'
import PathScannerPage from './views/PathScannerPage.vue'
import CertificationsChoicePage from './views/CertificationsChoicePage.vue'
import CertificationsByCertPage from './views/CertificationsByCertPage.vue'
import CertificationsByUserPage from './views/CertificationsByUserPage.vue'
import TrainingExportPage from './views/TrainingExportPage.vue'
import CompletionsMappingPage from './views/CompletionsMappingPage.vue'
import CheckUsersPage from './views/CheckUsersPage.vue'
import CoursewareToolsPage from './views/CoursewareToolsPage.vue'
import IntegrationToolsPage from './views/IntegrationToolsPage.vue'

const routes = [
  { path: '/', name: 'Home', component: Home },
  { path: '/credentials', redirect: () => ({ path: '/', query: { openCredentials: '1' } }) },

  { path: '/user-training-data', name: 'UserDataTools', component: CertificationsChoicePage },
  { path: '/user-training-data/by-certification', name: 'UserTrainingDataByCert', component: CertificationsByCertPage },
  { path: '/user-training-data/by-user', name: 'UserTrainingDataByUser', component: CertificationsByUserPage },
  { path: '/user-training-data/export', name: 'UserTrainingDataExport', component: TrainingExportPage },
  { path: '/user-training-data/map-completions', name: 'UserTrainingDataMapCompletions', component: CompletionsMappingPage },
  { path: '/user-training-data/check-users', name: 'UserTrainingDataCheckUsers', component: CheckUsersPage },

  { path: '/courseware-tools', name: 'CoursewareTools', component: CoursewareToolsPage },
  { path: '/courseware-tools/scan', name: 'CoursewareToolsScan', component: PathScannerPage },

  { path: '/integration-tools', name: 'IntegrationTools', component: IntegrationToolsPage },
  { path: '/integration-tools/link-builder', name: 'IntegrationToolsLinkBuilder', component: LinkBuilderPage },

  { path: '/scan', redirect: () => ({ path: '/courseware-tools/scan' }) },
  { path: '/link-builder', redirect: () => ({ path: '/integration-tools/link-builder' }) },
  { path: '/certifications', redirect: () => ({ path: '/user-training-data' }) },
  { path: '/certifications/by-certification', redirect: () => ({ path: '/user-training-data/by-certification' }) },
  { path: '/certifications/by-user', redirect: () => ({ path: '/user-training-data/by-user' }) },
  { path: '/training/export', redirect: () => ({ path: '/user-training-data/export' }) },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
