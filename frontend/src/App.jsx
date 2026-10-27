import { BrowserRouter, Route, Routes } from 'react-router-dom';
import AppLayout from './layouts/AppLayout';
import Dashboard from './pages/Dashboard';
import History from './pages/History';
import Nutrition from './pages/Nutrition';
import Preferences from './pages/Preferences';
import Health from './pages/Health';
import Recommend from './pages/Recommend';
import WhatIf from './pages/WhatIf';
import Budget from './pages/Budget';
import Evidence from './pages/Evidence';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="history" element={<History />} />
          <Route path="nutrition" element={<Nutrition />} />
          <Route path="preferences" element={<Preferences />} />
          <Route path="health" element={<Health />} />
          <Route path="recommend" element={<Recommend />} />
          <Route path="what-if" element={<WhatIf />} />
          <Route path="budget" element={<Budget />} />
          <Route path="evidence" element={<Evidence />} />
          <Route path="*" element={<p>Page not found.</p>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
