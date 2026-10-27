import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';

const LINKS = [
  ['/', 'Dashboard'],
  ['/history', 'Food history'],
  ['/nutrition', 'Nutrition'],
  ['/preferences', 'Preferences'],
  ['/health', 'Health indicators'],
  ['/recommend', 'Next meal'],
  ['/what-if', 'What-if simulator'],
  ['/budget', 'Budget simulator'],
  ['/evidence', 'Data & evidence'],
];

export default function AppLayout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="app">
      <header className="topbar">
        <div className="container-xxl d-flex align-items-center justify-content-between gap-3">
          <NavLink to="/" className="brand" onClick={() => setOpen(false)}>
            FoodSpend <span>Insights</span>
          </NavLink>
          <button className="btn btn-sm btn-outline-light d-lg-none" aria-expanded={open} aria-controls="mainnav"
            onClick={() => setOpen(!open)}>
            Menu
          </button>
          <nav id="mainnav" className={`mainnav ${open ? 'open' : ''}`} aria-label="Main">
            {LINKS.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === '/'} onClick={() => setOpen(false)}>
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <div className="synthetic-banner" role="note">
        <div className="container-xxl">
          Synthetic data for a fictional person (“Synthetic Persona A”). Decision support only, not medical advice.
        </div>
      </div>
      <main className="container-xxl py-4">
        <Outlet />
      </main>
    </div>
  );
}
