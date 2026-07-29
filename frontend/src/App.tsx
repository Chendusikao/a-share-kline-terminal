export default function App() {
  return (
    <div className="terminal-shell">
      <header className="terminal-header">
        <div>
          <p className="eyebrow">LOCAL MARKET WORKSTATION</p>
          <h1>A 股 K 线终端</h1>
        </div>
        <span className="local-badge">本机模式</span>
      </header>

      <main className="terminal-panel">
        <div aria-hidden="true" className="status-light" />
        <div>
          <p className="scope-label">行情范围</p>
          <p className="scope-value">仅支持 A 股前复权日线</p>
          <p className="status-copy">
            工程环境已就绪，行情功能将在后续任务中接入。
          </p>
        </div>
      </main>

      <footer className="terminal-footer">
        <span>数据来源：AKShare</span>
        <span>不构成投资建议</span>
      </footer>
    </div>
  );
}
