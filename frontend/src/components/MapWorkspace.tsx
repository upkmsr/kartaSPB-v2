export function MapWorkspace() {
  return (
    <main className="map-workspace" aria-label="Рабочая область карты">
      <div className="map-grid" aria-hidden="true" />
      <div className="map-coordinate map-coordinate--top">59.9343° N</div>
      <div className="map-coordinate map-coordinate--bottom">30.3351° E</div>
      <div className="map-placeholder">
        <span className="map-placeholder__marker" aria-hidden="true" />
        <p className="eyebrow">Map workspace</p>
        <h2>Пространственные данные появятся здесь</h2>
        <p>MapLibre готов к подключению слоёв на следующем этапе.</p>
      </div>
    </main>
  );
}
