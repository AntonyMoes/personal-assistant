import { Outlet, NavLink } from 'react-router-dom';

export default function Layout() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <nav className="nav">
          <NavLink to="/chat" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Chats
          </NavLink>
          <NavLink to="/memories" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Memories
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Settings
          </NavLink>
        </nav>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
