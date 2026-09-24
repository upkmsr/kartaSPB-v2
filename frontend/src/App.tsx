import { useEffect, useState } from "react";
import { fetchReadiness } from "./api/health";
import { LayerControl } from "./components/LayerControl";
import { MapWorkspace } from "./components/MapWorkspace";
import { StatusIndicator } from "./components/StatusIndicator";
import { defaultVisibleLayerIds } from "./map/layerRegistry";

type ConnectionState = "checking" | "ready" | "offline";
const INITIAL_ZOOM = 12;

export function App() {
  const [backend, setBackend] = useState<ConnectionState>("checking");
  const [postgis, setPostgis] = useState<ConnectionState>("checking");
  const [zoom, setZoom] = useState(INITIAL_ZOOM);
  const [visibleLayerIds, setVisibleLayerIds] = useState(defaultVisibleLayerIds);

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

  const toggleLayer = (layerId: string) => {
    setVisibleLayerIds((current) => {
      const next = new Set(current);
      if (next.has(layerId)) next.delete(layerId);
      else next.add(layerId);
      return next;
    });
  };

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
          <span className="version">FOUNDATION 4</span>
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

          <LayerControl
            visibleLayerIds={visibleLayerIds}
            zoom={zoom}
            onToggle={toggleLayer}
          />

          <div className="sidebar-note">
            <span>04</span>
            <p>Объекты загружаются из canonical catalog для текущего окна карты.</p>
          </div>
        </aside>

        <MapWorkspace visibleLayerIds={visibleLayerIds} onZoomChange={setZoom} />
      </div>

      <div className="viewport-warning" role="alert">
        <strong>KARTASPB — desktop GIS</strong>
        <span>Для работы рекомендуется экран шириной от 1280 px.</span>
      </div>
    </div>
  );
}
