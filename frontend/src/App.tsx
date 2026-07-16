
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { Home } from './pages/Home';
import { CreateProject } from './pages/CreateProject';
import { ProjectWorkspace } from './pages/ProjectWorkspace';
import { Documents } from './pages/Documents';
import { Predict } from './pages/Predict';
import { Reports } from './pages/Reports';
import { Skills } from './pages/Skills';
import { Settings } from './pages/Settings';

function App() {
  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <div className="min-h-screen bg-bp-base">
        <Navbar />
        <main className="pb-12">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/projects" element={<Navigate to="/" replace />} />
            <Route path="/projects/new" element={<CreateProject />} />
            <Route path="/projects/:projectId" element={<ProjectWorkspace />} />
            <Route path="/predict" element={<Predict />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/workflow" element={<Navigate to="/" replace />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/skills" element={<Skills />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
