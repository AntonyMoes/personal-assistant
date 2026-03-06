import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import ChatListPage from './pages/ChatListPage';
import ChatPage from './pages/ChatPage';
import MemoriesPage from './pages/MemoriesPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/chat" replace />} />
        <Route path="chat" element={<ChatListPage />} />
        <Route path="chat/:chatId" element={<ChatPage />} />
        <Route path="memories" element={<MemoriesPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
