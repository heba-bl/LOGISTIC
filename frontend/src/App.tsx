import { Navigate, Route, Routes } from 'react-router-dom'

import { AppLayout } from '@/layouts/AppLayout'
import AiAssistant from '@/pages/AiAssistant'
import Alertes from '@/pages/Alertes'
import AnalyticsLayout from '@/pages/analytics/AnalyticsLayout'
import ProductionRisques from '@/pages/analytics/ProductionRisques'
import QualiteFlux from '@/pages/analytics/QualiteFlux'
import StockEntrepot from '@/pages/analytics/StockEntrepot'
import VueGlobale from '@/pages/analytics/VueGlobale'
import DonneesOperationnelles from '@/pages/DonneesOperationnelles'
import Entry from '@/pages/Entry'
import FichierOperationnel from '@/pages/FichierOperationnel'
import Inspection from '@/pages/Inspection'
import MissionControl from '@/pages/MissionControl'
import NotFound from '@/pages/NotFound'
import Production from '@/pages/Production'
import Quality from '@/pages/Quality'
import Rapports from '@/pages/Rapports'
import Referentiel from '@/pages/Referentiel'
import Receiving from '@/pages/Receiving'
import Settings from '@/pages/Settings'
import Traceability from '@/pages/Traceability'
import Warehouse from '@/pages/Warehouse'

export default function App() {
  return (
    <Routes>
      {/* The entrance sits outside the shell: it has no sidebar, no topbar and
          no page chrome, because it is not a page of the application yet. */}
      <Route path="/" element={<Entry />} />
      <Route element={<AppLayout />}>
        <Route path="/mission-control" element={<MissionControl />} />
        <Route path="/alertes" element={<Alertes />} />
        {/* The operator station is gone: operators work in the shared
            workbook, and this site is not in their hands. The address is
            kept so an old bookmark lands somewhere sensible. */}
        <Route path="/operateur" element={<Navigate to="/mission-control" replace />} />

        <Route path="/donnees" element={<FichierOperationnel />} />
        <Route path="/donnees/imports" element={<DonneesOperationnelles />} />
        {/* Previous address, kept so existing links do not break. */}
        <Route path="/data-import" element={<Navigate to="/donnees" replace />} />

        <Route path="/receiving" element={<Receiving />} />
        <Route path="/inspection" element={<Inspection />} />
        <Route path="/quality" element={<Quality />} />
        <Route path="/warehouse" element={<Warehouse />} />
        <Route path="/production" element={<Production />} />

        <Route path="/traceability" element={<Traceability />} />
        <Route path="/rapports" element={<Rapports />} />
        <Route path="/referentiel" element={<Referentiel />} />
        {/* The four Analytics tabs share one window and one request. */}
        <Route path="/analytics" element={<AnalyticsLayout />}>
          <Route index element={<VueGlobale />} />
          <Route path="stock" element={<StockEntrepot />} />
          <Route path="qualite" element={<QualiteFlux />} />
          <Route path="production" element={<ProductionRisques />} />
        </Route>
        <Route path="/ai-assistant" element={<AiAssistant />} />

        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
