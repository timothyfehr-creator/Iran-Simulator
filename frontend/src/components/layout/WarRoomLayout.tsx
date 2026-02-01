import { useState } from 'react';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { MainView } from './MainView';
import { TimelineSlider } from '../timeline/TimelineSlider';
import { ErrorBoundary } from './ErrorBoundary';

export function WarRoomLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex flex-col h-screen bg-war-room-bg">
      <ErrorBoundary>
        <Header
          onMenuClick={() => setSidebarOpen(!sidebarOpen)}
          showMenuButton={true}
        />
      </ErrorBoundary>

      <div className="flex flex-1 overflow-hidden gap-0">
        <ErrorBoundary>
          <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        </ErrorBoundary>

        <ErrorBoundary>
          <MainView />
        </ErrorBoundary>
      </div>

      <ErrorBoundary>
        <div className="panel border-t border-war-room-border rounded-none px-5 py-4">
          <TimelineSlider />
        </div>
      </ErrorBoundary>
    </div>
  );
}
