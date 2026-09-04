import React, { useState } from 'react';

export default function Dashboard({ onLogout }) {
  const [activePanel, setActivePanel] = useState('command');
  
  return (
    <div>
      <div className="topbar">
        <div className="brand">
          <img className="brand-mark" src="/loha-drishti-logo.svg" alt="Loha Drishti maritime emblem" />
          <div>
            <div className="brand-text">LOHA DRISHTI</div>
            <div className="brand-sub">Maritime Decision Intelligence · SAIL Logistics</div>
          </div>
        </div>

        <div className="nav-menu">
          <a className={activePanel === 'command' ? 'active' : ''} onClick={() => setActivePanel('command')}>⚙ Command Center</a>
          <a className={activePanel === 'intelligence' ? 'active' : ''} onClick={() => setActivePanel('intelligence')}>📊 Intelligence</a>
          <a className={activePanel === 'scenarios' ? 'active' : ''} onClick={() => setActivePanel('scenarios')}>⚡ Scenarios</a>
          <a className={activePanel === 'transparency' ? 'active' : ''} onClick={() => setActivePanel('transparency')}>📖 Data Sources</a>
        </div>

        <div className="topbar-actions">
          <button className="icon-btn" onClick={onLogout}>🚪 Logout</button>
        </div>
      </div>

      <div className="cargo-bar-wrapper">
        <div className="cargo-bar">
          <div className="cargo-summary-pills">
            <div className="cargo-pill"><span className="label">Parcel:</span> <span>80,000 MT</span></div>
            <div className="cargo-pill"><span className="label">Cargo:</span> <span>Coking Coal</span></div>
            <div className="cargo-pill"><span className="label">Origin:</span> <span>Australia</span></div>
          </div>
          <div className="cargo-actions">
            <button className="btn-optimize">⚡ FIND BEST STRATEGY</button>
          </div>
        </div>
      </div>

      <div className="section-tabs">
        <button className={`tab-btn ${activePanel === 'command' ? 'active' : ''}`} onClick={() => setActivePanel('command')}>Command Center</button>
        <button className={`tab-btn ${activePanel === 'intelligence' ? 'active' : ''}`} onClick={() => setActivePanel('intelligence')}>Freight Intelligence</button>
        <button className={`tab-btn ${activePanel === 'transparency' ? 'active' : ''}`} onClick={() => setActivePanel('transparency')}>Data & Methodology</button>
      </div>

      {activePanel === 'command' && (
        <div className="panel active">
          <div className="section">
            <div className="section-header">
              <div>
                <h2>Executive Command Center — WHAT SHOULD I DO?</h2>
                <p>Primary strategy recommendation based on Minimax-Regret optimization across market scenarios.</p>
              </div>
              <span className="section-tag">Recommended Strategy</span>
            </div>
            
            <div style={{textAlign: 'center', padding: '50px 20px', background: 'var(--bg-surface)', border: '1px dashed var(--steel-border)', borderRadius: 'var(--radius-lg)'}}>
              <div style={{fontSize: '32px', marginBottom: '10px'}}>⚡</div>
              <div style={{fontFamily: "'Space Grotesk'", fontSize: '18px', fontWeight: '700', color: 'var(--navy-deep)'}}>Click FIND BEST STRATEGY to begin</div>
              <div style={{fontSize: '13px', color: 'var(--steel-muted)', marginTop: '6px'}}>The decision engine will evaluate all origin-port-vessel combinations.</div>
            </div>
          </div>
        </div>
      )}
      
      {activePanel === 'intelligence' && (
        <div className="panel active">
          <div className="section">
             <div className="section-header">
              <div>
                <h2>Freight Intelligence & Market Pressure</h2>
                <p>Historical trends and market timing signals.</p>
              </div>
            </div>
            <div className="chart-card">
              <h4 style={{margin: '0', fontSize: '14px'}}>Data will load from API...</h4>
            </div>
          </div>
        </div>
      )}
      
      {activePanel === 'transparency' && (
        <div className="panel active">
          <div className="section">
             <div className="section-header">
              <div>
                <h2>Data Sources & Methodology</h2>
                <p>Transparent documentation of all datasets and models used in the platform.</p>
              </div>
            </div>
            <div className="decision-card">
              <h3>Datasets</h3>
              <ul>
                <li><strong>Freight and Shipping Data:</strong> Simulated based on general historical Baltic Dry Index (BDI) and bunker fuel prices to mimic realistic market conditions (Synthetic Benchmark Data).</li>
                <li><strong>Port Data:</strong> Real publicly available parameters (max draft, LOA, loading rates) for major Indian ports like Paradip, Dhamra, Haldia, and Vizag (Real Public Data).</li>
                <li><strong>Vessel Data:</strong> Standardized maritime industry averages for Panamax, Supramax, and Capesize classes (Real Industry Standard Data).</li>
                <li><strong>Commodity/Cargo Data:</strong> Coking coal and limestone operational requirements provided by SAIL specifications (Sample Operational Data).</li>
              </ul>
              <hr style={{margin: '20px 0', borderColor: 'var(--steel-border)', borderStyle: 'solid'}} />
              <h3>Machine Learning Methodology</h3>
              <p>The platform utilizes a <strong>Random Forest Regressor</strong> (Scikit-Learn) to forecast freight rates. It is trained on historical features including Route Distance, Month (Seasonality), Bunker Fuel Price, and Market Pressure Indices. The model achieves an average Mean Absolute Error (MAE) of $2.30/MT and an R2 Score of ~0.95 on the simulated dataset.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
