import { useEffect, useState } from "react";
import { fetchReadiness } from "./api/health";
import { MapWorkspace } from "./components/MapWorkspace";
import { StatusIndicator } from "./components/StatusIndicator";

type ConnectionState = "checking" | "ready" | "offline";

export function App() {
  const [backend, setBackend] = useState<ConnectionState>("checking");
  const [postgis, setPostgis] = useState<ConnectionState>("checking");

  useEffect(() => {
    const controller = new AbortController();
    fetchReadiness(controller.signal)
      .then((report) => {
        setBackend(report.status === "ready" ? "ready" : "offline");
        setPostgis(report.postgis.status === "ready" ? "ready" : "offline");
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setBackend("offline");
          setPostgis("offline");
        }
      });
    return () => controller.abort();
  }, []);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            К
          </span>
          <div>
            <h1>KARTASPB</h1>
            <p>Data-driven GIS platform</p>
          </div>
        </div>
        <div className="topbar-meta">
          <span>59°57′ N</span>
          <span>30°19′ E</span>
          <span className="version">FOUNDATION 0</span>
        </div>
      </header>

      <div className="workspace">
        <aside className="sidebar" aria-label="Панель инструментов">
          <section>
            <p className="section-label">System</p>
            <StatusIndicator label="Backend" status={backend} />
            <StatusIndicator label="PostGIS" status={postgis} />
          </section>

          <section>
            <p className="section-label">Workspace</p>
            <button className="nav-item nav-item--active" type="button">
              <span className="nav-icon">⌖</span>
              Обзор карты
            </button>
            <button className="nav-item" type="button" disabled>
              <span className="nav-icon">◇</span>
              Слои
              <span className="soon">SOON</span>
            </button>
            <button className="nav-item" type="button" disabled>
              <span className="nav-icon">∿</span>
              Аналитика
              <span className="soon">SOON</span>
            </button>
          </section>

          <div className="sidebar-note">
            <span>01</span>
            <p>Архитектурный фундамент готов к подключению открытых GIS-данных.</p>
          </div>
        </aside>

        <MapWorkspace />
      </div>

      <div className="viewport-warning" role="alert">
        <strong>KARTASPB — desktop GIS</strong>
        <span>Для работы рекомендуется экран шириной от 1280 px.</span>
      </div>
    </div>
  );
}
