import { useEffect } from 'react';
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom';
import Layout from './components/Layout';
import { AuthProvider } from './hooks/useAuth';
import { PendingFileProvider } from './hooks/usePendingFile';
import About from './pages/About';
import History from './pages/History';
import Home from './pages/Home';
import Login from './pages/Login';
import NotFound from './pages/NotFound';
import Processing from './pages/Processing';
import Register from './pages/Register';
import Result from './pages/Result';
import Upload from './pages/Upload';

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

export default function App() {
  return (
    <AuthProvider>
      <PendingFileProvider>
        <BrowserRouter>
          <ScrollToTop />
          <Layout>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/upload" element={<Upload />} />
              <Route path="/processing/:jobId" element={<Processing />} />
              <Route path="/result/:jobId" element={<Result />} />
              <Route path="/history" element={<History />} />
              <Route path="/about" element={<About />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Layout>
        </BrowserRouter>
      </PendingFileProvider>
    </AuthProvider>
  );
}
